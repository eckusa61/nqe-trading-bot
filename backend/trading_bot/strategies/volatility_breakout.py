"""
Volatility Breakout Strategy
Uses ATR for breakout detection
"""
from typing import Dict, List, Optional
from trading_bot.strategies.base_strategy import BaseStrategy, Signal
from trading_bot.data.feature_engine import FeatureSet


class VolatilityBreakoutStrategy(BaseStrategy):
    """
    Volatility Breakout Strategy
    
    Rules:
    - LONG: Price breaks above upper Bollinger Band with expanding volatility
    - SHORT: Price breaks below lower Bollinger Band with expanding volatility
    - Signal strength based on breakout magnitude
    - Confidence based on volume confirmation
    """
    
    def __init__(
        self,
        atr_multiplier: float = 2.0,
        volume_threshold: float = 1.5,  # Volume must be 1.5x average
        min_volatility_expansion: float = 1.2  # Current vol must be 1.2x recent
    ):
        super().__init__(
            name="VolatilityBreakout",
            description="ATR-based volatility breakout strategy"
        )
        self.atr_multiplier = atr_multiplier
        self.volume_threshold = volume_threshold
        self.min_volatility_expansion = min_volatility_expansion
    
    def generate_signal(self, features: FeatureSet, historical_features: Optional[List[FeatureSet]] = None) -> Signal:
        """
        Generate volatility breakout signal
        """
        price = features.price
        bb_upper = features.bollinger_upper
        bb_lower = features.bollinger_lower
        bb_pct_b = features.bollinger_pct_b
        atr = features.atr_14
        atr_pct = features.atr_pct
        volume_ratio = features.volume_ratio
        daily_range = features.daily_range_pct
        
        # Check for volatility expansion (using daily range as proxy)
        volatility_expanding = daily_range > atr_pct * self.min_volatility_expansion
        
        # Check volume confirmation
        volume_confirmed = volume_ratio >= self.volume_threshold
        
        # Detect breakouts
        if bb_pct_b > 1.0:  # Price above upper BB
            # Bullish breakout
            breakout_strength = (bb_pct_b - 1.0) * 2  # Scale breakout
            raw_signal = min(1.0, breakout_strength)
            reason = f"Bullish breakout: Price above upper BB, %B={bb_pct_b:.2f}"
            
        elif bb_pct_b < 0.0:  # Price below lower BB
            # Bearish breakout
            breakout_strength = abs(bb_pct_b) * 2
            raw_signal = -min(1.0, breakout_strength)
            reason = f"Bearish breakout: Price below lower BB, %B={bb_pct_b:.2f}"
            
        elif bb_pct_b > 0.9:  # Approaching upper band
            raw_signal = 0.3 * (bb_pct_b - 0.9) / 0.1
            reason = f"Approaching upper breakout: %B={bb_pct_b:.2f}"
            
        elif bb_pct_b < 0.1:  # Approaching lower band
            raw_signal = -0.3 * (0.1 - bb_pct_b) / 0.1
            reason = f"Approaching lower breakout: %B={bb_pct_b:.2f}"
        else:
            raw_signal = 0.0
            reason = "No breakout detected"
        
        # Calculate confidence
        confidence = 0.3  # Base confidence
        
        if volatility_expanding:
            confidence += 0.3
            reason += " | Vol expanding"
        
        if volume_confirmed:
            confidence += 0.3
            reason += f" | Vol {volume_ratio:.1f}x"
        
        # Additional confidence from ADX (trend strength)
        if features.adx_14 > 25:
            confidence += 0.1
        
        confidence = min(1.0, confidence)
        
        # If no volume or volatility confirmation, reduce signal
        if not volume_confirmed and not volatility_expanding:
            raw_signal *= 0.5
            confidence *= 0.6
        
        # Breakout strategy uses wider stops
        if raw_signal > 0:
            stop_loss = price - self.atr_multiplier * atr
            take_profit = price + 3 * atr
        elif raw_signal < 0:
            stop_loss = price + self.atr_multiplier * atr
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
            "atr_multiplier": self.atr_multiplier,
            "volume_threshold": self.volume_threshold,
            "min_volatility_expansion": self.min_volatility_expansion
        }
