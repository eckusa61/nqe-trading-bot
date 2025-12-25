"""
IBKR Connector Module
Dual-mode: Simulated and Live Paper Trading
Uses adapter pattern for seamless switching
"""
import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Callable, Any
from enum import Enum
import random
import math

from trading_bot.config import CONFIG, TradingMode, IBKRConfig

logger = logging.getLogger(__name__)


class ConnectionState(Enum):
    """Connection states"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


@dataclass
class MarketData:
    """Real-time market data"""
    symbol: str
    timestamp: datetime
    bid: float
    ask: float
    last: float
    volume: int
    high: float
    low: float
    open: float
    close: float
    
    @property
    def mid(self) -> float:
        return (self.bid + self.ask) / 2
    
    @property
    def spread(self) -> float:
        return self.ask - self.bid
    
    @property
    def spread_pct(self) -> float:
        return self.spread / self.mid if self.mid > 0 else 0


@dataclass
class HistoricalBar:
    """Historical OHLCV bar"""
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    bar_count: int = 1
    wap: float = 0.0  # Volume weighted average price
    
    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp.isoformat(),
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "bar_count": self.bar_count,
            "wap": self.wap
        }


@dataclass
class OrderStatus:
    """Order execution status"""
    order_id: str
    symbol: str
    status: str  # "pending", "filled", "partial", "cancelled", "error"
    filled_qty: int = 0
    remaining_qty: int = 0
    avg_fill_price: float = 0.0
    commission: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class BaseIBKRConnector(ABC):
    """Abstract base class for IBKR connectors"""
    
    @abstractmethod
    async def connect(self) -> bool:
        """Establish connection"""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection"""
        pass
    
    @abstractmethod
    async def get_market_data(self, symbol: str) -> Optional[MarketData]:
        """Get real-time market data"""
        pass
    
    @abstractmethod
    async def get_historical_data(
        self, 
        symbol: str, 
        duration: str,
        bar_size: str,
        end_date: Optional[datetime] = None
    ) -> List[HistoricalBar]:
        """Get historical OHLCV data"""
        pass
    
    @abstractmethod
    async def place_order(
        self,
        symbol: str,
        quantity: int,
        order_type: str,
        side: str,
        limit_price: Optional[float] = None
    ) -> OrderStatus:
        """Place an order"""
        pass
    
    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an order"""
        pass
    
    @abstractmethod
    async def get_positions(self) -> Dict[str, int]:
        """Get current positions"""
        pass
    
    @abstractmethod
    async def get_account_summary(self) -> Dict[str, float]:
        """Get account summary"""
        pass
    
    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """Check connection status"""
        pass


class SimulatedIBKRConnector(BaseIBKRConnector):
    """
    Simulated IBKR Connector for testing
    Generates realistic market data with proper characteristics
    """
    
    def __init__(self, config: IBKRConfig = CONFIG.ibkr):
        self.config = config
        self._connected = False
        self._positions: Dict[str, int] = {}
        self._orders: Dict[str, OrderStatus] = {}
        self._order_counter = 0
        
        # Simulated price state with realistic starting prices
        self._base_prices: Dict[str, float] = {
            "SPY": 590.0,
            "QQQ": 520.0,
            "AAPL": 195.0,
            "MSFT": 430.0,
            "TSLA": 250.0,
            "NVDA": 140.0,
            "META": 580.0,
        }
        self._current_prices: Dict[str, float] = self._base_prices.copy()
        
        # Volatility by symbol (annual)
        self._volatility: Dict[str, float] = {
            "SPY": 0.15, "QQQ": 0.20, "AAPL": 0.25,
            "MSFT": 0.22, "TSLA": 0.45, "NVDA": 0.40, "META": 0.35
        }
        
        # Account state
        self._cash = 100000.0
        self._initial_cash = 100000.0
        
        # Historical data cache
        self._historical_cache: Dict[str, List[HistoricalBar]] = {}
        
        logger.info("SimulatedIBKRConnector initialized")
    
    async def connect(self) -> bool:
        """Simulate connection"""
        await asyncio.sleep(0.1)  # Simulate connection delay
        self._connected = True
        logger.info("Simulated IBKR connection established")
        return True
    
    async def disconnect(self) -> None:
        """Simulate disconnection"""
        self._connected = False
        logger.info("Simulated IBKR connection closed")
    
    @property
    def is_connected(self) -> bool:
        return self._connected
    
    def _simulate_price_move(self, symbol: str, dt_hours: float = 1/24) -> float:
        """
        Simulate realistic price movement using geometric Brownian motion
        """
        current = self._current_prices.get(symbol, 100.0)
        vol = self._volatility.get(symbol, 0.25)
        
        # Annual to hourly volatility
        hourly_vol = vol * math.sqrt(dt_hours / 252 / 6.5)
        
        # Random walk with slight mean reversion
        drift = 0.0001 * dt_hours  # Slight upward drift
        shock = random.gauss(0, hourly_vol)
        
        # Mean reversion toward base price (weak)
        base = self._base_prices.get(symbol, current)
        reversion = 0.001 * (base - current) / base * dt_hours
        
        new_price = current * math.exp(drift + shock + reversion)
        self._current_prices[symbol] = new_price
        return new_price
    
    async def get_market_data(self, symbol: str) -> Optional[MarketData]:
        """Get simulated real-time market data"""
        if not self._connected:
            return None
        
        price = self._simulate_price_move(symbol)
        vol = self._volatility.get(symbol, 0.25)
        
        # Spread proportional to volatility
        half_spread = price * (0.0001 + vol * 0.0002)
        
        # Simulate daily range
        daily_vol = vol / math.sqrt(252)
        high = price * (1 + daily_vol * random.uniform(0.3, 0.8))
        low = price * (1 - daily_vol * random.uniform(0.3, 0.8))
        
        return MarketData(
            symbol=symbol,
            timestamp=datetime.now(timezone.utc),
            bid=price - half_spread,
            ask=price + half_spread,
            last=price,
            volume=random.randint(100000, 5000000),
            high=high,
            low=low,
            open=self._base_prices.get(symbol, price),
            close=price
        )
    
    async def get_historical_data(
        self,
        symbol: str,
        duration: str = "5 Y",
        bar_size: str = "1 day",
        end_date: Optional[datetime] = None
    ) -> List[HistoricalBar]:
        """
        Generate realistic historical data
        duration format: "5 Y" for 5 years, "1 M" for 1 month, etc.
        """
        if not self._connected:
            return []
        
        # Parse duration
        parts = duration.split()
        num = int(parts[0])
        unit = parts[1].upper()
        
        if unit.startswith("Y"):
            days = num * 252  # Trading days per year
        elif unit.startswith("M"):
            days = num * 21
        elif unit.startswith("W"):
            days = num * 5
        else:
            days = num
        
        end = end_date or datetime.now(timezone.utc)
        
        # Check cache
        cache_key = f"{symbol}_{duration}_{bar_size}"
        if cache_key in self._historical_cache:
            return self._historical_cache[cache_key]
        
        bars = []
        base_price = self._base_prices.get(symbol, 100.0)
        vol = self._volatility.get(symbol, 0.25)
        daily_vol = vol / math.sqrt(252)
        
        current_price = base_price * 0.5  # Start lower, trend up
        
        for i in range(days):
            bar_date = end - timedelta(days=days - i)
            
            # Skip weekends
            if bar_date.weekday() >= 5:
                continue
            
            # Simulate daily bar
            drift = 0.0004  # Slight upward bias
            shock = random.gauss(0, daily_vol)
            
            open_price = current_price
            close_price = open_price * math.exp(drift + shock)
            
            # Intraday range
            high_price = max(open_price, close_price) * (1 + abs(random.gauss(0, daily_vol * 0.5)))
            low_price = min(open_price, close_price) * (1 - abs(random.gauss(0, daily_vol * 0.5)))
            
            # Volume (correlated with volatility)
            base_volume = 10000000 if symbol in ["SPY", "QQQ"] else 5000000
            volume = int(base_volume * (1 + abs(shock) * 10) * random.uniform(0.7, 1.3))
            
            bars.append(HistoricalBar(
                symbol=symbol,
                timestamp=bar_date.replace(hour=16, minute=0, second=0, microsecond=0),
                open=round(open_price, 2),
                high=round(high_price, 2),
                low=round(low_price, 2),
                close=round(close_price, 2),
                volume=volume,
                wap=round((high_price + low_price + close_price) / 3, 2)
            ))
            
            current_price = close_price
        
        # Update current price to match historical end
        if bars:
            self._current_prices[symbol] = bars[-1].close
        
        # Cache results
        self._historical_cache[cache_key] = bars
        
        logger.info(f"Generated {len(bars)} historical bars for {symbol}")
        return bars
    
    async def place_order(
        self,
        symbol: str,
        quantity: int,
        order_type: str,
        side: str,
        limit_price: Optional[float] = None
    ) -> OrderStatus:
        """
        Simulate order placement with realistic fills
        """
        if not self._connected:
            return OrderStatus(
                order_id="",
                symbol=symbol,
                status="error"
            )
        
        self._order_counter += 1
        order_id = f"SIM_{self._order_counter:06d}"
        
        market_data = await self.get_market_data(symbol)
        if not market_data:
            return OrderStatus(order_id=order_id, symbol=symbol, status="error")
        
        # Determine fill price with slippage
        base_slippage = CONFIG.backtest.base_slippage
        vol_slippage = self._volatility.get(symbol, 0.25) * CONFIG.backtest.volatility_slippage_multiplier / 100
        size_slippage = max(0, quantity - CONFIG.backtest.size_impact_threshold) * CONFIG.backtest.size_impact_rate
        
        total_slippage = base_slippage + vol_slippage + size_slippage
        
        if side.upper() == "BUY":
            fill_price = market_data.ask * (1 + total_slippage)
        else:
            fill_price = market_data.bid * (1 - total_slippage)
        
        # Partial fill simulation
        filled_qty = quantity
        if random.random() < CONFIG.backtest.partial_fill_probability:
            filled_qty = int(quantity * CONFIG.backtest.avg_fill_rate)
        
        # Calculate commission
        commission = max(
            CONFIG.backtest.min_commission,
            filled_qty * CONFIG.backtest.commission_per_share
        )
        
        # Update positions and cash
        if side.upper() == "BUY":
            cost = fill_price * filled_qty + commission
            if cost <= self._cash:
                self._cash -= cost
                self._positions[symbol] = self._positions.get(symbol, 0) + filled_qty
                status = "filled" if filled_qty == quantity else "partial"
            else:
                filled_qty = 0
                status = "rejected"
        else:
            proceeds = fill_price * filled_qty - commission
            current_pos = self._positions.get(symbol, 0)
            if filled_qty <= current_pos:
                self._cash += proceeds
                self._positions[symbol] = current_pos - filled_qty
                status = "filled" if filled_qty == quantity else "partial"
            else:
                filled_qty = 0
                status = "rejected"
        
        order_status = OrderStatus(
            order_id=order_id,
            symbol=symbol,
            status=status,
            filled_qty=filled_qty,
            remaining_qty=quantity - filled_qty,
            avg_fill_price=fill_price if filled_qty > 0 else 0,
            commission=commission if filled_qty > 0 else 0
        )
        
        self._orders[order_id] = order_status
        logger.info(f"Order {order_id}: {side} {filled_qty}/{quantity} {symbol} @ {fill_price:.2f}")
        
        return order_status
    
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel a pending order"""
        if order_id in self._orders:
            self._orders[order_id].status = "cancelled"
            return True
        return False
    
    async def get_positions(self) -> Dict[str, int]:
        """Get current positions"""
        return {k: v for k, v in self._positions.items() if v != 0}
    
    async def get_account_summary(self) -> Dict[str, float]:
        """Get account summary"""
        # Calculate portfolio value
        portfolio_value = self._cash
        for symbol, qty in self._positions.items():
            if qty != 0:
                market_data = await self.get_market_data(symbol)
                if market_data:
                    portfolio_value += market_data.last * qty
        
        return {
            "cash": self._cash,
            "portfolio_value": portfolio_value,
            "initial_capital": self._initial_cash,
            "pnl": portfolio_value - self._initial_cash,
            "pnl_pct": (portfolio_value - self._initial_cash) / self._initial_cash * 100
        }


