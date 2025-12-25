"""
Trend Following Strategy
Uses ADX + Directional Movement for trend identification
"""
from typing import Dict, List, Optional
from trading_bot.strategies.base_strategy import BaseStrategy, Signal
from trading_bot.data.feature_engine import FeatureSet


class TrendFollowingStrategy(BaseStrategy):
    """
    Trend Following Strategy using ADX and Directional Movement
    
    Rules:
    - LONG: ADX > 25 AND +DI > -DI (strong uptrend)
    - SHORT: ADX > 25 AND -DI > +DI (strong downtrend)
    - Signal strength based on DI difference
    - Confidence based on ADX strength and MA alignment
    """
    
    def __init__(
        self,
        adx_threshold: float = 25.0,
        strong_trend_adx: float = 40.0,
        di_min_difference: float = 5.0  # Minimum DI difference
    ):
        super().__init__(
            name="TrendFollowing",
            description="ADX + Directional Movement trend strategy"
        )
        self.adx_threshold = adx_threshold
        self.strong_trend_adx = strong_trend_adx
        self.di_min_difference = di_min_difference
    
    def generate_signal(self, features: FeatureSet, historical_features: Optional[List[FeatureSet]] = None) -> Signal:
        """
        Generate trend following signal based on ADX and DI
        """
        price = features.price
        adx = features.adx_14
        plus_di = features.plus_di
        minus_di = features.minus_di
        
        # Calculate DI difference
        di_diff = plus_di - minus_di
        
        # Check if we have a trending market
        is_trending = adx >= self.adx_threshold
        is_strong_trend = adx >= self.strong_trend_adx
        
        if not is_trending:
            # No trend - stay flat
            return Signal(
                symbol=features.symbol,
                signal=0.0,
                confidence=0.3,
                strategy=self.name,
                reason=f"No trend: ADX={adx:.1f} < {self.adx_threshold}",
                entry_price=price
            )
        
        # Determine trend direction
        if di_diff > self.di_min_difference:
            # Uptrend
            signal_strength = min(1.0, di_diff / 30.0)  # Scale DI diff to signal
            reason = f"Uptrend: +DI({plus_di:.1f}) > -DI({minus_di:.1f}), ADX={adx:.1f}"
        elif di_diff < -self.di_min_difference:
            # Downtrend
            signal_strength = max(-1.0, di_diff / 30.0)
            reason = f"Downtrend: -DI({minus_di:.1f}) > +DI({plus_di:.1f}), ADX={adx:.1f}"
        else:
            # DI crossover zone - uncertain
            signal_strength = 0.0
            reason = f"DI crossover zone: diff={di_diff:.1f}"
        
        # Calculate confidence based on trend strength and MA confirmation
        if is_strong_trend:
            confidence = 0.8
        else:
            confidence = 0.5 + (adx - self.adx_threshold) / 30.0 * 0.3
        
        # MA confirmation
        ma_aligned = False
        if signal_strength > 0:
            # For uptrend, check if price > SMA50 > SMA200
            if features.sma_20 > features.sma_50:
                confidence += 0.1
                ma_aligned = True
                reason += " | MA aligned"
        elif signal_strength < 0:
            # For downtrend, check if price < SMA50 < SMA200
            if features.sma_20 < features.sma_50:
                confidence += 0.1
                ma_aligned = True
                reason += " | MA aligned"
        
        confidence = min(1.0, confidence)
        
        # Trend following uses trailing stops
        atr = features.atr_14
        if signal_strength > 0:
            stop_loss = price - 2.5 * atr
            take_profit = price + 4 * atr  # Let winners run
        elif signal_strength < 0:
            stop_loss = price + 2.5 * atr
            take_profit = price - 4 * atr
        else:
            stop_loss = None
            take_profit = None
        
        return Signal(
            symbol=features.symbol,
            signal=signal_strength,
            confidence=confidence,
            strategy=self.name,
            reason=reason,
            entry_price=price,
            stop_loss=stop_loss,
            take_profit=take_profit
        )
    
    def get_parameters(self) -> Dict:
        return {
            "adx_threshold": self.adx_threshold,
            "strong_trend_adx": self.strong_trend_adx,
            "di_min_difference": self.di_min_difference
        }
