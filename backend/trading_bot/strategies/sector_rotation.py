"""
Sector Rotation Strategy
Rotates between sectors based on relative strength
"""
import logging
import numpy as np
from typing import Dict, List
from datetime import datetime, timezone

from .base_strategy import BaseStrategy, Signal, StrategyResult

logger = logging.getLogger(__name__)


# Sector ETF mappings
SECTOR_ETFS = {
    "XLK": "Technology",
    "XLF": "Financials",
    "XLV": "Healthcare",
    "XLE": "Energy",
    "XLI": "Industrials",
    "XLY": "Consumer Discretionary",
    "XLP": "Consumer Staples",
    "XLU": "Utilities",
    "XLB": "Materials",
    "XLRE": "Real Estate",
}

# Stock to sector mapping
STOCK_SECTORS = {
    "AAPL": "Technology",
    "MSFT": "Technology",
    "NVDA": "Technology",
    "META": "Technology",
    "GOOGL": "Technology",
    "AMZN": "Consumer Discretionary",
    "TSLA": "Consumer Discretionary",
    "JPM": "Financials",
    "BAC": "Financials",
    "XOM": "Energy",
    "CVX": "Energy",
}


class SectorRotationStrategy(BaseStrategy):
    """
    Sector Rotation Trading Strategy
    
    Logic:
    1. Calculate relative strength of each sector
    2. Rank sectors by momentum
    3. Go long strong sectors, avoid/short weak sectors
    4. Rotate based on momentum shifts
    """
    
    name = "SectorRotation"
    
    def __init__(
        self,
        momentum_period: int = 20,
        ranking_threshold: float = 0.6,
        rotation_lookback: int = 5
    ):
        super().__init__()
        self.momentum_period = momentum_period
        self.ranking_threshold = ranking_threshold
        self.rotation_lookback = rotation_lookback
        
        self.sector_rankings: Dict[str, float] = {}
        self.previous_rankings: Dict[str, float] = {}
        
        logger.info("Sector Rotation strategy initialized")
    
    def calculate_momentum(self, close: np.ndarray) -> float:
        """Calculate momentum (return over period)"""
        if len(close) < self.momentum_period:
            return 0.0
        return (close[-1] / close[-self.momentum_period] - 1) * 100
    
    def calculate_relative_strength(self, stock_close: np.ndarray, benchmark_close: np.ndarray) -> float:
        """Calculate relative strength vs benchmark"""
        if len(stock_close) < self.momentum_period or len(benchmark_close) < self.momentum_period:
            return 0.0
        
        stock_return = stock_close[-1] / stock_close[-self.momentum_period] - 1
        benchmark_return = benchmark_close[-1] / benchmark_close[-self.momentum_period] - 1
        
        return (stock_return - benchmark_return) * 100
    
    def get_sector(self, symbol: str) -> str:
        """Get sector for a symbol"""
        return STOCK_SECTORS.get(symbol, "Unknown")
    
    def generate_signal(self, symbol: str, features: Dict) -> StrategyResult:
        """Generate sector rotation signal"""
        close = np.array(features.get('close', []))
        spy_close = np.array(features.get('SPY_close', close))  # Use SPY as benchmark
        
        if len(close) < self.momentum_period + self.rotation_lookback:
            return self._no_signal(symbol)
        
        # Get symbol's sector
        sector = self.get_sector(symbol)
        
        # Calculate momentum
        momentum = self.calculate_momentum(close)
        
        # Calculate relative strength vs SPY
        relative_strength = self.calculate_relative_strength(close, spy_close)
        
        # Calculate momentum trend (is it improving?)
        prev_momentum = self.calculate_momentum(close[:-self.rotation_lookback])
        momentum_improving = momentum > prev_momentum
        
        # Store rankings
        self.previous_rankings = self.sector_rankings.copy()
        self.sector_rankings[symbol] = relative_strength
        
        signal_value = 0.0
        confidence = 0.0
        rotation_signal = "hold"
        
        # Strong relative strength + improving momentum = buy
        if relative_strength > 2.0 and momentum_improving:
            signal_value = 0.7
            confidence = 0.65
            rotation_signal = "strong_sector"
        
        # Very strong outperformance
        elif relative_strength > 5.0:
            signal_value = 0.85
            confidence = 0.7
            rotation_signal = "sector_leader"
        
        # Weak relative strength + deteriorating momentum = sell/avoid
        elif relative_strength < -2.0 and not momentum_improving:
            signal_value = -0.6
            confidence = 0.6
            rotation_signal = "weak_sector"
        
        # Very weak underperformance
        elif relative_strength < -5.0:
            signal_value = -0.8
            confidence = 0.7
            rotation_signal = "sector_laggard"
        
        # Rotation opportunity - sector turning around
        elif symbol in self.previous_rankings:
            prev_rs = self.previous_rankings.get(symbol, 0)
            if relative_strength > 0 and prev_rs < 0:
                # Turning positive
                signal_value = 0.5
                confidence = 0.55
                rotation_signal = "sector_turnaround_up"
            elif relative_strength < 0 and prev_rs > 0:
                # Turning negative
                signal_value = -0.5
                confidence = 0.55
                rotation_signal = "sector_turnaround_down"
        
        # Determine signal
        if signal_value > 0.3:
            signal = Signal.BUY
        elif signal_value < -0.3:
            signal = Signal.SELL
        else:
            signal = Signal.HOLD
        
        return StrategyResult(
            strategy_name=self.name,
            symbol=symbol,
            signal=signal,
            raw_signal=signal_value,
            confidence=confidence,
            features_used={
                "sector": sector,
                "momentum": momentum,
                "relative_strength": relative_strength,
                "momentum_improving": momentum_improving,
                "rotation_signal": rotation_signal
            },
            timestamp=datetime.now(timezone.utc)
        )
    
    def _no_signal(self, symbol: str) -> StrategyResult:
        return StrategyResult(
            strategy_name=self.name,
            symbol=symbol,
            signal=Signal.HOLD,
            raw_signal=0.0,
            confidence=0.0,
            features_used={},
            timestamp=datetime.now(timezone.utc)
        )
