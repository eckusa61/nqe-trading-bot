"""
Crypto Feed - Free cryptocurrency data

Sources:
- CoinGecko (free, no API key)
- Binance public API
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import aiohttp

logger = logging.getLogger(__name__)


@dataclass
class CryptoQuote:
    symbol: str
    name: str
    price_usd: float
    change_24h: float
    change_7d: float
    volume_24h: float
    market_cap: float
    rank: int
    timestamp: datetime


class CryptoFeed:
    """
    Cryptocurrency data from CoinGecko and Binance
    Completely free, no API key needed
    """
    
    COINGECKO_BASE = "https://api.coingecko.com/api/v3"
    BINANCE_BASE = "https://api.binance.com/api/v3"
    
    # Map common symbols to CoinGecko IDs
    SYMBOL_MAP = {
        'BTC': 'bitcoin',
        'ETH': 'ethereum',
        'BNB': 'binancecoin',
        'SOL': 'solana',
        'XRP': 'ripple',
        'ADA': 'cardano',
        'DOGE': 'dogecoin',
        'DOT': 'polkadot',
        'MATIC': 'matic-network',
        'LINK': 'chainlink',
        'AVAX': 'avalanche-2',
        'UNI': 'uniswap',
        'ATOM': 'cosmos',
        'LTC': 'litecoin',
        'FIL': 'filecoin'
    }
    
    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None
        logger.info("Crypto Feed initialized (CoinGecko + Binance)")
    
    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session
    
    async def get_price(self, symbol: str) -> Optional[CryptoQuote]:
        """Get current price for a crypto"""
        coin_id = self.SYMBOL_MAP.get(symbol.upper())
        if not coin_id:
            coin_id = symbol.lower()
        
        try:
            session = await self._get_session()
            url = f"{self.COINGECKO_BASE}/coins/{coin_id}"
            params = {
                'localization': 'false',
                'tickers': 'false',
                'community_data': 'false',
                'developer_data': 'false'
            }
            
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    market = data.get('market_data', {})
                    
                    return CryptoQuote(
                        symbol=symbol.upper(),
                        name=data.get('name', ''),
                        price_usd=market.get('current_price', {}).get('usd', 0),
                        change_24h=market.get('price_change_percentage_24h', 0),
                        change_7d=market.get('price_change_percentage_7d', 0),
                        volume_24h=market.get('total_volume', {}).get('usd', 0),
                        market_cap=market.get('market_cap', {}).get('usd', 0),
                        rank=data.get('market_cap_rank', 0),
                        timestamp=datetime.now(timezone.utc)
                    )
                elif response.status == 429:
                    logger.warning("CoinGecko rate limit hit")
                    return None
                else:
                    return None
        except Exception as e:
            logger.error(f"Crypto price error: {e}")
            return None
    
    async def get_top_cryptos(self, limit: int = 20) -> List[CryptoQuote]:
        """Get top cryptocurrencies by market cap"""
        try:
            session = await self._get_session()
            url = f"{self.COINGECKO_BASE}/coins/markets"
            params = {
                'vs_currency': 'usd',
                'order': 'market_cap_desc',
                'per_page': limit,
                'page': 1,
                'sparkline': 'false'
            }
            
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    return [
                        CryptoQuote(
                            symbol=coin.get('symbol', '').upper(),
                            name=coin.get('name', ''),
                            price_usd=coin.get('current_price', 0),
                            change_24h=coin.get('price_change_percentage_24h', 0),
                            change_7d=coin.get('price_change_percentage_7d_in_currency', 0) or 0,
                            volume_24h=coin.get('total_volume', 0),
                            market_cap=coin.get('market_cap', 0),
                            rank=coin.get('market_cap_rank', 0),
                            timestamp=datetime.now(timezone.utc)
                        )
                        for coin in data
                    ]
                return []
        except Exception as e:
            logger.error(f"Top cryptos error: {e}")
            return []
    
    async def get_binance_price(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get price from Binance (faster, real-time)"""
        try:
            session = await self._get_session()
            pair = f"{symbol.upper()}USDT"
            url = f"{self.BINANCE_BASE}/ticker/24hr"
            params = {'symbol': pair}
            
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return {
                        'symbol': symbol.upper(),
                        'price': float(data.get('lastPrice', 0)),
                        'change_24h': float(data.get('priceChangePercent', 0)),
                        'volume_24h': float(data.get('volume', 0)),
                        'high_24h': float(data.get('highPrice', 0)),
                        'low_24h': float(data.get('lowPrice', 0))
                    }
                return None
        except Exception as e:
            logger.error(f"Binance price error: {e}")
            return None
    
    async def get_fear_greed_index(self) -> Dict[str, Any]:
        """Get crypto fear & greed index"""
        try:
            session = await self._get_session()
            url = "https://api.alternative.me/fng/"
            
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    fng = data.get('data', [{}])[0]
                    return {
                        'value': int(fng.get('value', 50)),
                        'classification': fng.get('value_classification', 'Neutral'),
                        'timestamp': fng.get('timestamp')
                    }
                return {'value': 50, 'classification': 'Neutral'}
        except Exception as e:
            logger.error(f"Fear & Greed error: {e}")
            return {'value': 50, 'classification': 'Neutral'}
    
    def get_status(self) -> Dict[str, Any]:
        return {
            "configured": True,
            "sources": ["CoinGecko", "Binance"],
            "tracked_cryptos": list(self.SYMBOL_MAP.keys()),
            "rate_limit": "10-50/min (CoinGecko)"
        }
    
    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
