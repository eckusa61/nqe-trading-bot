"""
News Feed - Free financial news aggregation

Sources:
- NewsAPI (100 requests/day free)
- Alpha Vantage News (free)
- Finviz News (scraping)
"""
import os
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import aiohttp

logger = logging.getLogger(__name__)


@dataclass
class NewsArticle:
    title: str
    source: str
    url: str
    published: datetime
    summary: str = ""
    sentiment: Optional[str] = None
    symbols: List[str] = None
    
    def __post_init__(self):
        if self.symbols is None:
            self.symbols = []


class NewsFeed:
    """
    Aggregates news from multiple free sources
    """
    
    NEWSAPI_BASE = "https://newsapi.org/v2"
    ALPHAVANTAGE_BASE = "https://www.alphavantage.co/query"
    
    def __init__(self):
        self.newsapi_key = os.environ.get('NEWSAPI_KEY')
        self.alphavantage_key = os.environ.get('ALPHAVANTAGE_KEY')
        self._session: Optional[aiohttp.ClientSession] = None
        
        logger.info(f"News Feed initialized (NewsAPI: {bool(self.newsapi_key)}, AlphaVantage: {bool(self.alphavantage_key)})")
    
    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session
    
    async def get_market_news(self, limit: int = 20) -> List[NewsArticle]:
        """Get general market news"""
        articles = []
        
        # Try NewsAPI first
        if self.newsapi_key:
            newsapi_articles = await self._get_newsapi_articles(
                query='stock market OR trading OR finance',
                limit=limit
            )
            articles.extend(newsapi_articles)
        
        # Also try Alpha Vantage
        if self.alphavantage_key:
            av_articles = await self._get_alphavantage_news(limit=limit)
            articles.extend(av_articles)
        
        # Sort by date
        articles.sort(key=lambda x: x.published, reverse=True)
        return articles[:limit]
    
    async def get_symbol_news(self, symbol: str, limit: int = 10) -> List[NewsArticle]:
        """Get news for a specific symbol"""
        articles = []
        
        if self.newsapi_key:
            newsapi_articles = await self._get_newsapi_articles(
                query=f'"{symbol}" stock',
                limit=limit
            )
            articles.extend(newsapi_articles)
        
        if self.alphavantage_key:
            av_articles = await self._get_alphavantage_symbol_news(symbol, limit)
            articles.extend(av_articles)
        
        articles.sort(key=lambda x: x.published, reverse=True)
        return articles[:limit]
    
    async def _get_newsapi_articles(
        self,
        query: str,
        limit: int = 20
    ) -> List[NewsArticle]:
        """Get articles from NewsAPI"""
        if not self.newsapi_key:
            return []
        
        try:
            session = await self._get_session()
            url = f"{self.NEWSAPI_BASE}/everything"
            params = {
                'q': query,
                'apiKey': self.newsapi_key,
                'language': 'en',
                'sortBy': 'publishedAt',
                'pageSize': limit
            }
            
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    return [
                        NewsArticle(
                            title=a.get('title', ''),
                            source=a.get('source', {}).get('name', 'Unknown'),
                            url=a.get('url', ''),
                            published=datetime.fromisoformat(
                                a.get('publishedAt', '').replace('Z', '+00:00')
                            ) if a.get('publishedAt') else datetime.now(timezone.utc),
                            summary=a.get('description', '')[:300]
                        )
                        for a in data.get('articles', [])
                    ]
                else:
                    logger.error(f"NewsAPI error: {response.status}")
                    return []
        except Exception as e:
            logger.error(f"NewsAPI error: {e}")
            return []
    
    async def _get_alphavantage_news(
        self,
        limit: int = 20
    ) -> List[NewsArticle]:
        """Get news from Alpha Vantage"""
        if not self.alphavantage_key:
            return []
        
        try:
            session = await self._get_session()
            url = self.ALPHAVANTAGE_BASE
            params = {
                'function': 'NEWS_SENTIMENT',
                'apikey': self.alphavantage_key,
                'limit': limit
            }
            
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    feed = data.get('feed', [])
                    
                    return [
                        NewsArticle(
                            title=a.get('title', ''),
                            source=a.get('source', 'Unknown'),
                            url=a.get('url', ''),
                            published=datetime.strptime(
                                a.get('time_published', '')[:15],
                                '%Y%m%dT%H%M%S'
                            ).replace(tzinfo=timezone.utc) if a.get('time_published') else datetime.now(timezone.utc),
                            summary=a.get('summary', '')[:300],
                            sentiment=a.get('overall_sentiment_label'),
                            symbols=[t.get('ticker') for t in a.get('ticker_sentiment', [])]
                        )
                        for a in feed[:limit]
                    ]
                return []
        except Exception as e:
            logger.error(f"Alpha Vantage news error: {e}")
            return []
    
    async def _get_alphavantage_symbol_news(
        self,
        symbol: str,
        limit: int = 10
    ) -> List[NewsArticle]:
        """Get news for specific symbol from Alpha Vantage"""
        if not self.alphavantage_key:
            return []
        
        try:
            session = await self._get_session()
            url = self.ALPHAVANTAGE_BASE
            params = {
                'function': 'NEWS_SENTIMENT',
                'tickers': symbol.upper(),
                'apikey': self.alphavantage_key,
                'limit': limit
            }
            
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    feed = data.get('feed', [])
                    
                    return [
                        NewsArticle(
                            title=a.get('title', ''),
                            source=a.get('source', 'Unknown'),
                            url=a.get('url', ''),
                            published=datetime.strptime(
                                a.get('time_published', '')[:15],
                                '%Y%m%dT%H%M%S'
                            ).replace(tzinfo=timezone.utc) if a.get('time_published') else datetime.now(timezone.utc),
                            summary=a.get('summary', '')[:300],
                            sentiment=a.get('overall_sentiment_label'),
                            symbols=[symbol.upper()]
                        )
                        for a in feed[:limit]
                    ]
                return []
        except Exception as e:
            logger.error(f"Alpha Vantage symbol news error: {e}")
            return []
    
    def get_status(self) -> Dict[str, Any]:
        return {
            "newsapi_configured": bool(self.newsapi_key),
            "alphavantage_configured": bool(self.alphavantage_key),
            "newsapi_rate_limit": "100/day",
            "alphavantage_rate_limit": "5/min, 500/day"
        }
    
    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
