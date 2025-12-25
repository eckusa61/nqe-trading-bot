"""
Signal Levels Calculator
Calculates optimal entry/exit levels for trading signals
"""
import logging
import numpy as np
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


class SignalStrength(Enum):
    STRONG_BUY = "strong_buy"
    BUY = "buy"
    WEAK_BUY = "weak_buy"
    NEUTRAL = "neutral"
    WEAK_SELL = "weak_sell"
    SELL = "sell"
    STRONG_SELL = "strong_sell"


@dataclass
class SignalLevel:
    symbol: str
    signal_strength: SignalStrength
    current_price: float
    
    # Entry levels
    best_buy_price: float
    aggressive_buy_price: float
    conservative_buy_price: float
    
    # Exit levels for long
    take_profit_1: float
    take_profit_2: float
    take_profit_3: float
    stop_loss: float
    
    # Short levels
    best_sell_price: float
    short_take_profit: float
    short_stop_loss: float
    
    # Support/Resistance
    support_levels: List[float] = field(default_factory=list)
    resistance_levels: List[float] = field(default_factory=list)
    
    # Indicators
    rsi: float = 50.0
    macd_signal: str = "neutral"
    trend: str = "sideways"
    volatility: float = 0.0
    
    # Risk metrics
    risk_reward_ratio: float = 0.0
    position_size_pct: float = 0.0
    
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict:
        return {
            "symbol": self.symbol,
            "signal_strength": self.signal_strength.value,
            "current_price": round(self.current_price, 2),
            "entry_levels": {
                "best_buy": round(self.best_buy_price, 2),
                "aggressive_buy": round(self.aggressive_buy_price, 2),
                "conservative_buy": round(self.conservative_buy_price, 2),
            },
            "exit_levels": {
                "take_profit_1": round(self.take_profit_1, 2),
                "take_profit_2": round(self.take_profit_2, 2),
                "take_profit_3": round(self.take_profit_3, 2),
                "stop_loss": round(self.stop_loss, 2),
            },
            "short_levels": {
                "best_sell": round(self.best_sell_price, 2),
                "take_profit": round(self.short_take_profit, 2),
                "stop_loss": round(self.short_stop_loss, 2),
            },
            "support_levels": [round(s, 2) for s in self.support_levels],
            "resistance_levels": [round(r, 2) for r in self.resistance_levels],
            "indicators": {
                "rsi": round(self.rsi, 1),
                "macd_signal": self.macd_signal,
                "trend": self.trend,
                "volatility_pct": round(self.volatility * 100, 2),
            },
            "risk_metrics": {
                "risk_reward_ratio": round(self.risk_reward_ratio, 2),
                "suggested_position_pct": round(self.position_size_pct, 1),
            },
            "timestamp": self.timestamp.isoformat()
        }


