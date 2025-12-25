"""
StockTwits Feed - Free social sentiment for stocks

No API key required for basic access!
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import aiohttp

logger = logging.getLogger(__name__)


@dataclass 
class StockTwit:
    id: int
    body: str
    symbol: str
    sentiment: Optional[str]  # "Bullish", "Bearish", None
    created_at: datetime
    user: str
    likes: int = 0


class StockTwitsFeed:
    """
    StockTwits API - Free tier, no auth required
    Rate limit: 200 requests per hour
    """
    
    BASE_URL = "https://api.stocktwits.com/api/2"
    
    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None
        self._request_count = 0
        logger.info("StockTwits Feed initialized (no API key required)")
    
    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session
    
    async def get_symbol_stream(
        self,
        symbol: str,
        limit: int = 30
    ) -> List[StockTwit]:
        """
        Get recent twits for a symbol
        """
        try:
            session = await self._get_session()
            url = f"{self.BASE_URL}/streams/symbol/{symbol.upper()}.json"
            
            params = {'limit': min(limit, 30)}
            
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    twits = []
                    
                    messages = data.get('messages', [])
                    for msg in messages:
                        sentiment = None
                        if msg.get('entities', {}).get('sentiment'):
                            sentiment = msg['entities']['sentiment'].get('basic')
                        
                        twit = StockTwit(
                            id=msg.get('id', 0),
                            body=msg.get('body', ''),
                            symbol=symbol.upper(),
                            sentiment=sentiment,
                            created_at=datetime.fromisoformat(
                                msg.get('created_at', '').replace('Z', '+00:00')
                            ) if msg.get('created_at') else datetime.now(timezone.utc),
                            user=msg.get('user', {}).get('username', 'unknown'),
                            likes=msg.get('likes', {}).get('total', 0)
                        )
                        twits.append(twit)
                    
                    self._request_count += 1
                    return twits
                elif response.status == 429:
                    logger.warning("StockTwits rate limit hit")
                    return []
                else:
                    logger.error(f"StockTwits error: {response.status}")
                    return []
        except Exception as e:
            logger.error(f"StockTwits error: {e}")
            return []
    
    async def get_trending(self) -> List[Dict[str, Any]]:
        """
        Get trending symbols on StockTwits
        """
        try:
            session = await self._get_session()
            url = f"{self.BASE_URL}/trending/symbols.json"
            
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    symbols = data.get('symbols', [])
                    
                    return [
                        {
                            'symbol': s.get('symbol'),
                            'title': s.get('title'),
                            'watchlist_count': s.get('watchlist_count', 0)
                        }
                        for s in symbols[:20]
                    ]
                return []
        except Exception as e:
            logger.error(f"StockTwits trending error: {e}")
            return []
    
    async def get_sentiment_score(self, symbol: str) -> Dict[str, Any]:
        """
        Calculate sentiment score from recent twits
        Returns score from -1 (bearish) to 1 (bullish)
        """
        twits = await self.get_symbol_stream(symbol, limit=30)
        
        if not twits:
            return {
                'symbol': symbol,
                'score': 0.0,
                'confidence': 0.0,
                'bullish_count': 0,
                'bearish_count': 0,
                'neutral_count': 0,
                'total': 0
            }
        
        bullish = sum(1 for t in twits if t.sentiment == 'Bullish')
        bearish = sum(1 for t in twits if t.sentiment == 'Bearish')
        neutral = len(twits) - bullish - bearish
        
        # Calculate score
        if bullish + bearish > 0:
            score = (bullish - bearish) / (bullish + bearish)
        else:
            score = 0.0
        
        # Confidence based on how many have sentiment
        labeled = bullish + bearish
        confidence = labeled / len(twits) if twits else 0
        
        return {
            'symbol': symbol,
            'score': round(score, 3),
            'confidence': round(confidence, 3),
            'bullish_count': bullish,
            'bearish_count': bearish,
            'neutral_count': neutral,
            'total': len(twits)
        }
    
    def get_status(self) -> Dict[str, Any]:
        return {
            "configured": True,
            "requests_made": self._request_count,
            "rate_limit": "200/hour"
        }
    
    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
