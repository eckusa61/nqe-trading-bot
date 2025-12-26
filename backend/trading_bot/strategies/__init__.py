"""
Trading Strategies Module
15 Professional Trading Strategies
"""

# Base
from .base_strategy import BaseStrategy, Signal, StrategyResult

# Original 5 Strategies
from .mean_reversion import MeanReversionStrategy
from .momentum import MomentumStrategy
from .volatility_breakout import VolatilityBreakoutStrategy
from .trend_following import TrendFollowingStrategy
from .stat_arb import StatisticalArbitrageStrategy

# New 10 Strategies
from .pairs_trading import PairsTradingStrategy
from .breakout import BreakoutStrategy
from .rsi_divergence import RSIDivergenceStrategy
from .macd_crossover import MACDCrossoverStrategy
from .bollinger_squeeze import BollingerSqueezeStrategy
from .vwap_reversion import VWAPReversionStrategy
from .orb import ORBStrategy
from .gap_trading import GapTradingStrategy
from .volume_profile import VolumeProfileStrategy
from .sector_rotation import SectorRotationStrategy

__all__ = [
    # Base
    'BaseStrategy',
    'Signal',
    'StrategyResult',
    
    # Original Strategies
    'MeanReversionStrategy',
    'MomentumStrategy',
    'VolatilityBreakoutStrategy',
    'TrendFollowingStrategy',
    'StatisticalArbitrageStrategy',
    
    # New Strategies
    'PairsTradingStrategy',
    'BreakoutStrategy',
    'RSIDivergenceStrategy',
    'MACDCrossoverStrategy',
    'BollingerSqueezeStrategy',
    'VWAPReversionStrategy',
    'ORBStrategy',
    'GapTradingStrategy',
    'VolumeProfileStrategy',
    'SectorRotationStrategy',
]

# Strategy registry for easy access
STRATEGY_REGISTRY = {
    'mean_reversion': MeanReversionStrategy,
    'momentum': MomentumStrategy,
    'volatility_breakout': VolatilityBreakoutStrategy,
    'trend_following': TrendFollowingStrategy,
    'stat_arb': StatisticalArbitrageStrategy,
    'pairs_trading': PairsTradingStrategy,
    'breakout': BreakoutStrategy,
    'rsi_divergence': RSIDivergenceStrategy,
    'macd_crossover': MACDCrossoverStrategy,
    'bollinger_squeeze': BollingerSqueezeStrategy,
    'vwap_reversion': VWAPReversionStrategy,
    'orb': ORBStrategy,
    'gap_trading': GapTradingStrategy,
    'volume_profile': VolumeProfileStrategy,
    'sector_rotation': SectorRotationStrategy,
}


def get_all_strategies():
    """Get instances of all strategies"""
    return [
        MeanReversionStrategy(),
        MomentumStrategy(),
        VolatilityBreakoutStrategy(),
        TrendFollowingStrategy(),
        StatArbStrategy(),
        PairsTradingStrategy(),
        BreakoutStrategy(),
        RSIDivergenceStrategy(),
        MACDCrossoverStrategy(),
        BollingerSqueezeStrategy(),
        VWAPReversionStrategy(),
        ORBStrategy(),
        GapTradingStrategy(),
        VolumeProfileStrategy(),
        SectorRotationStrategy(),
    ]
