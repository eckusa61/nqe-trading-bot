"""
Mean Reversion Strategy
Uses RSI for overbought/oversold conditions
"""
from typing import Dict, List, Optional
from trading_bot.strategies.base_strategy import BaseStrategy, Signal
from trading_bot.data.feature_engine import FeatureSet


class MeanReversionStrategy(BaseStrategy):
    """
    Mean Reversion Strategy based on RSI
    
    Rules:
    - LONG: RSI < 30 (oversold)
    - SHORT: RSI > 70 (overbought)
    - Signal strength based on RSI extremity
    - Confidence based on Bollinger Band position
    """
    
    def __init__(
        self,
        oversold_threshold: float = 30.0,
        overbought_threshold: float = 70.0,
        extreme_oversold: float = 20.0,
        extreme_overbought: float = 80.0
    ):
        super().__init__(
            name="MeanReversion",
            description="RSI-based mean reversion strategy"
        )
        self.oversold_threshold = oversold_threshold
        self.overbought_threshold = overbought_threshold
        self.extreme_oversold = extreme_oversold
        self.extreme_overbought = extreme_overbought
    
    def generate_signal(self, features: FeatureSet, historical_features: Optional[List[FeatureSet]] = None) -> Signal:
        """
        Generate mean reversion signal based on RSI
        """
        rsi = features.rsi_14
        price = features.price
        bb_pct_b = features.bollinger_pct_b
        
        # Determine signal based on RSI
        if rsi <= self.extreme_oversold:
            # Extremely oversold - strong buy signal
            raw_signal = 1.0
            reason = f"Extreme oversold: RSI={rsi:.1f}"
        elif rsi <= self.oversold_threshold:
            # Oversold - buy signal scaled by RSI level
            raw_signal = (self.oversold_threshold - rsi) / (self.oversold_threshold - self.extreme_oversold)
            reason = f"Oversold: RSI={rsi:.1f}"
        elif rsi >= self.extreme_overbought:
            # Extremely overbought - strong sell signal
            raw_signal = -1.0
            reason = f"Extreme overbought: RSI={rsi:.1f}"
        elif rsi >= self.overbought_threshold:
            # Overbought - sell signal scaled by RSI level
            raw_signal = -(rsi - self.overbought_threshold) / (self.extreme_overbought - self.overbought_threshold)
            reason = f"Overbought: RSI={rsi:.1f}"
        else:
            # Neutral zone
            raw_signal = 0.0
            reason = f"Neutral RSI: {rsi:.1f}"
        
        # Calculate confidence based on Bollinger Band confirmation
        # BB %B < 0 means price below lower band (confirms oversold)
        # BB %B > 1 means price above upper band (confirms overbought)
        if raw_signal > 0 and bb_pct_b < 0.2:
            confidence = 0.8 + (0.2 - bb_pct_b) * 0.5
        elif raw_signal < 0 and bb_pct_b > 0.8:
            confidence = 0.8 + (bb_pct_b - 0.8) * 0.5
        elif raw_signal != 0:
            confidence = 0.5
        else:
            confidence = 0.3
        
        confidence = min(1.0, confidence)
        
        # Mean reversion needs tighter stops
        atr = features.atr_14
        if raw_signal > 0:
            stop_loss = price - 1.5 * atr  # Tighter stop for mean reversion
            take_profit = price + 2 * atr
        elif raw_signal < 0:
            stop_loss = price + 1.5 * atr
            take_profit = price - 2 * atr
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
            "oversold_threshold": self.oversold_threshold,
            "overbought_threshold": self.overbought_threshold,
            "extreme_oversold": self.extreme_oversold,
            "extreme_overbought": self.extreme_overbought
        }
