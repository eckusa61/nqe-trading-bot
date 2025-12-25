"""
Finviz Feed - Free stock screener and news

Provides:
- Stock screener data
- News headlines
- Technical signals
- Insider trading
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import aiohttp
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


@dataclass
class FinvizStock:
    symbol: str
    company: str
    sector: str
    industry: str
    price: float
    change: float
    volume: int
    market_cap: str
    pe: Optional[float]
    signal: str  # e.g., "Bullish", "Oversold", etc.


@dataclass
class FinvizNews:
    title: str
    link: str
    source: str
    time: str


class FinvizFeed:
    """
    Finviz data via web scraping
    Free, no API key needed
    """
    
    BASE_URL = "https://finviz.com"
    
    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        logger.info("Finviz Feed initialized")
    
    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(headers=self.headers)
        return self._session
    
    async def get_stock_news(self, symbol: str) -> List[FinvizNews]:
        """Get news for a specific stock"""
        try:
            session = await self._get_session()
            url = f"{self.BASE_URL}/quote.ashx?t={symbol.upper()}"
            
            async with session.get(url) as response:
                if response.status == 200:
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    news = []
                    news_table = soup.find('table', {'id': 'news-table'})
                    
                    if news_table:
                        rows = news_table.find_all('tr')[:10]
                        for row in rows:
                            cells = row.find_all('td')
                            if len(cells) >= 2:
                                time_cell = cells[0].text.strip()
                                link = cells[1].find('a')
                                if link:
                                    news.append(FinvizNews(
                                        title=link.text.strip(),
                                        link=link.get('href', ''),
                                        source=cells[1].find('span').text if cells[1].find('span') else '',
                                        time=time_cell
                                    ))
                    
                    return news
                return []
        except Exception as e:
            logger.error(f"Finviz news error: {e}")
            return []
    
    async def get_screener_results(
        self,
        filters: str = "ta_topgainers"
    ) -> List[Dict[str, Any]]:
        """
        Get stocks from Finviz screener
        
        Common filters:
        - ta_topgainers: Top gainers
        - ta_toplosers: Top losers
        - ta_mostactive: Most active
        - ta_overbought: Overbought
        - ta_oversold: Oversold
        - ta_unusualvolume: Unusual volume
        """
        try:
            session = await self._get_session()
            url = f"{self.BASE_URL}/screener.ashx?v=111&s={filters}"
            
            async with session.get(url) as response:
                if response.status == 200:
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    results = []
                    table = soup.find('table', {'class': 'table-light'})
                    
                    if table:
                        rows = table.find_all('tr')[1:21]  # Skip header, get top 20
                        for row in rows:
                            cells = row.find_all('td')
                            if len(cells) >= 10:
                                results.append({
                                    'symbol': cells[1].text.strip(),
                                    'company': cells[2].text.strip(),
                                    'sector': cells[3].text.strip(),
                                    'industry': cells[4].text.strip(),
                                    'market_cap': cells[6].text.strip(),
                                    'price': cells[8].text.strip(),
                                    'change': cells[9].text.strip(),
                                    'volume': cells[10].text.strip() if len(cells) > 10 else ''
                                })
                    
                    return results
                return []
        except Exception as e:
            logger.error(f"Finviz screener error: {e}")
            return []
    
    async def get_top_gainers(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get top gaining stocks"""
        results = await self.get_screener_results("ta_topgainers")
        return results[:limit]
    
    async def get_top_losers(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get top losing stocks"""
        results = await self.get_screener_results("ta_toplosers")
        return results[:limit]
    
    async def get_most_active(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get most active stocks"""
        results = await self.get_screener_results("ta_mostactive")
        return results[:limit]
    
    async def get_oversold(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get oversold stocks (potential buy signals)"""
        results = await self.get_screener_results("ta_oversold")
        return results[:limit]
    
    async def get_overbought(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get overbought stocks (potential sell signals)"""
        results = await self.get_screener_results("ta_overbought")
        return results[:limit]
    
    async def get_unusual_volume(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get stocks with unusual volume"""
        results = await self.get_screener_results("ta_unusualvolume")
        return results[:limit]
    
    def get_status(self) -> Dict[str, Any]:
        return {
            "configured": True,
            "method": "web_scraping",
            "rate_limit": "Be respectful (1 req/sec)"
        }
    
    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
