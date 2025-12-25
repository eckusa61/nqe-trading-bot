# Strategies module
from .base_strategy import BaseStrategy, Signal, StrategyResult, strategy_registry
from .momentum import MomentumStrategy
from .mean_reversion import MeanReversionStrategy
from .volatility_breakout import VolatilityBreakoutStrategy
from .trend_following import TrendFollowingStrategy
from .stat_arb import StatisticalArbitrageStrategy
