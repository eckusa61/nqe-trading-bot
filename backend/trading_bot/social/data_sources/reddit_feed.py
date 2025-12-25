"""
Reddit Feed - Free sentiment data from finance subreddits

Subreddits tracked:
- r/wallstreetbets
- r/stocks
- r/investing
- r/options
- r/forex
- r/cryptocurrency
"""
import os
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import aiohttp
import base64

logger = logging.getLogger(__name__)


@dataclass
class RedditPost:
    title: str
    subreddit: str
    score: int
    num_comments: int
    url: str
    created_utc: datetime
    selftext: str = ""
    symbols_mentioned: List[str] = None
    
    def __post_init__(self):
        if self.symbols_mentioned is None:
            self.symbols_mentioned = []


class RedditFeed:
    """
    Reddit API client for financial sentiment
    """
    
    FINANCE_SUBREDDITS = [
        'wallstreetbets',
        'stocks', 
        'investing',
        'options',
        'forex',
        'cryptocurrency',
        'StockMarket',
        'Daytrading',
        'algotrading'
    ]
    
    # Common stock ticker pattern
    TICKER_PATTERN = r'\$([A-Z]{1,5})\b|\b([A-Z]{2,5})\b'
    
    def __init__(self):
        self.client_id = os.environ.get('REDDIT_CLIENT_ID')
        self.client_secret = os.environ.get('REDDIT_CLIENT_SECRET')
        self.user_agent = 'NQE_Trading_Bot/1.0'
        self._access_token: Optional[str] = None
        self._token_expires: Optional[datetime] = None
        self._session: Optional[aiohttp.ClientSession] = None
        
        self.is_configured = bool(self.client_id and self.client_secret)
        if self.is_configured:
            logger.info("Reddit Feed initialized with API credentials")
        else:
            logger.warning("Reddit Feed: No API credentials, using public endpoints")
    
    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session
    
    async def _get_access_token(self) -> Optional[str]:
        """Get OAuth access token"""
        if not self.is_configured:
            return None
        
        # Check if token is still valid
        if self._access_token and self._token_expires:
            if datetime.now(timezone.utc) < self._token_expires:
                return self._access_token
        
        try:
            session = await self._get_session()
            auth = base64.b64encode(
                f"{self.client_id}:{self.client_secret}".encode()
            ).decode()
            
            headers = {
                'Authorization': f'Basic {auth}',
                'User-Agent': self.user_agent
            }
            
            data = {
                'grant_type': 'client_credentials'
            }
            
            async with session.post(
                'https://www.reddit.com/api/v1/access_token',
                headers=headers,
                data=data
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    self._access_token = result['access_token']
                    self._token_expires = datetime.now(timezone.utc) + timedelta(seconds=result['expires_in'] - 60)
                    return self._access_token
                else:
                    logger.error(f"Reddit auth failed: {response.status}")
                    return None
        except Exception as e:
            logger.error(f"Reddit auth error: {e}")
            return None
    
    async def get_hot_posts(
        self,
        subreddit: str = 'wallstreetbets',
        limit: int = 25
    ) -> List[RedditPost]:
        """Get hot posts from a subreddit"""
        try:
            session = await self._get_session()
            
            # Try authenticated request first
            token = await self._get_access_token()
            
            if token:
                headers = {
                    'Authorization': f'Bearer {token}',
                    'User-Agent': self.user_agent
                }
                url = f'https://oauth.reddit.com/r/{subreddit}/hot'
            else:
                # Public endpoint (rate limited)
                headers = {'User-Agent': self.user_agent}
                url = f'https://www.reddit.com/r/{subreddit}/hot.json'
            
            params = {'limit': limit}
            
            async with session.get(url, headers=headers, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    posts = []
                    
                    children = data.get('data', {}).get('children', [])
                    for child in children:
                        post_data = child.get('data', {})
                        
                        # Extract mentioned symbols
                        import re
                        text = f"{post_data.get('title', '')} {post_data.get('selftext', '')}"
                        symbols = re.findall(r'\$([A-Z]{1,5})', text)
                        
                        post = RedditPost(
                            title=post_data.get('title', ''),
                            subreddit=subreddit,
                            score=post_data.get('score', 0),
                            num_comments=post_data.get('num_comments', 0),
                            url=f"https://reddit.com{post_data.get('permalink', '')}",
                            created_utc=datetime.fromtimestamp(
                                post_data.get('created_utc', 0),
                                tz=timezone.utc
                            ),
                            selftext=post_data.get('selftext', '')[:500],
                            symbols_mentioned=list(set(symbols))
                        )
                        posts.append(post)
                    
                    return posts
                else:
                    logger.error(f"Reddit API error: {response.status}")
                    return []
        except Exception as e:
            logger.error(f"Reddit feed error: {e}")
            return []
    
    async def get_all_finance_posts(self, limit_per_sub: int = 10) -> List[RedditPost]:
        """Get posts from all finance subreddits"""
        all_posts = []
        
        for subreddit in self.FINANCE_SUBREDDITS:
            posts = await self.get_hot_posts(subreddit, limit_per_sub)
            all_posts.extend(posts)
            await asyncio.sleep(0.5)  # Rate limiting
        
        # Sort by score
        all_posts.sort(key=lambda x: x.score, reverse=True)
        return all_posts
    
    async def get_symbol_mentions(self, symbol: str, limit: int = 50) -> List[RedditPost]:
        """Search for posts mentioning a specific symbol"""
        all_posts = await self.get_all_finance_posts(limit_per_sub=25)
        
        # Filter posts mentioning the symbol
        symbol_upper = symbol.upper()
        matching = [
            post for post in all_posts
            if symbol_upper in post.symbols_mentioned or
               symbol_upper in post.title.upper() or
               f'${symbol_upper}' in post.title
        ]
        
        return matching[:limit]
    
    async def get_trending_tickers(self, min_mentions: int = 2) -> Dict[str, int]:
        """Get trending tickers across all finance subreddits"""
        all_posts = await self.get_all_finance_posts(limit_per_sub=25)
        
        # Count symbol mentions
        ticker_counts: Dict[str, int] = {}
        
        for post in all_posts:
            for symbol in post.symbols_mentioned:
                if len(symbol) >= 2 and len(symbol) <= 5:
                    ticker_counts[symbol] = ticker_counts.get(symbol, 0) + 1
        
        # Filter by minimum mentions
        trending = {
            k: v for k, v in ticker_counts.items()
            if v >= min_mentions
        }
        
        # Sort by count
        return dict(sorted(trending.items(), key=lambda x: x[1], reverse=True))
    
    def get_status(self) -> Dict[str, Any]:
        return {
            "configured": self.is_configured,
            "subreddits_tracked": self.FINANCE_SUBREDDITS,
            "has_valid_token": bool(self._access_token)
        }
    
    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
