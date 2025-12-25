"""
Forex Feed - Free currency data

Sources:
- Exchange Rates API (free tier)
- Open Exchange Rates (free tier)
"""
import os
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import aiohttp

logger = logging.getLogger(__name__)


@dataclass
class ForexQuote:
    pair: str
    rate: float
    change_24h: float
    high_24h: float
    low_24h: float
    timestamp: datetime


class ForexFeed:
    """
    Forex data from free APIs
    """
    
    # Major currency pairs
    MAJOR_PAIRS = [
        'EUR/USD', 'GBP/USD', 'USD/JPY', 'USD/CHF',
        'AUD/USD', 'USD/CAD', 'NZD/USD'
    ]
    
    CROSS_PAIRS = [
        'EUR/GBP', 'EUR/JPY', 'GBP/JPY', 'EUR/CHF',
        'AUD/JPY', 'CAD/JPY'
    ]
    
    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None
        self._cache: Dict[str, ForexQuote] = {}
        self._last_update: Optional[datetime] = None
        logger.info("Forex Feed initialized")
    
    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session
    
    async def get_rate(self, base: str, quote: str) -> Optional[float]:
        """Get exchange rate for a currency pair"""
        try:
            session = await self._get_session()
            # Using free Exchange Rates API
            url = f"https://api.exchangerate-api.com/v4/latest/{base.upper()}"
            
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    rates = data.get('rates', {})
                    return rates.get(quote.upper())
                return None
        except Exception as e:
            logger.error(f"Forex rate error: {e}")
            return None
    
    async def get_all_major_rates(self) -> Dict[str, float]:
        """Get all major forex pairs"""
        try:
            session = await self._get_session()
            # Get USD base rates
            url = "https://api.exchangerate-api.com/v4/latest/USD"
            
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    rates = data.get('rates', {})
                    
                    result = {}
                    for pair in self.MAJOR_PAIRS:
                        base, quote = pair.split('/')
                        if base == 'USD':
                            result[pair] = rates.get(quote, 0)
                        else:
                            base_rate = rates.get(base, 0)
                            if base_rate > 0:
                                result[pair] = 1 / base_rate
                    
                    self._last_update = datetime.now(timezone.utc)
                    return result
                return {}
        except Exception as e:
            logger.error(f"Forex major rates error: {e}")
            return {}
    
    async def get_market_summary(self) -> Dict[str, Any]:
        """Get forex market summary"""
        rates = await self.get_all_major_rates()
        
        return {
            "major_pairs": rates,
            "last_update": self._last_update.isoformat() if self._last_update else None,
            "dxy_estimate": self._calculate_dxy_estimate(rates)
        }
    
    def _calculate_dxy_estimate(self, rates: Dict[str, float]) -> float:
        """Estimate DXY (Dollar Index) from major pairs"""
        # Simplified DXY calculation
        # Real DXY = 50.14348112 × EUR^(-0.576) × JPY^(0.136) × GBP^(-0.119) × ...
        try:
            eur = rates.get('EUR/USD', 1.0)
            jpy = rates.get('USD/JPY', 100) / 100
            gbp = rates.get('GBP/USD', 1.0)
            cad = rates.get('USD/CAD', 1.0)
            
            # Simplified estimate
            dxy = 50 * (1/eur)**0.576 * jpy**0.136 * (1/gbp)**0.119 * cad**0.091
            return round(dxy, 2)
        except:
            return 100.0
    
    def get_status(self) -> Dict[str, Any]:
        return {
            "configured": True,
            "source": "ExchangeRate-API",
            "major_pairs": self.MAJOR_PAIRS,
            "cross_pairs": self.CROSS_PAIRS,
            "last_update": self._last_update.isoformat() if self._last_update else None,
            "rate_limit": "1500/month (free)"
        }
    
    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
