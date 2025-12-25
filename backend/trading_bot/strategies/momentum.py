"""
Momentum Strategy
Uses 20/50 MA crossover for trend identification
"""
from typing import Dict, List, Optional
from trading_bot.strategies.base_strategy import BaseStrategy, Signal
from trading_bot.data.feature_engine import FeatureSet


class MomentumStrategy(BaseStrategy):
    """
    Momentum Strategy based on Moving Average Crossover
    
    Rules:
    - LONG: SMA20 > SMA50 (golden cross territory)
    - SHORT: SMA20 < SMA50 (death cross territory)
    - Signal strength based on distance between MAs
    - Confidence based on trend consistency (ADX)
    """
    
    def __init__(
        self,
        fast_period: int = 20,
        slow_period: int = 50,
        adx_threshold: float = 25.0,
        min_ma_separation: float = 0.005  # 0.5% minimum separation
    ):
        super().__init__(
            name="Momentum",
            description="MA Crossover momentum strategy (20/50 SMA)"
        )
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.adx_threshold = adx_threshold
        self.min_ma_separation = min_ma_separation
    
    def generate_signal(self, features: FeatureSet, historical_features: Optional[List[FeatureSet]] = None) -> Signal:
        """
        Generate momentum signal based on MA crossover
        """
        # Get MA values
        sma_fast = features.sma_20
        sma_slow = features.sma_50
        price = features.price
        adx = features.adx_14
        
        # Calculate MA separation
        if sma_slow > 0:
            ma_separation = (sma_fast - sma_slow) / sma_slow
        else:
            ma_separation = 0
        
        # Determine signal direction
        if ma_separation > self.min_ma_separation:
            # Bullish: fast MA above slow MA
            raw_signal = min(1.0, ma_separation / 0.05)  # Scale to max 1.0 at 5% separation
            reason = f"Golden cross: SMA20 ({sma_fast:.2f}) > SMA50 ({sma_slow:.2f})"
        elif ma_separation < -self.min_ma_separation:
            # Bearish: fast MA below slow MA
            raw_signal = max(-1.0, ma_separation / 0.05)
            reason = f"Death cross: SMA20 ({sma_fast:.2f}) < SMA50 ({sma_slow:.2f})"
        else:
            # No clear signal
            raw_signal = 0.0
            reason = "No clear MA crossover signal"
        
        # Calculate confidence based on ADX (trend strength)
        if adx > self.adx_threshold:
            confidence = min(1.0, adx / 50.0)  # Scale ADX to confidence
        else:
            confidence = adx / self.adx_threshold * 0.5  # Lower confidence in weak trends
        
        # Additional confirmation from price relative to MAs
        price_confirmation = 1.0
        if raw_signal > 0 and price < sma_fast:
            price_confirmation = 0.7  # Price below fast MA reduces confidence
        elif raw_signal < 0 and price > sma_fast:
            price_confirmation = 0.7
        
        confidence *= price_confirmation
        
        # Calculate stop loss and take profit
        atr = features.atr_14
        if raw_signal > 0:
            stop_loss = price - 2 * atr
            take_profit = price + 3 * atr
        elif raw_signal < 0:
            stop_loss = price + 2 * atr
            take_profit = price - 3 * atr
        else:
            stop_loss = None
            take_profit = None
        
        return Signal(
            symbol=features.symbol,
            signal=raw_signal,
            confidence=confidence,
            strategy=self.name,
            reason=reason,
            entry_price=price,
            stop_loss=stop_loss,
            take_profit=take_profit
        )
    
    def get_parameters(self) -> Dict:
        return {
            "fast_period": self.fast_period,
            "slow_period": self.slow_period,
            "adx_threshold": self.adx_threshold,
            "min_ma_separation": self.min_ma_separation
        }