class SignalLevelsCalculator:
    """
    Calculates optimal trading levels for each symbol
    """
    
    def __init__(
        self,
        atr_multiplier_sl: float = 2.0,
        atr_multiplier_tp: float = 3.0,
        risk_per_trade_pct: float = 1.0
    ):
        self.atr_multiplier_sl = atr_multiplier_sl
        self.atr_multiplier_tp = atr_multiplier_tp
        self.risk_per_trade_pct = risk_per_trade_pct
        
        self.signal_cache: Dict[str, SignalLevel] = {}
        logger.info("Signal Levels Calculator initialized")
    
    def calculate_atr(self, high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> float:
        """Calculate Average True Range"""
        if len(close) < period + 1:
            return 0.0
        
        tr1 = high[1:] - low[1:]
        tr2 = np.abs(high[1:] - close[:-1])
        tr3 = np.abs(low[1:] - close[:-1])
        tr = np.maximum(tr1, np.maximum(tr2, tr3))
        
        return np.mean(tr[-period:])
    
    def calculate_rsi(self, close: np.ndarray, period: int = 14) -> float:
        """Calculate RSI"""
        if len(close) < period + 1:
            return 50.0
        
        deltas = np.diff(close)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))
    
    def find_support_resistance(self, high: np.ndarray, low: np.ndarray, close: np.ndarray) -> Tuple[List[float], List[float]]:
        """Find support and resistance levels using pivot points"""
        if len(close) < 20:
            return [], []
        
        supports = []
        resistances = []
        
        # Recent pivots
        for i in range(5, len(close) - 5):
            # Pivot high (resistance)
            if high[i] == max(high[i-5:i+6]):
                resistances.append(high[i])
            # Pivot low (support)
            if low[i] == min(low[i-5:i+6]):
                supports.append(low[i])
        
        # Keep most recent and relevant levels
        current = close[-1]
        supports = sorted([s for s in supports if s < current], reverse=True)[:3]
        resistances = sorted([r for r in resistances if r > current])[:3]
        
        return supports, resistances
    
    def determine_signal_strength(self, rsi: float, macd_signal: str, trend: str, volatility: float) -> SignalStrength:
        """Determine overall signal strength"""
        score = 0
        
        # RSI contribution
        if rsi < 30:
            score += 2  # Oversold - bullish
        elif rsi < 40:
            score += 1
        elif rsi > 70:
            score -= 2  # Overbought - bearish
        elif rsi > 60:
            score -= 1
        
        # MACD contribution
        if macd_signal == "bullish":
            score += 2
        elif macd_signal == "bearish":
            score -= 2
        
        # Trend contribution
        if trend == "uptrend":
            score += 1
        elif trend == "downtrend":
            score -= 1
        
        # Map score to signal strength
        if score >= 4:
            return SignalStrength.STRONG_BUY
        elif score >= 2:
            return SignalStrength.BUY
        elif score >= 1:
            return SignalStrength.WEAK_BUY
        elif score <= -4:
            return SignalStrength.STRONG_SELL
        elif score <= -2:
            return SignalStrength.SELL
        elif score <= -1:
            return SignalStrength.WEAK_SELL
        else:
            return SignalStrength.NEUTRAL
    
    def determine_trend(self, close: np.ndarray) -> str:
        """Determine trend direction using moving averages"""
        if len(close) < 50:
            return "sideways"
        
        sma_20 = np.mean(close[-20:])
        sma_50 = np.mean(close[-50:])
        current = close[-1]
        
        if current > sma_20 > sma_50:
            return "uptrend"
        elif current < sma_20 < sma_50:
            return "downtrend"
        else:
            return "sideways"
    
    def calculate_macd_signal(self, close: np.ndarray) -> str:
        """Simple MACD signal"""
        if len(close) < 26:
            return "neutral"
        
        ema_12 = self._ema(close, 12)
        ema_26 = self._ema(close, 26)
        macd = ema_12 - ema_26
        signal = self._ema(macd, 9)
        
        if macd[-1] > signal[-1] and macd[-2] <= signal[-2]:
            return "bullish"
        elif macd[-1] < signal[-1] and macd[-2] >= signal[-2]:
            return "bearish"
        elif macd[-1] > signal[-1]:
            return "bullish_trend"
        elif macd[-1] < signal[-1]:
            return "bearish_trend"
        else:
            return "neutral"
    
    def _ema(self, data: np.ndarray, period: int) -> np.ndarray:
        """Calculate EMA"""
        ema = np.zeros_like(data)
        multiplier = 2 / (period + 1)
        ema[period-1] = np.mean(data[:period])
        for i in range(period, len(data)):
            ema[i] = (data[i] - ema[i-1]) * multiplier + ema[i-1]
        return ema
    
    def calculate_signal_levels(self, symbol: str, market_data: Dict) -> SignalLevel:
        """
        Calculate all signal levels for a symbol
        """
        close = np.array(market_data.get('close', []))
        high = np.array(market_data.get('high', close))
        low = np.array(market_data.get('low', close))
        
        if len(close) < 20:
            return self._empty_signal(symbol)
        
        current_price = close[-1]
        
        # Calculate indicators
        atr = self.calculate_atr(high, low, close)
        rsi = self.calculate_rsi(close)
        trend = self.determine_trend(close)
        macd_signal = self.calculate_macd_signal(close)
        volatility = np.std(np.diff(close) / close[:-1]) if len(close) > 1 else 0
        
        # Find support/resistance
        supports, resistances = self.find_support_resistance(high, low, close)
        
        # Determine signal strength
        signal_strength = self.determine_signal_strength(rsi, macd_signal, trend, volatility)
        
        # Calculate entry levels
        best_buy = current_price - atr * 0.5  # Slight pullback
        aggressive_buy = current_price  # At market
        conservative_buy = current_price - atr  # Wait for larger pullback
        
        # Take profit levels (Fibonacci-style)
        stop_loss = current_price - atr * self.atr_multiplier_sl
        take_profit_1 = current_price + atr * 1.0  # 1:0.5 R:R
        take_profit_2 = current_price + atr * 2.0  # 1:1 R:R
        take_profit_3 = current_price + atr * self.atr_multiplier_tp  # 1:1.5 R:R
        
        # Short levels
        best_sell = current_price + atr * 0.5
        short_tp = current_price - atr * 2.0
        short_sl = current_price + atr * self.atr_multiplier_sl
        
        # Risk/reward calculation
        risk = current_price - stop_loss
        reward = take_profit_2 - current_price
        risk_reward = reward / risk if risk > 0 else 0
        
        # Position size based on risk
        position_size_pct = self.risk_per_trade_pct / (risk / current_price * 100) if risk > 0 else 0
        position_size_pct = min(position_size_pct, 10)  # Cap at 10%
        
        signal = SignalLevel(
            symbol=symbol,
            signal_strength=signal_strength,
            current_price=current_price,
            best_buy_price=best_buy,
            aggressive_buy_price=aggressive_buy,
            conservative_buy_price=conservative_buy,
            take_profit_1=take_profit_1,
            take_profit_2=take_profit_2,
            take_profit_3=take_profit_3,
            stop_loss=stop_loss,
            best_sell_price=best_sell,
            short_take_profit=short_tp,
            short_stop_loss=short_sl,
            support_levels=supports,
            resistance_levels=resistances,
            rsi=rsi,
            macd_signal=macd_signal,
            trend=trend,
            volatility=volatility,
            risk_reward_ratio=risk_reward,
            position_size_pct=position_size_pct
        )
        
        self.signal_cache[symbol] = signal
        return signal
    
    def _empty_signal(self, symbol: str) -> SignalLevel:
        return SignalLevel(
            symbol=symbol,
            signal_strength=SignalStrength.NEUTRAL,
            current_price=0,
            best_buy_price=0,
            aggressive_buy_price=0,
            conservative_buy_price=0,
            take_profit_1=0,
            take_profit_2=0,
            take_profit_3=0,
            stop_loss=0,
            best_sell_price=0,
            short_take_profit=0,
            short_stop_loss=0
        )
    
    def get_best_signals(self, limit: int = 5) -> Dict:
        """Get best buy and sell signals"""
        buy_signals = []
        sell_signals = []
        
        for symbol, signal in self.signal_cache.items():
            if signal.signal_strength in [SignalStrength.STRONG_BUY, SignalStrength.BUY]:
                buy_signals.append(signal)
            elif signal.signal_strength in [SignalStrength.STRONG_SELL, SignalStrength.SELL]:
                sell_signals.append(signal)
        
        # Sort by risk/reward
        buy_signals.sort(key=lambda x: x.risk_reward_ratio, reverse=True)
        sell_signals.sort(key=lambda x: x.risk_reward_ratio, reverse=True)
        
        return {
            "best_buys": [s.to_dict() for s in buy_signals[:limit]],
            "best_sells": [s.to_dict() for s in sell_signals[:limit]],
            "total_symbols_analyzed": len(self.signal_cache)
        }
    
    def get_all_signals(self) -> List[Dict]:
        """Get all cached signals"""
        return [signal.to_dict() for signal in self.signal_cache.values()]
