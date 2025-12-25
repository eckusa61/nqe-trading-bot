"""
Yahoo Finance Feed - Free market data

Provides:
- Real-time quotes
- Historical data
- News headlines
- Analyst recommendations
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class YahooQuote:
    symbol: str
    price: float
    change: float
    change_percent: float
    volume: int
    market_cap: Optional[float]
    pe_ratio: Optional[float]
    fifty_two_week_high: float
    fifty_two_week_low: float
    timestamp: datetime


@dataclass
class YahooNews:
    title: str
    link: str
    publisher: str
    published: datetime
    summary: str = ""


class YahooFinanceFeed:
    """
    Yahoo Finance data using yfinance library
    Completely free, no API key needed
    """
    
    def __init__(self):
        self._yf = None
        self._init_yfinance()
        logger.info("Yahoo Finance Feed initialized")
    
    def _init_yfinance(self):
        try:
            import yfinance as yf
            self._yf = yf
        except ImportError:
            logger.warning("yfinance not installed, installing...")
            import subprocess
            subprocess.run(['pip', 'install', 'yfinance'], check=True)
            import yfinance as yf
            self._yf = yf
    
    def get_quote(self, symbol: str) -> Optional[YahooQuote]:
        """Get real-time quote for a symbol"""
        try:
            ticker = self._yf.Ticker(symbol)
            info = ticker.info
            
            return YahooQuote(
                symbol=symbol.upper(),
                price=info.get('currentPrice') or info.get('regularMarketPrice', 0),
                change=info.get('regularMarketChange', 0),
                change_percent=info.get('regularMarketChangePercent', 0),
                volume=info.get('regularMarketVolume', 0),
                market_cap=info.get('marketCap'),
                pe_ratio=info.get('trailingPE'),
                fifty_two_week_high=info.get('fiftyTwoWeekHigh', 0),
                fifty_two_week_low=info.get('fiftyTwoWeekLow', 0),
                timestamp=datetime.now(timezone.utc)
            )
        except Exception as e:
            logger.error(f"Yahoo quote error for {symbol}: {e}")
            return None
    
    def get_quotes_batch(self, symbols: List[str]) -> Dict[str, YahooQuote]:
        """Get quotes for multiple symbols"""
        quotes = {}
        for symbol in symbols:
            quote = self.get_quote(symbol)
            if quote:
                quotes[symbol] = quote
        return quotes
    
    def get_news(self, symbol: str, limit: int = 10) -> List[YahooNews]:
        """Get recent news for a symbol"""
        try:
            ticker = self._yf.Ticker(symbol)
            news = ticker.news[:limit] if ticker.news else []
            
            return [
                YahooNews(
                    title=n.get('title', ''),
                    link=n.get('link', ''),
                    publisher=n.get('publisher', ''),
                    published=datetime.fromtimestamp(
                        n.get('providerPublishTime', 0),
                        tz=timezone.utc
                    ),
                    summary=n.get('summary', '')[:300]
                )
                for n in news
            ]
        except Exception as e:
            logger.error(f"Yahoo news error for {symbol}: {e}")
            return []
    
    def get_recommendations(self, symbol: str) -> Dict[str, Any]:
        """Get analyst recommendations"""
        try:
            ticker = self._yf.Ticker(symbol)
            recs = ticker.recommendations
            
            if recs is None or recs.empty:
                return {'symbol': symbol, 'recommendations': []}
            
            recent = recs.tail(10).to_dict('records')
            return {
                'symbol': symbol,
                'recommendations': recent
            }
        except Exception as e:
            logger.error(f"Yahoo recommendations error: {e}")
            return {'symbol': symbol, 'recommendations': []}
    
    def get_historical(self, symbol: str, period: str = '1mo') -> List[Dict]:
        """Get historical data"""
        try:
            ticker = self._yf.Ticker(symbol)
            hist = ticker.history(period=period)
            
            return [
                {
                    'date': idx.isoformat(),
                    'open': row['Open'],
                    'high': row['High'],
                    'low': row['Low'],
                    'close': row['Close'],
                    'volume': row['Volume']
                }
                for idx, row in hist.iterrows()
            ]
        except Exception as e:
            logger.error(f"Yahoo historical error: {e}")
            return []
    
    def get_market_summary(self) -> Dict[str, Any]:
        """Get major index summary"""
        indices = {
            'SPY': 'S&P 500',
            'QQQ': 'NASDAQ',
            'DIA': 'Dow Jones',
            'IWM': 'Russell 2000',
            'VIX': 'Volatility'
        }
        
        summary = {}
        for symbol, name in indices.items():
            quote = self.get_quote(symbol)
            if quote:
                summary[name] = {
                    'symbol': symbol,
                    'price': quote.price,
                    'change_percent': quote.change_percent
                }
        
        return summary
    
    def get_status(self) -> Dict[str, Any]:
        return {
            "configured": True,
            "library": "yfinance",
            "rate_limit": "None (be reasonable)"
        }
