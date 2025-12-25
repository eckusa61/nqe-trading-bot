"""
Base Strategy Class
All strategies inherit from this base class
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from enum import Enum
import logging

from trading_bot.data.feature_engine import FeatureSet

logger = logging.getLogger(__name__)


class SignalType(Enum):
    """Signal types"""
    LONG = "long"
    SHORT = "short"
    FLAT = "flat"


@dataclass
class Signal:
    """
    Trading signal from a strategy
    signal: -1 (full short) to +1 (full long), 0 = no position
    confidence: 0 to 1, how confident the strategy is
    """
    symbol: str
    signal: float  # -1 to +1
    confidence: float  # 0 to 1
    strategy: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    reason: str = ""
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    
    @property
    def signal_type(self) -> SignalType:
        if self.signal > 0.1:
            return SignalType.LONG
        elif self.signal < -0.1:
            return SignalType.SHORT
        return SignalType.FLAT
    
    def to_dict(self) -> Dict:
        return {
            "symbol": self.symbol,
            "signal": self.signal,
            "confidence": self.confidence,
            "strategy": self.strategy,
            "timestamp": self.timestamp.isoformat(),
            "reason": self.reason,
            "signal_type": self.signal_type.value,
            "entry_price": self.entry_price,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit
        }


@dataclass
class StrategyResult:
    """Result of strategy evaluation across multiple symbols"""
    strategy_name: str
    signals: List[Signal]
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict = field(default_factory=dict)
    
    @property
    def long_signals(self) -> List[Signal]:
        return [s for s in self.signals if s.signal_type == SignalType.LONG]
    
    @property
    def short_signals(self) -> List[Signal]:
        return [s for s in self.signals if s.signal_type == SignalType.SHORT]


class BaseStrategy(ABC):
    """
    Abstract base class for all trading strategies
    
    Each strategy must implement:
    - generate_signal(): Generate signal for a single symbol
    - get_parameters(): Return strategy parameters
    """
    
    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
        self.enabled = True
        self._last_signals: Dict[str, Signal] = {}
        logger.info(f"Strategy initialized: {name}")
    
    @abstractmethod
    def generate_signal(self, features: FeatureSet, historical_features: Optional[List[FeatureSet]] = None) -> Signal:
        """
        Generate trading signal for a single symbol
        
        Args:
            features: Current feature set for the symbol
            historical_features: Optional list of historical features for lookback
        
        Returns:
            Signal object with signal strength and confidence
        """
        pass
    
    @abstractmethod
    def get_parameters(self) -> Dict:
        """Return strategy parameters for transparency"""
        pass
    
    def evaluate(self, features_list: List[FeatureSet], historical_data: Optional[Dict[str, List[FeatureSet]]] = None) -> StrategyResult:
        """
        Evaluate strategy across multiple symbols
        
        Args:
            features_list: List of current features for each symbol
            historical_data: Optional dict of {symbol: [historical_features]}
        
        Returns:
            StrategyResult containing all signals
        """
        signals = []
        
        for features in features_list:
            if not self.enabled:
                continue
            
            try:
                hist = historical_data.get(features.symbol) if historical_data else None
                signal = self.generate_signal(features, hist)
                signals.append(signal)
                self._last_signals[features.symbol] = signal
            except Exception as e:
                logger.error(f"Error generating signal for {features.symbol} in {self.name}: {e}")
                # Generate neutral signal on error
                signals.append(Signal(
                    symbol=features.symbol,
                    signal=0.0,
                    confidence=0.0,
                    strategy=self.name,
                    reason=f"Error: {str(e)}"
                ))
        
        return StrategyResult(
            strategy_name=self.name,
            signals=signals,
            metadata={"parameters": self.get_parameters()}
        )
    
    def get_last_signal(self, symbol: str) -> Optional[Signal]:
        """Get the last generated signal for a symbol"""
        return self._last_signals.get(symbol)
    
    def reset(self):
        """Reset strategy state"""
        self._last_signals.clear()


class StrategyRegistry:
    """Registry for managing multiple strategies"""
    
    def __init__(self):
        self._strategies: Dict[str, BaseStrategy] = {}
    
    def register(self, strategy: BaseStrategy):
        """Register a strategy"""
        self._strategies[strategy.name] = strategy
        logger.info(f"Registered strategy: {strategy.name}")
    
    def unregister(self, name: str):
        """Unregister a strategy"""
        if name in self._strategies:
            del self._strategies[name]
    
    def get(self, name: str) -> Optional[BaseStrategy]:
        """Get a strategy by name"""
        return self._strategies.get(name)
    
    def get_all(self) -> List[BaseStrategy]:
        """Get all registered strategies"""
        return list(self._strategies.values())
    
    def get_enabled(self) -> List[BaseStrategy]:
        """Get all enabled strategies"""
        return [s for s in self._strategies.values() if s.enabled]
    
    def evaluate_all(self, features_list: List[FeatureSet], historical_data: Optional[Dict[str, List[FeatureSet]]] = None) -> List[StrategyResult]:
        """Evaluate all enabled strategies"""
        results = []
        for strategy in self.get_enabled():
            result = strategy.evaluate(features_list, historical_data)
            results.append(result)
        return results


# Global strategy registry
strategy_registry = StrategyRegistry()
