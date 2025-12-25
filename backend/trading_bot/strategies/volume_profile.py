"""
Volume Profile Strategy
Trades based on volume at price levels (support/resistance)
"""
import logging
import numpy as np
from typing import Dict, List, Tuple
from datetime import datetime, timezone
from collections import defaultdict

from .base_strategy import BaseStrategy, Signal, StrategyResult

logger = logging.getLogger(__name__)


class VolumeProfileStrategy(BaseStrategy):
    """
    Volume Profile Trading Strategy
    
    Logic:
    1. Build volume profile (volume at each price level)
    2. Identify high volume nodes (HVN) - support/resistance
    3. Identify low volume nodes (LVN) - breakout zones
    4. Trade bounces off HVN, breakouts through LVN
    """
    
    name = "VolumeProfile"
    
    def __init__(
        self,
        lookback: int = 100,
        num_bins: int = 50,
        hvn_threshold: float = 1.5,
        lvn_threshold: float = 0.5
    ):
        super().__init__()
        self.lookback = lookback
        self.num_bins = num_bins
        self.hvn_threshold = hvn_threshold
        self.lvn_threshold = lvn_threshold
        logger.info("Volume Profile strategy initialized")
    
    def build_volume_profile(self, close: np.ndarray, volume: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Build volume profile histogram"""
        price_min = np.min(close)
        price_max = np.max(close)
        
        # Create price bins
        bins = np.linspace(price_min, price_max, self.num_bins + 1)
        bin_centers = (bins[:-1] + bins[1:]) / 2
        
        # Assign volume to bins
        volume_profile = np.zeros(self.num_bins)
        for i, price in enumerate(close):
            bin_idx = np.digitize(price, bins) - 1
            bin_idx = min(max(bin_idx, 0), self.num_bins - 1)
            volume_profile[bin_idx] += volume[i]
        
        return bin_centers, volume_profile
    
    def find_nodes(self, volume_profile: np.ndarray) -> Tuple[List[int], List[int]]:
        """Find high and low volume nodes"""
        avg_volume = np.mean(volume_profile)
        
        hvn_indices = []
        lvn_indices = []
        
        for i, vol in enumerate(volume_profile):
            if vol > avg_volume * self.hvn_threshold:
                hvn_indices.append(i)
            elif vol < avg_volume * self.lvn_threshold:
                lvn_indices.append(i)
        
        return hvn_indices, lvn_indices
    
    def find_poc(self, volume_profile: np.ndarray) -> int:
        """Find Point of Control (highest volume price level)"""
        return np.argmax(volume_profile)
    
    def generate_signal(self, symbol: str, features: Dict) -> StrategyResult:
        """Generate volume profile signal"""
        close = np.array(features.get('close', []))
        volume = np.array(features.get('volume', []))
        
        if len(close) < self.lookback:
            return self._no_signal(symbol)
        
        # Use lookback period
        close_lb = close[-self.lookback:]
        volume_lb = volume[-self.lookback:]
        
        # Build volume profile
        bin_centers, volume_profile = self.build_volume_profile(close_lb, volume_lb)
        
        # Find nodes
        hvn_indices, lvn_indices = self.find_nodes(volume_profile)
        poc_idx = self.find_poc(volume_profile)
        
        current_price = close[-1]
        prev_price = close[-2]
        
        # Find nearest levels
        hvn_prices = [bin_centers[i] for i in hvn_indices]
        lvn_prices = [bin_centers[i] for i in lvn_indices]
        poc_price = bin_centers[poc_idx]
        
        signal_value = 0.0
        confidence = 0.0
        level_type = "none"
        nearest_level = None
        
        # Check proximity to POC
        poc_distance = abs(current_price - poc_price) / current_price
        if poc_distance < 0.005:  # Within 0.5% of POC
            # POC acts as magnet - expect mean reversion
            if current_price > poc_price:
                signal_value = -0.3
            else:
                signal_value = 0.3
            confidence = 0.5
            level_type = "at_poc"
            nearest_level = poc_price
        
        # Check HVN (support/resistance)
        for hvn_price in hvn_prices:
            distance = abs(current_price - hvn_price) / current_price
            if distance < 0.008:  # Within 0.8%
                # Bounce off HVN
                if current_price > hvn_price and prev_price < hvn_price:
                    # Bounced up from support
                    signal_value = 0.6
                    confidence = 0.65
                    level_type = "hvn_support_bounce"
                    nearest_level = hvn_price
                elif current_price < hvn_price and prev_price > hvn_price:
                    # Rejected from resistance
                    signal_value = -0.6
                    confidence = 0.65
                    level_type = "hvn_resistance_reject"
                    nearest_level = hvn_price
                break
        
        # Check LVN (breakout zones)
        for lvn_price in lvn_prices:
            distance = abs(current_price - lvn_price) / current_price
            if distance < 0.005:  # Within 0.5%
                # Breakout through LVN
                if current_price > lvn_price and prev_price < lvn_price:
                    # Bullish breakout
                    signal_value = 0.7
                    confidence = 0.6
                    level_type = "lvn_breakout_up"
                    nearest_level = lvn_price
                elif current_price < lvn_price and prev_price > lvn_price:
                    # Bearish breakout
                    signal_value = -0.7
                    confidence = 0.6
                    level_type = "lvn_breakout_down"
                    nearest_level = lvn_price
                break
        
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
                "poc_price": poc_price,
                "hvn_count": len(hvn_prices),
                "lvn_count": len(lvn_prices),
                "level_type": level_type,
                "nearest_level": nearest_level,
                "current_price": current_price
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
