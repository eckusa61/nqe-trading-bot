"""
News Aggregator - Real-time news from multiple sources
"""
import logging
import asyncio
import aiohttp
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
from enum import Enum
import re

logger = logging.getLogger(__name__)


class NewsSentiment(Enum):
    VERY_BULLISH = "very_bullish"
    BULLISH = "bullish"
    NEUTRAL = "neutral"
    BEARISH = "bearish"
    VERY_BEARISH = "very_bearish"


class NewsSource(Enum):
    YAHOO = "yahoo"
    FINVIZ = "finviz"
    BENZINGA = "benzinga"
    REUTERS = "reuters"
    BLOOMBERG = "bloomberg"
    CNBC = "cnbc"
    TWITTER = "twitter"


@dataclass
class NewsItem:
    title: str
    source: NewsSource
    url: str
    published_at: datetime
    symbols: List[str] = field(default_factory=list)
    sentiment: NewsSentiment = NewsSentiment.NEUTRAL
    sentiment_score: float = 0.0
    summary: str = ""
    category: str = "general"
    is_breaking: bool = False
    
    def to_dict(self) -> Dict:
        return {
            "title": self.title,
            "source": self.source.value,
            "url": self.url,
            "published_at": self.published_at.isoformat(),
            "symbols": self.symbols,
            "sentiment": self.sentiment.value,
            "sentiment_score": round(self.sentiment_score, 2),
            "summary": self.summary,
            "category": self.category,
            "is_breaking": self.is_breaking,
            "age_minutes": int((datetime.now(timezone.utc) - self.published_at).total_seconds() / 60)
        }


