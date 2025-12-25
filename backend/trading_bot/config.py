"""
Trading Bot Configuration
All system parameters in one place for easy modification
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from enum import Enum
import os


class TradingMode(Enum):
    """Trading mode selector"""
    SIMULATED = "simulated"
    LIVE_PAPER = "live_paper"
    LIVE_REAL = "live_real"


class MarketRegime(Enum):
    """Market regime states"""
    BULL_QUIET = "bull_quiet"
    BULL_VOLATILE = "bull_volatile"
    BEAR_QUIET = "bear_quiet"
    BEAR_VOLATILE = "bear_volatile"
    SIDEWAYS = "sideways"
    CRISIS = "crisis"


@dataclass
class IBKRConfig:
    """Interactive Brokers Connection Configuration"""
    host: str = "127.0.0.1"
    paper_port: int = 7497  # TWS Paper Trading
    live_port: int = 7496   # TWS Live
    gateway_paper_port: int = 4002  # IB Gateway Paper
    gateway_live_port: int = 4001   # IB Gateway Live
    client_id: int = 1
    timeout: int = 60
    auto_reconnect: bool = True
    reconnect_delay: int = 5
    max_reconnect_attempts: int = 10


@dataclass
class SymbolTier:
    """Symbol configuration with liquidity tier"""
    symbol: str
    tier: int  # 1 = ultra liquid, 2 = very liquid, 3 = liquid
    sector: str
    
    
@dataclass
class SymbolConfig:
    """Trading symbols configuration"""
    symbols: List[SymbolTier] = field(default_factory=lambda: [
        # Tier 1: Ultra Liquid ETFs
        SymbolTier("SPY", 1, "ETF"),
        SymbolTier("QQQ", 1, "ETF"),
        # Tier 2: Very Liquid Stocks
        SymbolTier("AAPL", 2, "Technology"),
        SymbolTier("MSFT", 2, "Technology"),
        SymbolTier("TSLA", 2, "Automotive"),
        # Tier 3: Liquid Testing
        SymbolTier("NVDA", 3, "Technology"),
        SymbolTier("META", 3, "Technology"),
    ])
    
    @property
    def all_symbols(self) -> List[str]:
        return [s.symbol for s in self.symbols]
    
    def get_tier(self, symbol: str) -> int:
        for s in self.symbols:
            if s.symbol == symbol:
                return s.tier
        return 3  # Default to tier 3


@dataclass
class DataConfig:
    """Data management configuration"""
    db_path: str = "trading_data.db"
    history_years: int = 5
    bar_size: str = "1 day"  # IBKR bar size
    use_rth: bool = True  # Regular trading hours only
    max_bars_per_request: int = 1000
    data_quality_check: bool = True
    outlier_std_threshold: float = 5.0


@dataclass 
class FeatureConfig:
    """Feature engineering configuration"""
    return_periods: List[int] = field(default_factory=lambda: [1, 5, 20, 60, 120, 252])
    ma_periods: List[int] = field(default_factory=lambda: [10, 20, 50, 100, 200])
    volatility_window: int = 20
    rsi_period: int = 14
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    atr_period: int = 14
    bollinger_period: int = 20
    bollinger_std: float = 2.0
    adx_period: int = 14
    volume_ma_period: int = 20


@dataclass
class BacktestConfig:
    """Backtesting configuration with realistic costs"""
    # Transaction costs
    commission_per_share: float = 0.005  # $0.005/share
    min_commission: float = 1.0  # Minimum $1 per trade
    base_slippage: float = 0.0005  # 0.05% base slippage
    volatility_slippage_multiplier: float = 0.5
    size_impact_threshold: int = 1000  # Shares before size impact
    size_impact_rate: float = 0.0001  # Additional slippage per 1000 shares
    
    # Latency simulation
    signal_to_fill_delay_ms: int = 150
    
    # Partial fills
    partial_fill_probability: float = 0.15
    avg_fill_rate: float = 0.70
    
    # Walk-forward optimization
    train_window_days: int = 252  # 1 year
    test_window_days: int = 63    # 3 months
    walk_forward_step: int = 21   # Monthly steps


@dataclass
class RiskConfig:
    """Risk management configuration"""
    # Position sizing
    target_annual_volatility: float = 0.15  # 15% annual portfolio vol
    max_risk_per_trade: float = 0.02  # 2% max risk per trade
    max_kelly_fraction: float = 0.25  # Maximum Kelly bet
    
    # Portfolio limits
    max_gross_exposure: float = 3.0  # 3x leverage max for paper
    max_single_position: float = 0.10  # 10% max single position
    max_sector_exposure: float = 0.30  # 30% max sector
    
    # Drawdown protection
    warning_drawdown: float = 0.10  # 10% - reduce leverage
    max_drawdown: float = 0.15  # 15% - hard stop
    kill_switch_drawdown: float = 0.20  # 20% - full shutdown
    
    # VaR/CVaR
    var_confidence: float = 0.95
    cvar_confidence: float = 0.95
    var_lookback_days: int = 252


@dataclass
class ExecutionConfig:
    """Execution engine configuration"""
    # Order types
    default_order_type: str = "LMT"  # Limit orders default
    market_order_exits_only: bool = True
    
    # Timing
    avoid_first_minutes: int = 15  # Avoid first 15 min
    avoid_last_minutes: int = 15   # Avoid last 15 min
    
    # Tier-based execution
    tier1_fill_aggressiveness: float = 1.0  # Aggressive
    tier2_vwap_participation: float = 0.10  # 10% of volume
    tier3_patience_hours: float = 2.0  # Spread over 2 hours


@dataclass
class MonitoringConfig:
    """Monitoring and alerting configuration"""
    heartbeat_interval_seconds: int = 30
    data_staleness_threshold_seconds: int = 300
    log_level: str = "INFO"
    alert_on_drawdown: bool = True
    alert_on_error: bool = True
    performance_snapshot_interval: int = 300  # 5 min


@dataclass
class TradingConfig:
    """Master configuration combining all configs"""
    mode: TradingMode = TradingMode.SIMULATED
    ibkr: IBKRConfig = field(default_factory=IBKRConfig)
    symbols: SymbolConfig = field(default_factory=SymbolConfig)
    data: DataConfig = field(default_factory=DataConfig)
    features: FeatureConfig = field(default_factory=FeatureConfig)
    backtest: BacktestConfig = field(default_factory=BacktestConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)
    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)
    
    @classmethod
    def from_env(cls) -> "TradingConfig":
        """Load configuration from environment variables"""
        config = cls()
        
        # Override mode from environment
        mode_str = os.environ.get("TRADING_MODE", "simulated").lower()
        if mode_str == "live_paper":
            config.mode = TradingMode.LIVE_PAPER
        elif mode_str == "live_real":
            config.mode = TradingMode.LIVE_REAL
        else:
            config.mode = TradingMode.SIMULATED
            
        # Override database path
        if db_path := os.environ.get("TRADING_DB_PATH"):
            config.data.db_path = db_path
            
        return config


# Global config instance
CONFIG = TradingConfig.from_env()
