"""
Twitter Feed - Free alternatives for Twitter/X data

Since Twitter API is expensive ($100/month), we use:
1. Nitter instances (free Twitter frontend)
2. Web scraping with proxies
3. Third-party aggregators

Note: For production, consider Twitter API Basic ($100/mo) for reliability
"""
import asyncio
import logging
import re
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import aiohttp
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


@dataclass
class Tweet:
    text: str
    author: str
    likes: int
    retweets: int
    timestamp: datetime
    symbols_mentioned: List[str] = None
    
    def __post_init__(self):
        if self.symbols_mentioned is None:
            self.symbols_mentioned = []


class TwitterFeed:
    """
    Twitter data via free alternatives
    
    Methods:
    1. Nitter instances (Twitter mirror)
    2. Social Blade / Social Searcher (limited)
    3. Manual tracking of key accounts
    
    Key Trading Accounts to Monitor:
    - @jimcramer
    - @DeItaone (news)
    - @unusual_whales
    - @WallStMemes
    - @Mr_Derivatives
    """
    
    # Nitter instances (may change, some go down)
    NITTER_INSTANCES = [
        'nitter.net',
        'nitter.it',
        'nitter.nl'
    ]
    
    # Key trading accounts to monitor
    TRADING_ACCOUNTS = [
        'DeItaone',      # Breaking news
        'unusual_whales', # Options flow
        'WallStMemes',   # Memes/sentiment
        'jimcramer',     # Inverse indicator :)
        'zaborsky',      # Options
        'Mr_Derivatives' # Derivatives
    ]
    
    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None
        self._working_nitter: Optional[str] = None
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        logger.info("Twitter Feed initialized (using Nitter)")
    
    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(headers=self.headers)
        return self._session
    
    async def _find_working_nitter(self) -> Optional[str]:
        """Find a working Nitter instance"""
        if self._working_nitter:
            return self._working_nitter
        
        session = await self._get_session()
        
        for instance in self.NITTER_INSTANCES:
            try:
                url = f"https://{instance}"
                async with session.get(url, timeout=5) as response:
                    if response.status == 200:
                        self._working_nitter = instance
                        logger.info(f"Using Nitter instance: {instance}")
                        return instance
            except:
                continue
        
        logger.warning("No working Nitter instance found")
        return None
    
    async def get_user_tweets(
        self,
        username: str,
        limit: int = 10
    ) -> List[Tweet]:
        """Get recent tweets from a user via Nitter"""
        nitter = await self._find_working_nitter()
        if not nitter:
            return []
        
        try:
            session = await self._get_session()
            url = f"https://{nitter}/{username}"
            
            async with session.get(url) as response:
                if response.status == 200:
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    tweets = []
                    tweet_items = soup.find_all('div', class_='timeline-item')[:limit]
                    
                    for item in tweet_items:
                        content = item.find('div', class_='tweet-content')
                        if content:
                            text = content.get_text(strip=True)
                            
                            # Extract mentioned symbols
                            symbols = re.findall(r'\$([A-Z]{1,5})', text)
                            
                            # Get stats
                            stats = item.find_all('span', class_='tweet-stat')
                            likes = 0
                            retweets = 0
                            for stat in stats:
                                if 'like' in str(stat):
                                    likes = self._parse_count(stat.get_text())
                                elif 'retweet' in str(stat):
                                    retweets = self._parse_count(stat.get_text())
                            
                            tweets.append(Tweet(
                                text=text[:500],
                                author=username,
                                likes=likes,
                                retweets=retweets,
                                timestamp=datetime.now(timezone.utc),
                                symbols_mentioned=list(set(symbols))
                            ))
                    
                    return tweets
                return []
        except Exception as e:
            logger.error(f"Twitter feed error: {e}")
            return []
    
    def _parse_count(self, text: str) -> int:
        """Parse count like '1.2K' to integer"""
        try:
            text = text.strip().upper()
            if 'K' in text:
                return int(float(text.replace('K', '')) * 1000)
            elif 'M' in text:
                return int(float(text.replace('M', '')) * 1000000)
            return int(text)
        except:
            return 0
    
    async def get_trading_feed(self, limit_per_account: int = 5) -> List[Tweet]:
        """Get tweets from all tracked trading accounts"""
        all_tweets = []
        
        for account in self.TRADING_ACCOUNTS:
            tweets = await self.get_user_tweets(account, limit_per_account)
            all_tweets.extend(tweets)
            await asyncio.sleep(1)  # Be respectful
        
        # Sort by engagement
        all_tweets.sort(key=lambda x: x.likes + x.retweets, reverse=True)
        return all_tweets
    
    async def search_symbol(self, symbol: str) -> List[Tweet]:
        """Search for tweets mentioning a symbol"""
        nitter = await self._find_working_nitter()
        if not nitter:
            return []
        
        try:
            session = await self._get_session()
            url = f"https://{nitter}/search?f=tweets&q=%24{symbol.upper()}"
            
            async with session.get(url) as response:
                if response.status == 200:
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    tweets = []
                    tweet_items = soup.find_all('div', class_='timeline-item')[:20]
                    
                    for item in tweet_items:
                        content = item.find('div', class_='tweet-content')
                        username = item.find('a', class_='username')
                        
                        if content:
                            tweets.append(Tweet(
                                text=content.get_text(strip=True)[:500],
                                author=username.get_text() if username else 'unknown',
                                likes=0,
                                retweets=0,
                                timestamp=datetime.now(timezone.utc),
                                symbols_mentioned=[symbol.upper()]
                            ))
                    
                    return tweets
                return []
        except Exception as e:
            logger.error(f"Twitter search error: {e}")
            return []
    
    async def get_symbol_sentiment(self, symbol: str) -> Dict[str, Any]:
        """Get sentiment for a symbol from Twitter"""
        tweets = await self.search_symbol(symbol)
        
        if not tweets:
            return {
                'symbol': symbol,
                'score': 0,
                'confidence': 0,
                'tweet_count': 0
            }
        
        # Simple sentiment based on keywords
        bullish_words = ['buy', 'long', 'calls', 'moon', 'bullish', 'up', 'pump', 'rocket']
        bearish_words = ['sell', 'short', 'puts', 'crash', 'bearish', 'down', 'dump', 'tank']
        
        bullish_count = 0
        bearish_count = 0
        
        for tweet in tweets:
            text_lower = tweet.text.lower()
            for word in bullish_words:
                if word in text_lower:
                    bullish_count += 1
                    break
            for word in bearish_words:
                if word in text_lower:
                    bearish_count += 1
                    break
        
        total = bullish_count + bearish_count
        if total > 0:
            score = (bullish_count - bearish_count) / total
        else:
            score = 0
        
        return {
            'symbol': symbol,
            'score': round(score, 3),
            'confidence': min(len(tweets) / 20, 1.0),
            'tweet_count': len(tweets),
            'bullish_count': bullish_count,
            'bearish_count': bearish_count
        }
    
    def get_status(self) -> Dict[str, Any]:
        return {
            "configured": True,
            "method": "Nitter (free Twitter mirror)",
            "working_instance": self._working_nitter,
            "tracked_accounts": self.TRADING_ACCOUNTS,
            "note": "For production, consider Twitter API Basic ($100/mo)"
        }
    
    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
