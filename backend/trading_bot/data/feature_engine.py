"""
Feature Engineering Module
Calculates 50+ technical and statistical features for trading signals
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
import math

from trading_bot.config import CONFIG, FeatureConfig
from trading_bot.data.ibkr_connector import HistoricalBar

logger = logging.getLogger(__name__)


@dataclass
class FeatureSet:
    """Complete feature set for a symbol at a point in time"""
    symbol: str
    timestamp: datetime
    
    # Price
    price: float = 0.0
    
    # Returns
    return_1d: float = 0.0
    return_5d: float = 0.0
    return_20d: float = 0.0
    return_60d: float = 0.0
    return_120d: float = 0.0
    return_252d: float = 0.0
    
    # Volatility
    volatility_20d: float = 0.0
    volatility_60d: float = 0.0
    volatility_annualized: float = 0.0
    
    # Moving Averages
    sma_10: float = 0.0
    sma_20: float = 0.0
    sma_50: float = 0.0
    sma_100: float = 0.0
    sma_200: float = 0.0
    ema_10: float = 0.0
    ema_20: float = 0.0
    ema_50: float = 0.0
    
    # Price relative to MAs
    price_to_sma_20: float = 0.0
    price_to_sma_50: float = 0.0
    price_to_sma_200: float = 0.0
    
    # MA Crossovers
    sma_20_50_cross: float = 0.0  # 1 if 20 > 50, else -1
    sma_50_200_cross: float = 0.0
    
    # Momentum Indicators
    rsi_14: float = 50.0
    rsi_oversold: float = 0.0  # 1 if RSI < 30
    rsi_overbought: float = 0.0  # 1 if RSI > 70
    
    # MACD
    macd_line: float = 0.0
    macd_signal: float = 0.0
    macd_histogram: float = 0.0
    macd_crossover: float = 0.0  # 1 if MACD crosses above signal
    
    # Bollinger Bands
    bollinger_upper: float = 0.0
    bollinger_lower: float = 0.0
    bollinger_width: float = 0.0
    bollinger_pct_b: float = 0.5  # Position within bands (0-1)
    
    # ATR (Average True Range)
    atr_14: float = 0.0
    atr_pct: float = 0.0  # ATR as % of price
    
    # ADX (Average Directional Index)
    adx_14: float = 0.0
    plus_di: float = 0.0
    minus_di: float = 0.0
    trend_strength: float = 0.0  # 1 if ADX > 25
    
    # Volume Features
    volume: int = 0
    volume_sma_20: float = 0.0
    volume_ratio: float = 1.0  # Current volume / avg volume
    obv: float = 0.0  # On-Balance Volume
    money_flow_index: float = 50.0
    
    # Price Patterns
    higher_high: float = 0.0
    lower_low: float = 0.0
    inside_day: float = 0.0
    
    # Range Features
    daily_range_pct: float = 0.0
    avg_daily_range: float = 0.0
    
    # Distance from key levels
    distance_52w_high_pct: float = 0.0
    distance_52w_low_pct: float = 0.0
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            k: v for k, v in self.__dict__.items()
            if not k.startswith('_')
        }
    
    def to_vector(self) -> List[float]:
        """Convert to feature vector for ML models"""
        exclude = {'symbol', 'timestamp', 'volume'}
        return [
            float(v) if isinstance(v, (int, float)) else 0.0
            for k, v in self.__dict__.items()
            if not k.startswith('_') and k not in exclude
        ]


class FeatureEngine:
    """
    Calculates technical indicators and features from price data
    All calculations are point-in-time to avoid look-ahead bias
    """
    
    def __init__(self, config: FeatureConfig = CONFIG.features):
        self.config = config
        logger.info("FeatureEngine initialized")
    
    def calculate_features(
        self,
        bars: List[HistoricalBar],
        current_idx: Optional[int] = None
    ) -> Optional[FeatureSet]:
        """
        Calculate all features for a given point in time
        
        Args:
            bars: List of historical bars (oldest first)
            current_idx: Index to calculate features for (default: last bar)
        
        Returns: FeatureSet or None if insufficient data
        """
        if len(bars) < 252:  # Need at least 1 year of data
            logger.warning(f"Insufficient data: {len(bars)} bars (need 252+)")
            return None
        
        idx = current_idx if current_idx is not None else len(bars) - 1
        
        if idx < 252:
            return None
        
        bar = bars[idx]
        closes = [b.close for b in bars[:idx+1]]
        highs = [b.high for b in bars[:idx+1]]
        lows = [b.low for b in bars[:idx+1]]
        volumes = [b.volume for b in bars[:idx+1]]
        
        features = FeatureSet(
            symbol=bar.symbol,
            timestamp=bar.timestamp,
            price=bar.close,
            volume=bar.volume
        )
        
        # ===== Returns =====
        features.return_1d = self._calculate_return(closes, 1)
        features.return_5d = self._calculate_return(closes, 5)
        features.return_20d = self._calculate_return(closes, 20)
        features.return_60d = self._calculate_return(closes, 60)
        features.return_120d = self._calculate_return(closes, 120)
        features.return_252d = self._calculate_return(closes, 252)
        
        # ===== Volatility =====
        features.volatility_20d = self._calculate_volatility(closes, 20)
        features.volatility_60d = self._calculate_volatility(closes, 60)
        features.volatility_annualized = features.volatility_20d * math.sqrt(252)
        
        # ===== Moving Averages =====
        features.sma_10 = self._sma(closes, 10)
        features.sma_20 = self._sma(closes, 20)
        features.sma_50 = self._sma(closes, 50)
        features.sma_100 = self._sma(closes, 100)
        features.sma_200 = self._sma(closes, 200)
        
        features.ema_10 = self._ema(closes, 10)
        features.ema_20 = self._ema(closes, 20)
        features.ema_50 = self._ema(closes, 50)
        
        # Price relative to MAs
        if features.sma_20 > 0:
            features.price_to_sma_20 = bar.close / features.sma_20 - 1
        if features.sma_50 > 0:
            features.price_to_sma_50 = bar.close / features.sma_50 - 1
        if features.sma_200 > 0:
            features.price_to_sma_200 = bar.close / features.sma_200 - 1
        
        # MA Crossovers
        features.sma_20_50_cross = 1.0 if features.sma_20 > features.sma_50 else -1.0
        features.sma_50_200_cross = 1.0 if features.sma_50 > features.sma_200 else -1.0
        
        # ===== RSI =====
        features.rsi_14 = self._calculate_rsi(closes, 14)
        features.rsi_oversold = 1.0 if features.rsi_14 < 30 else 0.0
        features.rsi_overbought = 1.0 if features.rsi_14 > 70 else 0.0
        
        # ===== MACD =====
        macd_result = self._calculate_macd(closes)
        features.macd_line = macd_result['macd']
        features.macd_signal = macd_result['signal']
        features.macd_histogram = macd_result['histogram']
        features.macd_crossover = macd_result['crossover']
        
        # ===== Bollinger Bands =====
        bb_result = self._calculate_bollinger(closes, 20, 2.0)
        features.bollinger_upper = bb_result['upper']
        features.bollinger_lower = bb_result['lower']
        features.bollinger_width = bb_result['width']
        features.bollinger_pct_b = bb_result['pct_b']
        
        # ===== ATR =====
        features.atr_14 = self._calculate_atr(highs, lows, closes, 14)
        if bar.close > 0:
            features.atr_pct = features.atr_14 / bar.close
        
        # ===== ADX =====
        adx_result = self._calculate_adx(highs, lows, closes, 14)
        features.adx_14 = adx_result['adx']
        features.plus_di = adx_result['plus_di']
        features.minus_di = adx_result['minus_di']
        features.trend_strength = 1.0 if features.adx_14 > 25 else 0.0
        
        # ===== Volume Features =====
        features.volume_sma_20 = self._sma(volumes, 20)
        if features.volume_sma_20 > 0:
            features.volume_ratio = bar.volume / features.volume_sma_20
        
        features.obv = self._calculate_obv(closes, volumes)
        features.money_flow_index = self._calculate_mfi(highs, lows, closes, volumes, 14)
        
        # ===== Price Patterns =====
        if idx >= 1:
            prev_bar = bars[idx-1]
            features.higher_high = 1.0 if bar.high > prev_bar.high else 0.0
            features.lower_low = 1.0 if bar.low < prev_bar.low else 0.0
            features.inside_day = 1.0 if (bar.high < prev_bar.high and bar.low > prev_bar.low) else 0.0
        
        # ===== Range Features =====
        if bar.low > 0:
            features.daily_range_pct = (bar.high - bar.low) / bar.low
        features.avg_daily_range = self._calculate_avg_range(highs, lows, 20)
        
        # ===== 52-week High/Low =====
        high_252 = max(highs[-252:])
        low_252 = min(lows[-252:])
        if high_252 > 0:
            features.distance_52w_high_pct = (bar.close - high_252) / high_252
        if low_252 > 0:
            features.distance_52w_low_pct = (bar.close - low_252) / low_252
        
        return features
    
    def calculate_features_series(
        self,
        bars: List[HistoricalBar],
        start_idx: int = 252
    ) -> List[FeatureSet]:
        """
        Calculate features for a series of bars
        
        Args:
            bars: List of historical bars
            start_idx: Index to start calculating from
        
        Returns: List of FeatureSet objects
        """
        features_list = []
        
        for i in range(start_idx, len(bars)):
            features = self.calculate_features(bars, i)
            if features:
                features_list.append(features)
        
        logger.info(f"Calculated features for {len(features_list)} bars")
        return features_list
    
    # ===== Helper Methods =====
    
    def _calculate_return(self, prices: List[float], period: int) -> float:
        """Calculate return over period"""
        if len(prices) <= period or prices[-period-1] == 0:
            return 0.0
        return (prices[-1] - prices[-period-1]) / prices[-period-1]
    
    def _calculate_volatility(self, prices: List[float], period: int) -> float:
        """Calculate rolling volatility (std of returns)"""
        if len(prices) < period + 1:
            return 0.0
        
        returns = [
            (prices[i] - prices[i-1]) / prices[i-1]
            for i in range(-period, 0)
            if prices[i-1] != 0
        ]
        
        if len(returns) < 2:
            return 0.0
        
        mean_ret = sum(returns) / len(returns)
        variance = sum((r - mean_ret) ** 2 for r in returns) / (len(returns) - 1)
        return math.sqrt(variance)
    
    def _sma(self, values: List[float], period: int) -> float:
        """Simple Moving Average"""
        if len(values) < period:
            return 0.0
        return sum(values[-period:]) / period
    
    def _ema(self, values: List[float], period: int) -> float:
        """Exponential Moving Average"""
        if len(values) < period:
            return 0.0
        
        multiplier = 2 / (period + 1)
        ema = sum(values[:period]) / period  # Start with SMA
        
        for price in values[period:]:
            ema = (price - ema) * multiplier + ema
        
        return ema
    
    def _calculate_rsi(self, prices: List[float], period: int = 14) -> float:
        """Relative Strength Index"""
        if len(prices) < period + 1:
            return 50.0
        
        gains = []
        losses = []
        
        for i in range(-period, 0):
            change = prices[i] - prices[i-1]
            if change >= 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(change))
        
        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))
    
    def _calculate_macd(self, prices: List[float]) -> Dict:
        """MACD indicator"""
        fast = self.config.macd_fast
        slow = self.config.macd_slow
        signal_period = self.config.macd_signal
        
        ema_fast = self._ema(prices, fast)
        ema_slow = self._ema(prices, slow)
        macd_line = ema_fast - ema_slow
        
        # Calculate signal line (EMA of MACD)
        if len(prices) >= slow + signal_period:
            macd_values = []
            for i in range(slow, len(prices)):
                ef = self._ema(prices[:i+1], fast)
                es = self._ema(prices[:i+1], slow)
                macd_values.append(ef - es)
            
            signal_line = self._ema(macd_values, signal_period) if len(macd_values) >= signal_period else 0
        else:
            signal_line = 0
        
        histogram = macd_line - signal_line
        
        # Crossover signal (simplified)
        crossover = 1.0 if histogram > 0 else -1.0
        
        return {
            'macd': macd_line,
            'signal': signal_line,
            'histogram': histogram,
            'crossover': crossover
        }
    
    def _calculate_bollinger(self, prices: List[float], period: int = 20, std_mult: float = 2.0) -> Dict:
        """Bollinger Bands"""
        if len(prices) < period:
            return {'upper': 0, 'lower': 0, 'width': 0, 'pct_b': 0.5}
        
        sma = self._sma(prices, period)
        
        # Standard deviation
        variance = sum((p - sma) ** 2 for p in prices[-period:]) / period
        std = math.sqrt(variance)
        
        upper = sma + std_mult * std
        lower = sma - std_mult * std
        width = (upper - lower) / sma if sma > 0 else 0
        
        # %B: position within bands
        current_price = prices[-1]
        if upper != lower:
            pct_b = (current_price - lower) / (upper - lower)
        else:
            pct_b = 0.5
        
        return {
            'upper': upper,
            'lower': lower,
            'width': width,
            'pct_b': max(0, min(1, pct_b))
        }
    
    def _calculate_atr(
        self,
        highs: List[float],
        lows: List[float],
        closes: List[float],
        period: int = 14
    ) -> float:
        """Average True Range"""
        if len(closes) < period + 1:
            return 0.0
        
        true_ranges = []
        for i in range(-period, 0):
            high_low = highs[i] - lows[i]
            high_close = abs(highs[i] - closes[i-1])
            low_close = abs(lows[i] - closes[i-1])
            true_ranges.append(max(high_low, high_close, low_close))
        
        return sum(true_ranges) / len(true_ranges)
    
    def _calculate_adx(
        self,
        highs: List[float],
        lows: List[float],
        closes: List[float],
        period: int = 14
    ) -> Dict:
        """Average Directional Index"""
        if len(closes) < period + 1:
            return {'adx': 0, 'plus_di': 0, 'minus_di': 0}
        
        plus_dm_list = []
        minus_dm_list = []
        tr_list = []
        
        for i in range(-period, 0):
            high_diff = highs[i] - highs[i-1]
            low_diff = lows[i-1] - lows[i]
            
            plus_dm = high_diff if high_diff > low_diff and high_diff > 0 else 0
            minus_dm = low_diff if low_diff > high_diff and low_diff > 0 else 0
            
            plus_dm_list.append(plus_dm)
            minus_dm_list.append(minus_dm)
            
            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i-1]),
                abs(lows[i] - closes[i-1])
            )
            tr_list.append(tr)
        
        atr = sum(tr_list) / period
        
        if atr == 0:
            return {'adx': 0, 'plus_di': 0, 'minus_di': 0}
        
        plus_di = 100 * sum(plus_dm_list) / period / atr
        minus_di = 100 * sum(minus_dm_list) / period / atr
        
        di_sum = plus_di + minus_di
        if di_sum == 0:
            dx = 0
        else:
            dx = 100 * abs(plus_di - minus_di) / di_sum
        
        # ADX is typically smoothed, but we'll use DX for simplicity
        adx = dx
        
        return {
            'adx': adx,
            'plus_di': plus_di,
            'minus_di': minus_di
        }
    
    def _calculate_obv(self, prices: List[float], volumes: List[int]) -> float:
        """On-Balance Volume (normalized)"""
        if len(prices) < 2:
            return 0.0
        
        obv = 0
        for i in range(1, len(prices)):
            if prices[i] > prices[i-1]:
                obv += volumes[i]
            elif prices[i] < prices[i-1]:
                obv -= volumes[i]
        
        # Normalize to recent average volume
        avg_vol = sum(volumes[-20:]) / 20 if len(volumes) >= 20 else sum(volumes) / len(volumes)
        return obv / avg_vol if avg_vol > 0 else 0
    
    def _calculate_mfi(
        self,
        highs: List[float],
        lows: List[float],
        closes: List[float],
        volumes: List[int],
        period: int = 14
    ) -> float:
        """Money Flow Index"""
        if len(closes) < period + 1:
            return 50.0
        
        positive_flow = 0
        negative_flow = 0
        
        for i in range(-period, 0):
            typical_price = (highs[i] + lows[i] + closes[i]) / 3
            prev_typical = (highs[i-1] + lows[i-1] + closes[i-1]) / 3
            raw_flow = typical_price * volumes[i]
            
            if typical_price > prev_typical:
                positive_flow += raw_flow
            else:
                negative_flow += raw_flow
        
        if negative_flow == 0:
            return 100.0
        
        mfi = 100 - (100 / (1 + positive_flow / negative_flow))
        return mfi
    
    def _calculate_avg_range(
        self,
        highs: List[float],
        lows: List[float],
        period: int = 20
    ) -> float:
        """Average daily range as percentage"""
        if len(highs) < period:
            return 0.0
        
        ranges = [
            (highs[i] - lows[i]) / lows[i] if lows[i] > 0 else 0
            for i in range(-period, 0)
        ]
        
        return sum(ranges) / len(ranges)