class LiveIBKRConnector(BaseIBKRConnector):
    """
    Live IBKR Connector using ib_insync library
    For actual paper/live trading with TWS or IB Gateway
    """
    
    def __init__(self, config: IBKRConfig = CONFIG.ibkr):
        self.config = config
        self._connected = False
        self._ib = None  # Will be ib_insync.IB instance
        self._positions: Dict[str, int] = {}
        logger.info("LiveIBKRConnector initialized (requires ib_insync)")
    
    async def connect(self) -> bool:
        """
        Connect to TWS or IB Gateway
        Requires ib_insync library and running TWS/Gateway
        """
        try:
            # Dynamic import to avoid dependency when using simulated mode
            from ib_insync import IB
            
            self._ib = IB()
            
            # Determine port based on config
            port = self.config.paper_port
            if CONFIG.mode == TradingMode.LIVE_REAL:
                port = self.config.live_port
            
            await self._ib.connectAsync(
                host=self.config.host,
                port=port,
                clientId=self.config.client_id,
                timeout=self.config.timeout
            )
            
            self._connected = self._ib.isConnected()
            if self._connected:
                logger.info(f"Connected to IBKR on port {port}")
            return self._connected
            
        except ImportError:
            logger.error("ib_insync not installed. Run: pip install ib_insync")
            return False
        except Exception as e:
            logger.error(f"Failed to connect to IBKR: {e}")
            return False
    
    async def disconnect(self) -> None:
        """Disconnect from IBKR"""
        if self._ib:
            self._ib.disconnect()
            self._connected = False
            logger.info("Disconnected from IBKR")
    
    @property
    def is_connected(self) -> bool:
        return self._connected and self._ib and self._ib.isConnected()
    
    async def get_market_data(self, symbol: str) -> Optional[MarketData]:
        """Get real-time market data from IBKR"""
        if not self.is_connected:
            return None
        
        try:
            from ib_insync import Stock
            
            contract = Stock(symbol, "SMART", "USD")
            ticker = self._ib.reqMktData(contract)
            
            await asyncio.sleep(0.5)  # Wait for data
            
            return MarketData(
                symbol=symbol,
                timestamp=datetime.now(timezone.utc),
                bid=ticker.bid or 0,
                ask=ticker.ask or 0,
                last=ticker.last or 0,
                volume=ticker.volume or 0,
                high=ticker.high or 0,
                low=ticker.low or 0,
                open=ticker.open or 0,
                close=ticker.close or 0
            )
        except Exception as e:
            logger.error(f"Error getting market data for {symbol}: {e}")
            return None
    
    async def get_historical_data(
        self,
        symbol: str,
        duration: str = "5 Y",
        bar_size: str = "1 day",
        end_date: Optional[datetime] = None
    ) -> List[HistoricalBar]:
        """Get historical data from IBKR"""
        if not self.is_connected:
            return []
        
        try:
            from ib_insync import Stock
            
            contract = Stock(symbol, "SMART", "USD")
            end = end_date or ""
            
            bars = await self._ib.reqHistoricalDataAsync(
                contract,
                endDateTime=end,
                durationStr=duration,
                barSizeSetting=bar_size,
                whatToShow="TRADES",
                useRTH=CONFIG.data.use_rth
            )
            
            return [
                HistoricalBar(
                    symbol=symbol,
                    timestamp=bar.date,
                    open=bar.open,
                    high=bar.high,
                    low=bar.low,
                    close=bar.close,
                    volume=bar.volume,
                    bar_count=bar.barCount,
                    wap=bar.average
                )
                for bar in bars
            ]
        except Exception as e:
            logger.error(f"Error getting historical data for {symbol}: {e}")
            return []
    
    async def place_order(
        self,
        symbol: str,
        quantity: int,
        order_type: str,
        side: str,
        limit_price: Optional[float] = None
    ) -> OrderStatus:
        """Place order through IBKR"""
        if not self.is_connected:
            return OrderStatus(order_id="", symbol=symbol, status="error")
        
        try:
            from ib_insync import Stock, MarketOrder, LimitOrder
            
            contract = Stock(symbol, "SMART", "USD")
            
            if order_type.upper() == "MKT":
                order = MarketOrder(side, quantity)
            else:
                order = LimitOrder(side, quantity, limit_price)
            
            trade = self._ib.placeOrder(contract, order)
            
            return OrderStatus(
                order_id=str(trade.order.orderId),
                symbol=symbol,
                status="pending",
                remaining_qty=quantity
            )
        except Exception as e:
            logger.error(f"Error placing order: {e}")
            return OrderStatus(order_id="", symbol=symbol, status="error")
    
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel order through IBKR"""
        # Implementation would use self._ib.cancelOrder()
        return False
    
    async def get_positions(self) -> Dict[str, int]:
        """Get positions from IBKR"""
        if not self.is_connected:
            return {}
        
        positions = self._ib.positions()
        return {
            pos.contract.symbol: int(pos.position)
            for pos in positions
        }
    
    async def get_account_summary(self) -> Dict[str, float]:
        """Get account summary from IBKR"""
        if not self.is_connected:
            return {}
        
        values = self._ib.accountSummary()
        return {v.tag: float(v.value) for v in values if v.value.replace('.', '').isdigit()}


class IBKRConnector:
    """
    Factory class that returns appropriate connector based on mode
    """
    
    @staticmethod
    def create(mode: Optional[TradingMode] = None) -> BaseIBKRConnector:
        """
        Create appropriate connector based on trading mode
        """
        mode = mode or CONFIG.mode
        
        if mode == TradingMode.SIMULATED:
            logger.info("Creating SimulatedIBKRConnector")
            return SimulatedIBKRConnector()
        else:
            logger.info(f"Creating LiveIBKRConnector for mode: {mode}")
            return LiveIBKRConnector()
