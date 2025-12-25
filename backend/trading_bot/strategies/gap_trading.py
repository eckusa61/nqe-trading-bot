"""
Gap Trading Strategy
Trades opening gaps with fade or continuation logic
"""
import logging
import numpy as np
from typing import Dict
from datetime import datetime, timezone

from .base_strategy import BaseStrategy, Signal, StrategyResult

logger = logging.getLogger(__name__)


class GapTradingStrategy(BaseStrategy):
    """
    Gap Trading Strategy
    
    Logic:
    1. Detect opening gaps (gap up or gap down)
    2. Small gaps: Fade (trade against gap)
    3. Large gaps: Continuation (trade with gap)
    4. Use previous day's range for context
    """
    
    name = "GapTrading"
    
    def __init__(
        self,
        small_gap_pct: float = 0.005,
        large_gap_pct: float = 0.02,
        fade_target: float = 0.5,
        continuation_target: float = 1.5
    ):
        super().__init__()
        self.small_gap_pct = small_gap_pct
        self.large_gap_pct = large_gap_pct
        self.fade_target = fade_target
        self.continuation_target = continuation_target
        logger.info("Gap Trading strategy initialized")
    
    def detect_gap(self, close: np.ndarray, open_price: float) -> tuple:
        """Detect gap size and direction"""
        prev_close = close[-2] if len(close) > 1 else close[-1]
        gap_pct = (open_price - prev_close) / prev_close
        
        if gap_pct > 0:
            gap_direction = "up"
        elif gap_pct < 0:
            gap_direction = "down"
        else:
            gap_direction = "none"
        
        return gap_pct, gap_direction
    
    def generate_signal(self, symbol: str, features: Dict) -> StrategyResult:
        """Generate gap trading signal"""
        close = np.array(features.get('close', []))
        open_prices = np.array(features.get('open', []))
        high = np.array(features.get('high', []))
        low = np.array(features.get('low', []))
        
        if len(close) < 5:
            return self._no_signal(symbol)
        
        current_open = open_prices[-1] if len(open_prices) > 0 else close[-1]
        current_price = close[-1]
        
        # Detect gap
        gap_pct, gap_direction = self.detect_gap(close, current_open)
        gap_size = abs(gap_pct)
        
        # Calculate previous day's range
        prev_range = high[-2] - low[-2] if len(high) > 1 else 0
        prev_atr = np.mean(high[-5:] - low[-5:]) if len(high) >= 5 else prev_range
        
        signal_value = 0.0
        confidence = 0.0
        strategy_type = "none"
        
        # Gap fill progress
        if gap_direction == "up":
            fill_progress = (current_open - current_price) / (current_open - close[-2]) if current_open != close[-2] else 0
        elif gap_direction == "down":
            fill_progress = (current_price - current_open) / (close[-2] - current_open) if close[-2] != current_open else 0
        else:
            fill_progress = 0
        
        # Small gap - Fade strategy
        if self.small_gap_pct <= gap_size < self.large_gap_pct:
            if gap_direction == "up" and fill_progress < 0.3:
                # Gap up, price hasn't filled much - short for gap fill
                signal_value = -0.6
                confidence = 0.65
                strategy_type = "fade_gap_up"
            elif gap_direction == "down" and fill_progress < 0.3:
                # Gap down, price hasn't filled much - long for gap fill
                signal_value = 0.6
                confidence = 0.65
                strategy_type = "fade_gap_down"
            elif fill_progress > 0.8:
                # Gap mostly filled - close position
                signal_value = 0.0
                confidence = 0.7
                strategy_type = "gap_filled"
        
        # Large gap - Continuation strategy
        elif gap_size >= self.large_gap_pct:
            if gap_direction == "up" and current_price > current_open:
                # Large gap up and price holding/rising - continue long
                signal_value = 0.7
                confidence = 0.6
                strategy_type = "continuation_gap_up"
            elif gap_direction == "down" and current_price < current_open:
                # Large gap down and price holding/falling - continue short
                signal_value = -0.7
                confidence = 0.6
                strategy_type = "continuation_gap_down"
            elif gap_direction == "up" and current_price < current_open:
                # Large gap up but failed - strong reversal signal
                signal_value = -0.8
                confidence = 0.7
                strategy_type = "failed_gap_up"
            elif gap_direction == "down" and current_price > current_open:
                # Large gap down but failed - strong reversal signal
                signal_value = 0.8
                confidence = 0.7
                strategy_type = "failed_gap_down"
        
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
                "gap_pct": gap_pct * 100,
                "gap_direction": gap_direction,
                "strategy_type": strategy_type,
                "fill_progress": fill_progress,
                "prev_atr": prev_atr
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
