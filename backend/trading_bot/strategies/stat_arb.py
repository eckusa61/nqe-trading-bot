"""
Statistical Arbitrage Strategy
Pairs trading between correlated assets (SPY vs QQQ)
"""
from typing import Dict, List, Optional
from trading_bot.strategies.base_strategy import BaseStrategy, Signal
from trading_bot.data.feature_engine import FeatureSet
import math


class StatisticalArbitrageStrategy(BaseStrategy):
    """
    Statistical Arbitrage / Pairs Trading Strategy
    
    Trades the spread between correlated ETFs (SPY vs QQQ)
    
    Rules:
    - Calculate z-score of price ratio (SPY/QQQ)
    - LONG SPY / SHORT QQQ: When z-score < -2 (SPY undervalued vs QQQ)
    - SHORT SPY / LONG QQQ: When z-score > 2 (SPY overvalued vs QQQ)
    - Exit when z-score reverts to 0
    """
    
    def __init__(
        self,
        entry_zscore: float = 2.0,
        exit_zscore: float = 0.5,
        lookback_period: int = 60,  # Days for calculating mean/std
        pair: tuple = ("SPY", "QQQ")
    ):
        super().__init__(
            name="StatArb",
            description="Statistical arbitrage pairs trading (SPY/QQQ)"
        )
        self.entry_zscore = entry_zscore
        self.exit_zscore = exit_zscore
        self.lookback_period = lookback_period
        self.pair = pair
        
        # Store historical ratios for z-score calculation
        self._ratio_history: List[float] = []
        self._current_position: str = "flat"  # "long_spread", "short_spread", "flat"
    
    def generate_signal(self, features: FeatureSet, historical_features: Optional[List[FeatureSet]] = None) -> Signal:
        """
        Generate stat arb signal
        
        Note: This strategy needs both symbols' features to work properly.
        When called with a single symbol, it provides individual recommendations
        based on relative strength.
        """
        symbol = features.symbol
        price = features.price
        
        # For non-pair symbols, return neutral
        if symbol not in self.pair:
            return Signal(
                symbol=symbol,
                signal=0.0,
                confidence=0.0,
                strategy=self.name,
                reason="Not in pairs universe",
                entry_price=price
            )
        
        # Use relative metrics as proxy for pair relationship
        # In a real implementation, we'd track the actual ratio
        return_20d = features.return_20d
        rsi = features.rsi_14
        price_to_ma = features.price_to_sma_50
        
        # Calculate a pseudo z-score based on available features
        # This is simplified - real stat arb would track the actual spread
        
        # Use distance from 50-day MA as mean reversion signal
        if abs(price_to_ma) > 0.05:  # More than 5% from MA
            zscore = price_to_ma / 0.025  # Normalize to z-score like metric
        else:
            zscore = 0
        
        # Generate signal based on z-score
        if symbol == self.pair[0]:  # SPY
            # When SPY is oversold relative to its MA (negative z), go long SPY
            if zscore < -self.entry_zscore:
                raw_signal = min(1.0, abs(zscore) / 3.0)
                reason = f"SPY undervalued: z={zscore:.2f}, price {price_to_ma*100:.1f}% from MA"
                self._current_position = "long_spread"
            elif zscore > self.entry_zscore:
                raw_signal = -min(1.0, abs(zscore) / 3.0)
                reason = f"SPY overvalued: z={zscore:.2f}, price {price_to_ma*100:.1f}% from MA"
                self._current_position = "short_spread"
            elif abs(zscore) < self.exit_zscore and self._current_position != "flat":
                raw_signal = 0.0
                reason = f"Mean reversion complete: z={zscore:.2f}"
                self._current_position = "flat"
            else:
                raw_signal = 0.0
                reason = f"No stat arb signal: z={zscore:.2f}"
        else:  # QQQ - opposite signal
            if zscore < -self.entry_zscore:
                raw_signal = -min(1.0, abs(zscore) / 3.0)  # Short QQQ when SPY long
                reason = f"QQQ leg of spread: z={zscore:.2f}"
            elif zscore > self.entry_zscore:
                raw_signal = min(1.0, abs(zscore) / 3.0)  # Long QQQ when SPY short
                reason = f"QQQ leg of spread: z={zscore:.2f}"
            else:
                raw_signal = 0.0
                reason = f"No stat arb signal for QQQ"
        
        # Confidence based on z-score magnitude and RSI confirmation
        if raw_signal != 0:
            confidence = min(1.0, 0.5 + abs(zscore) / 4.0)
            
            # RSI confirmation
            if (raw_signal > 0 and rsi < 40) or (raw_signal < 0 and rsi > 60):
                confidence += 0.15
                reason += " | RSI confirms"
        else:
            confidence = 0.2
        
        confidence = min(1.0, confidence)
        
        # Stat arb uses tight stops (mean reversion expected)
        atr = features.atr_14
        if raw_signal > 0:
            stop_loss = price - 1.5 * atr
            take_profit = price + 2 * atr
        elif raw_signal < 0:
            stop_loss = price + 1.5 * atr
            take_profit = price - 2 * atr
        else:
            stop_loss = None
            take_profit = None
        
        return Signal(
            symbol=symbol,
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
            "entry_zscore": self.entry_zscore,
            "exit_zscore": self.exit_zscore,
            "lookback_period": self.lookback_period,
            "pair": self.pair,
            "current_position": self._current_position
        }
    
    def reset(self):
        """Reset strategy state"""
        super().reset()
        self._ratio_history.clear()
        self._current_position = "flat"
