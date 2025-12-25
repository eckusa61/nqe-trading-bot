"""
Bollinger Band Squeeze Strategy
Trades volatility expansion after periods of contraction
"""
import logging
import numpy as np
from typing import Dict
from datetime import datetime, timezone

from .base_strategy import BaseStrategy, Signal, StrategyResult

logger = logging.getLogger(__name__)


class BollingerSqueezeStrategy(BaseStrategy):
    """
    Bollinger Band Squeeze Strategy
    
    Logic:
    1. Calculate Bollinger Bands
    2. Calculate Keltner Channels
    3. Squeeze = BB inside KC (low volatility)
    4. Trade breakout direction when squeeze releases
    """
    
    name = "BollingerSqueeze"
    
    def __init__(
        self,
        bb_period: int = 20,
        bb_std: float = 2.0,
        kc_period: int = 20,
        kc_multiplier: float = 1.5,
        squeeze_lookback: int = 6
    ):
        super().__init__()
        self.bb_period = bb_period
        self.bb_std = bb_std
        self.kc_period = kc_period
        self.kc_multiplier = kc_multiplier
        self.squeeze_lookback = squeeze_lookback
        logger.info("Bollinger Squeeze strategy initialized")
    
    def calculate_bollinger_bands(self, close: np.ndarray) -> tuple:
        """Calculate Bollinger Bands"""
        sma = np.zeros_like(close)
        upper = np.zeros_like(close)
        lower = np.zeros_like(close)
        
        for i in range(self.bb_period - 1, len(close)):
            window = close[i - self.bb_period + 1:i + 1]
            sma[i] = np.mean(window)
            std = np.std(window)
            upper[i] = sma[i] + self.bb_std * std
            lower[i] = sma[i] - self.bb_std * std
        
        return sma, upper, lower
    
    def calculate_keltner_channels(self, close: np.ndarray, high: np.ndarray, low: np.ndarray) -> tuple:
        """Calculate Keltner Channels"""
        # EMA
        ema = np.zeros_like(close)
        multiplier = 2 / (self.kc_period + 1)
        ema[self.kc_period - 1] = np.mean(close[:self.kc_period])
        for i in range(self.kc_period, len(close)):
            ema[i] = (close[i] - ema[i-1]) * multiplier + ema[i-1]
        
        # ATR
        tr = np.maximum(high - low, np.maximum(
            np.abs(high - np.roll(close, 1)),
            np.abs(low - np.roll(close, 1))
        ))
        atr = np.zeros_like(close)
        for i in range(self.kc_period - 1, len(close)):
            atr[i] = np.mean(tr[i - self.kc_period + 1:i + 1])
        
        upper = ema + self.kc_multiplier * atr
        lower = ema - self.kc_multiplier * atr
        
        return ema, upper, lower
    
    def calculate_momentum(self, close: np.ndarray, period: int = 12) -> np.ndarray:
        """Calculate momentum oscillator"""
        momentum = np.zeros_like(close)
        for i in range(period, len(close)):
            momentum[i] = close[i] - close[i - period]
        return momentum
    
    def generate_signal(self, symbol: str, features: Dict) -> StrategyResult:
        """Generate Bollinger Squeeze signal"""
        close = np.array(features.get('close', []))
        high = np.array(features.get('high', []))
        low = np.array(features.get('low', []))
        
        min_periods = max(self.bb_period, self.kc_period) + self.squeeze_lookback + 5
        if len(close) < min_periods:
            return self._no_signal(symbol)
        
        # Calculate indicators
        bb_mid, bb_upper, bb_lower = self.calculate_bollinger_bands(close)
        kc_mid, kc_upper, kc_lower = self.calculate_keltner_channels(close, high, low)
        momentum = self.calculate_momentum(close)
        
        # Check for squeeze (BB inside KC)
        squeeze_on = np.zeros(len(close), dtype=bool)
        for i in range(len(close)):
            squeeze_on[i] = (bb_lower[i] > kc_lower[i]) and (bb_upper[i] < kc_upper[i])
        
        current_squeeze = squeeze_on[-1]
        was_in_squeeze = np.any(squeeze_on[-self.squeeze_lookback:-1])
        squeeze_released = was_in_squeeze and not current_squeeze
        
        current_momentum = momentum[-1]
        prev_momentum = momentum[-2]
        momentum_rising = current_momentum > prev_momentum
        
        signal_value = 0.0
        confidence = 0.0
        state = "normal"
        
        # Squeeze release signals
        if squeeze_released:
            if current_momentum > 0 and momentum_rising:
                # Bullish breakout from squeeze
                signal_value = 0.85
                confidence = 0.75
                state = "squeeze_release_bullish"
            elif current_momentum < 0 and not momentum_rising:
                # Bearish breakout from squeeze
                signal_value = -0.85
                confidence = 0.75
                state = "squeeze_release_bearish"
        
        # In squeeze - prepare for breakout
        elif current_squeeze:
            state = "in_squeeze"
            # Small signal based on momentum direction
            if current_momentum > 0:
                signal_value = 0.2
            elif current_momentum < 0:
                signal_value = -0.2
            confidence = 0.3
        
        # Normal Bollinger Band signals
        else:
            current_price = close[-1]
            bb_position = (current_price - bb_lower[-1]) / (bb_upper[-1] - bb_lower[-1])
            
            if bb_position < 0.05:  # Near lower band
                signal_value = 0.5
                confidence = 0.5
                state = "near_lower_band"
            elif bb_position > 0.95:  # Near upper band
                signal_value = -0.5
                confidence = 0.5
                state = "near_upper_band"
        
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
                "state": state,
                "squeeze_on": current_squeeze,
                "squeeze_released": squeeze_released,
                "momentum": current_momentum,
                "momentum_rising": momentum_rising,
                "bb_upper": bb_upper[-1],
                "bb_lower": bb_lower[-1],
                "bb_mid": bb_mid[-1]
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