class NewsAggregator:
    """
    Aggregates news from multiple sources
    """
    
    def __init__(self):
        self.news_cache: List[NewsItem] = []
        self.symbol_news: Dict[str, List[NewsItem]] = {}
        self.last_update: Optional[datetime] = None
        
        # Sentiment keywords
        self.bullish_keywords = [
            'surge', 'soar', 'jump', 'rally', 'gain', 'rise', 'up', 'bull',
            'beat', 'exceed', 'strong', 'growth', 'profit', 'upgrade',
            'buy', 'outperform', 'record high', 'breakout', 'positive'
        ]
        self.bearish_keywords = [
            'drop', 'fall', 'decline', 'crash', 'plunge', 'sink', 'down',
            'miss', 'weak', 'loss', 'downgrade', 'sell', 'underperform',
            'layoff', 'cut', 'concern', 'risk', 'warning', 'negative'
        ]
        
        logger.info("News Aggregator initialized")
    
    def analyze_sentiment(self, text: str) -> tuple:
        """Analyze sentiment of text"""
        text_lower = text.lower()
        
        bullish_count = sum(1 for kw in self.bullish_keywords if kw in text_lower)
        bearish_count = sum(1 for kw in self.bearish_keywords if kw in text_lower)
        
        score = (bullish_count - bearish_count) / max(bullish_count + bearish_count, 1)
        
        if score > 0.5:
            sentiment = NewsSentiment.VERY_BULLISH
        elif score > 0.2:
            sentiment = NewsSentiment.BULLISH
        elif score < -0.5:
            sentiment = NewsSentiment.VERY_BEARISH
        elif score < -0.2:
            sentiment = NewsSentiment.BEARISH
        else:
            sentiment = NewsSentiment.NEUTRAL
        
        return sentiment, score
    
    def extract_symbols(self, text: str) -> List[str]:
        """Extract stock symbols from text"""
        # Common symbols
        known_symbols = [
            'SPY', 'QQQ', 'AAPL', 'MSFT', 'GOOGL', 'GOOG', 'AMZN', 'META',
            'TSLA', 'NVDA', 'AMD', 'INTC', 'JPM', 'BAC', 'GS', 'V', 'MA',
            'DIS', 'NFLX', 'CRM', 'ORCL', 'IBM', 'BA', 'CAT', 'XOM', 'CVX'
        ]
        
        found = []
        text_upper = text.upper()
        for symbol in known_symbols:
            if symbol in text_upper or f"${symbol}" in text_upper:
                found.append(symbol)
        
        # Also find $SYMBOL patterns
        pattern = r'\$([A-Z]{1,5})'
        matches = re.findall(pattern, text.upper())
        found.extend([m for m in matches if m not in found])
        
        return found[:5]  # Limit to 5 symbols
    
    async def fetch_simulated_news(self) -> List[NewsItem]:
        """Generate simulated news for demo"""
        now = datetime.now(timezone.utc)
        
        simulated_news = [
            {
                "title": "Fed signals potential rate pause as inflation cools",
                "source": NewsSource.REUTERS,
                "category": "macro",
                "minutes_ago": 5,
                "is_breaking": True
            },
            {
                "title": "NVDA beats earnings expectations, guidance strong",
                "source": NewsSource.YAHOO,
                "category": "earnings",
                "minutes_ago": 15
            },
            {
                "title": "Tech stocks rally on AI optimism",
                "source": NewsSource.CNBC,
                "category": "sector",
                "minutes_ago": 30
            },
            {
                "title": "AAPL announces new product launch event",
                "source": NewsSource.FINVIZ,
                "category": "corporate",
                "minutes_ago": 45
            },
            {
                "title": "Oil prices drop on demand concerns",
                "source": NewsSource.BLOOMBERG,
                "category": "commodities",
                "minutes_ago": 60
            },
            {
                "title": "TSLA deliveries exceed analyst estimates",
                "source": NewsSource.YAHOO,
                "category": "earnings",
                "minutes_ago": 90
            },
            {
                "title": "Market volatility expected ahead of jobs report",
                "source": NewsSource.CNBC,
                "category": "macro",
                "minutes_ago": 120
            },
            {
                "title": "Goldman upgrades META to buy rating",
                "source": NewsSource.BENZINGA,
                "category": "analyst",
                "minutes_ago": 150
            },
            {
                "title": "SPY hits new all-time high",
                "source": NewsSource.FINVIZ,
                "category": "market",
                "minutes_ago": 180
            },
            {
                "title": "Crypto markets surge as Bitcoin breaks $100K",
                "source": NewsSource.REUTERS,
                "category": "crypto",
                "minutes_ago": 200
            }
        ]
        
        news_items = []
        for item in simulated_news:
            sentiment, score = self.analyze_sentiment(item["title"])
            symbols = self.extract_symbols(item["title"])
            
            news_item = NewsItem(
                title=item["title"],
                source=item["source"],
                url=f"https://example.com/news/{hash(item['title']) % 10000}",
                published_at=now - timedelta(minutes=item["minutes_ago"]),
                symbols=symbols,
                sentiment=sentiment,
                sentiment_score=score,
                category=item["category"],
                is_breaking=item.get("is_breaking", False)
            )
            news_items.append(news_item)
        
        return news_items
    
    async def update_news(self):
        """Update news from all sources"""
        try:
            news_items = await self.fetch_simulated_news()
            
            # Update cache
            self.news_cache = news_items
            self.last_update = datetime.now(timezone.utc)
            
            # Index by symbol
            self.symbol_news.clear()
            for item in news_items:
                for symbol in item.symbols:
                    if symbol not in self.symbol_news:
                        self.symbol_news[symbol] = []
                    self.symbol_news[symbol].append(item)
            
            logger.info(f"Updated news: {len(news_items)} items")
            
        except Exception as e:
            logger.error(f"Error updating news: {e}")
    
    def get_latest_news(self, limit: int = 20) -> List[Dict]:
        """Get latest news"""
        sorted_news = sorted(self.news_cache, key=lambda x: x.published_at, reverse=True)
        return [n.to_dict() for n in sorted_news[:limit]]
    
    def get_breaking_news(self) -> List[Dict]:
        """Get breaking news only"""
        breaking = [n for n in self.news_cache if n.is_breaking]
        return [n.to_dict() for n in breaking]
    
    def get_news_by_symbol(self, symbol: str, limit: int = 10) -> List[Dict]:
        """Get news for specific symbol"""
        if symbol not in self.symbol_news:
            return []
        news = sorted(self.symbol_news[symbol], key=lambda x: x.published_at, reverse=True)
        return [n.to_dict() for n in news[:limit]]
    
    def get_news_by_category(self, category: str, limit: int = 10) -> List[Dict]:
        """Get news by category"""
        filtered = [n for n in self.news_cache if n.category == category]
        sorted_news = sorted(filtered, key=lambda x: x.published_at, reverse=True)
        return [n.to_dict() for n in sorted_news[:limit]]
    
    def get_sentiment_summary(self) -> Dict:
        """Get overall sentiment summary"""
        if not self.news_cache:
            return {"sentiment": "neutral", "score": 0, "news_count": 0}
        
        avg_score = sum(n.sentiment_score for n in self.news_cache) / len(self.news_cache)
        
        bullish_count = sum(1 for n in self.news_cache if n.sentiment in [NewsSentiment.BULLISH, NewsSentiment.VERY_BULLISH])
        bearish_count = sum(1 for n in self.news_cache if n.sentiment in [NewsSentiment.BEARISH, NewsSentiment.VERY_BEARISH])
        
        if avg_score > 0.3:
            overall = "bullish"
        elif avg_score < -0.3:
            overall = "bearish"
        else:
            overall = "neutral"
        
        return {
            "sentiment": overall,
            "score": round(avg_score, 2),
            "news_count": len(self.news_cache),
            "bullish_count": bullish_count,
            "bearish_count": bearish_count,
            "neutral_count": len(self.news_cache) - bullish_count - bearish_count,
            "last_update": self.last_update.isoformat() if self.last_update else None
        }
