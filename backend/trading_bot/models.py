"""
Pydantic Models for API endpoints
"""
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from datetime import datetime
from enum import Enum


class TradingModeEnum(str, Enum):
    SIMULATED = "simulated"
    LIVE_PAPER = "live_paper"


class MarketRegimeEnum(str, Enum):
    BULL_QUIET = "bull_quiet"
    BULL_VOLATILE = "bull_volatile"
    BEAR_QUIET = "bear_quiet"
    BEAR_VOLATILE = "bear_volatile"
    SIDEWAYS = "sideways"
    CRISIS = "crisis"


# ===== Response Models =====

class SystemStatus(BaseModel):
    """System health status"""
    status: str
    mode: str
    connected: bool
    uptime_seconds: float
    last_heartbeat: str
    symbols_tracked: List[str]
    data_loaded: bool


class MarketDataResponse(BaseModel):
    """Real-time market data response"""
    symbol: str
    timestamp: str
    bid: float
    ask: float
    last: float
    volume: int
    high: float
    low: float
    open: float
    close: float
    spread: float
    spread_pct: float


class HistoricalBarResponse(BaseModel):
    """Historical bar response"""
    symbol: str
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: int


class PositionResponse(BaseModel):
    """Position information"""
    symbol: str
    quantity: int
    avg_cost: float
    current_price: float
    market_value: float
    unrealized_pnl: float
    unrealized_pnl_pct: float


class AccountSummary(BaseModel):
    """Account summary"""
    cash: float
    portfolio_value: float
    initial_capital: float
    total_pnl: float
    total_pnl_pct: float
    daily_pnl: float
    daily_pnl_pct: float
    positions: List[PositionResponse]


class TradeResponse(BaseModel):
    """Trade execution record"""
    order_id: str
    symbol: str
    side: str
    quantity: int
    filled_qty: int
    avg_price: float
    commission: float
    strategy: Optional[str]
    regime: Optional[str]
    timestamp: str


class FeatureSetResponse(BaseModel):
    """Feature set for a symbol"""
    symbol: str
    timestamp: str
    price: float
    return_1d: float
    return_5d: float
    return_20d: float
    volatility_20d: float
    volatility_annualized: float
    rsi_14: float
    macd_histogram: float
    bollinger_pct_b: float
    atr_pct: float
    adx_14: float
    volume_ratio: float


class StrategySignal(BaseModel):
    """Strategy signal"""
    strategy: str
    symbol: str
    signal: float  # -1 to +1
    confidence: float
    timestamp: str


class PortfolioSnapshot(BaseModel):
    """Portfolio snapshot for charting"""
    timestamp: str
    portfolio_value: float
    cash: float
    daily_pnl: float
    total_pnl: float


class DataQualityReport(BaseModel):
    """Data quality check results"""
    symbol: str
    status: str
    total_bars: int
    date_range: str
    issues: List[str]


class PerformanceMetrics(BaseModel):
    """Performance metrics"""
    total_return: float
    annual_return: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    win_rate: float
    profit_factor: float
    total_trades: int
    avg_trade_pnl: float


class DashboardData(BaseModel):
    """Complete dashboard data"""
    system_status: SystemStatus
    account: AccountSummary
    recent_trades: List[TradeResponse]
    market_data: List[MarketDataResponse]
    portfolio_history: List[PortfolioSnapshot]
    regime: str
    signals: List[StrategySignal]


# ===== Request Models =====

class OrderRequest(BaseModel):
    """Order placement request"""
    symbol: str
    quantity: int
    side: str  # BUY or SELL
    order_type: str = "LMT"  # LMT or MKT
    limit_price: Optional[float] = None


class BacktestRequest(BaseModel):
    """Backtest request"""
    symbols: List[str]
    start_date: str
    end_date: str
    initial_capital: float = 100000.0
    strategies: List[str]
    leverage: float = 1.0


class ConfigUpdate(BaseModel):
    """Configuration update request"""
    mode: Optional[TradingModeEnum] = None
    max_drawdown: Optional[float] = None
    kill_switch_drawdown: Optional[float] = None
    target_volatility: Optional[float] = None


class KillSwitchAction(BaseModel):
    """Kill switch action"""
    action: str  # "activate" or "deactivate"
    reason: Optional[str] = None
