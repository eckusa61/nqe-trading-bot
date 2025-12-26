"""
Self-Learning Module - Walk-forward optimization and strategy adaptation
"""
import logging
import numpy as np
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
import json
import os

logger = logging.getLogger(__name__)


@dataclass
class StrategyPerformance:
    strategy_name: str
    win_rate: float
    profit_factor: float
    sharpe_ratio: float
    max_drawdown: float
    total_trades: int
    total_pnl: float
    avg_trade_pnl: float
    period_start: datetime
    period_end: datetime
    
    def to_dict(self) -> Dict:
        return {
            "strategy_name": self.strategy_name,
            "win_rate": round(self.win_rate, 2),
            "profit_factor": round(self.profit_factor, 2),
            "sharpe_ratio": round(self.sharpe_ratio, 2),
            "max_drawdown": round(self.max_drawdown, 2),
            "total_trades": self.total_trades,
            "total_pnl": round(self.total_pnl, 2),
            "avg_trade_pnl": round(self.avg_trade_pnl, 2),
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat()
        }


@dataclass
class LearningCycle:
    cycle_id: int
    cycle_type: str  # 'daily', 'weekly', 'monthly'
    start_time: datetime
    end_time: Optional[datetime] = None
    strategies_evaluated: List[str] = field(default_factory=list)
    weight_adjustments: Dict[str, float] = field(default_factory=dict)
    parameters_optimized: Dict[str, Dict] = field(default_factory=dict)
    performance_before: Dict[str, float] = field(default_factory=dict)
    performance_after: Dict[str, float] = field(default_factory=dict)
    status: str = "running"
    
    def to_dict(self) -> Dict:
        return {
            "cycle_id": self.cycle_id,
            "cycle_type": self.cycle_type,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "strategies_evaluated": self.strategies_evaluated,
            "weight_adjustments": self.weight_adjustments,
            "parameters_optimized": self.parameters_optimized,
            "performance_before": self.performance_before,
            "performance_after": self.performance_after,
            "status": self.status
        }


class SelfLearningEngine:
    """
    Self-Learning System for strategy optimization
    
    Features:
    1. Walk-forward optimization
    2. Strategy performance tracking
    3. Automatic weight adjustment
    4. Parameter optimization
    5. Regime-based learning
    """
    
    def __init__(
        self,
        data_dir: str = "learning_data",
        min_trades_for_evaluation: int = 10,
        learning_rate: float = 0.1
    ):
        self.data_dir = data_dir
        self.min_trades_for_evaluation = min_trades_for_evaluation
        self.learning_rate = learning_rate
        
        # State
        self.strategy_weights: Dict[str, float] = {}
        self.strategy_performance: Dict[str, StrategyPerformance] = {}
        self.learning_cycles: List[LearningCycle] = []
        self.trade_history: List[Dict] = []
        self.cycle_counter = 0
        
        # Default weights
        self.default_strategies = [
            'MeanReversion', 'Momentum', 'VolatilityBreakout',
            'TrendFollowing', 'StatArb', 'PairsTrading',
            'Breakout', 'RSIDivergence', 'MACDCrossover',
            'BollingerSqueeze', 'VWAPReversion', 'ORB',
            'GapTrading', 'VolumeProfile', 'SectorRotation'
        ]
        
        self._initialize_weights()
        logger.info("Self-Learning Engine initialized")
    
    def _initialize_weights(self):
        """Initialize equal weights for all strategies"""
        for strategy in self.default_strategies:
            self.strategy_weights[strategy] = 1.0 / len(self.default_strategies)
    
    def record_trade(self, trade: Dict):
        """Record a completed trade for learning"""
        self.trade_history.append({
            **trade,
            "recorded_at": datetime.now(timezone.utc).isoformat()
        })
    
    def calculate_strategy_performance(
        self,
        strategy_name: str,
        lookback_days: int = 30
    ) -> Optional[StrategyPerformance]:
        """Calculate performance metrics for a strategy"""
        cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
        
        # Filter trades for this strategy
        strategy_trades = [
            t for t in self.trade_history
            if t.get('strategy') == strategy_name
            and datetime.fromisoformat(t.get('timestamp', '2000-01-01')) > cutoff
        ]
        
        if len(strategy_trades) < self.min_trades_for_evaluation:
            return None
        
        # Calculate metrics
        pnls = [t.get('pnl', 0) for t in strategy_trades]
        wins = sum(1 for p in pnls if p > 0)
        losses = sum(1 for p in pnls if p < 0)
        
        win_rate = wins / len(pnls) if pnls else 0
        
        gross_profit = sum(p for p in pnls if p > 0)
        gross_loss = abs(sum(p for p in pnls if p < 0))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        # Sharpe ratio (simplified)
        if len(pnls) > 1:
            avg_pnl = np.mean(pnls)
            std_pnl = np.std(pnls)
            sharpe = (avg_pnl / std_pnl) * np.sqrt(252) if std_pnl > 0 else 0
        else:
            sharpe = 0
        
        # Max drawdown
        cumulative = np.cumsum(pnls)
        running_max = np.maximum.accumulate(cumulative)
        drawdowns = running_max - cumulative
        max_dd = np.max(drawdowns) if len(drawdowns) > 0 else 0
        
        return StrategyPerformance(
            strategy_name=strategy_name,
            win_rate=win_rate,
            profit_factor=profit_factor,
            sharpe_ratio=sharpe,
            max_drawdown=max_dd,
            total_trades=len(pnls),
            total_pnl=sum(pnls),
            avg_trade_pnl=np.mean(pnls) if pnls else 0,
            period_start=cutoff,
            period_end=datetime.now(timezone.utc)
        )
    
    def adjust_weights(self) -> Dict[str, float]:
        """Adjust strategy weights based on performance"""
        adjustments = {}
        
        for strategy in self.default_strategies:
            perf = self.calculate_strategy_performance(strategy)
            if perf is None:
                continue
            
            self.strategy_performance[strategy] = perf
            
            # Score based on metrics
            score = 0.0
            
            # Win rate contribution (0-100% -> 0-1 score)
            score += perf.win_rate * 0.3
            
            # Profit factor (capped at 3 -> 0-1 score)
            score += min(perf.profit_factor / 3, 1) * 0.3
            
            # Sharpe ratio (capped at 2 -> 0-1 score)
            score += min(max(perf.sharpe_ratio, 0) / 2, 1) * 0.4
            
            # Penalty for high drawdown
            if perf.max_drawdown > 1000:
                score *= 0.8
            
            # Calculate adjustment
            current_weight = self.strategy_weights.get(strategy, 0.1)
            target_weight = score / len(self.default_strategies)
            
            # Gradual adjustment
            adjustment = (target_weight - current_weight) * self.learning_rate
            new_weight = current_weight + adjustment
            new_weight = max(0.01, min(0.5, new_weight))  # Bounds
            
            self.strategy_weights[strategy] = new_weight
            adjustments[strategy] = adjustment
        
        # Normalize weights
        total_weight = sum(self.strategy_weights.values())
        if total_weight > 0:
            for strategy in self.strategy_weights:
                self.strategy_weights[strategy] /= total_weight
        
        return adjustments
    
    async def run_learning_cycle(self, cycle_type: str = "daily") -> LearningCycle:
        """Run a complete learning cycle"""
        self.cycle_counter += 1
        
        cycle = LearningCycle(
            cycle_id=self.cycle_counter,
            cycle_type=cycle_type,
            start_time=datetime.now(timezone.utc),
            strategies_evaluated=self.default_strategies.copy()
        )
        
        # Record performance before
        for strategy in self.default_strategies:
            perf = self.calculate_strategy_performance(strategy)
            if perf:
                cycle.performance_before[strategy] = perf.sharpe_ratio
        
        # Adjust weights
        adjustments = self.adjust_weights()
        cycle.weight_adjustments = adjustments
        
        # Record performance after (would be checked in next cycle)
        cycle.performance_after = {s: 0.0 for s in self.default_strategies}
        
        cycle.end_time = datetime.now(timezone.utc)
        cycle.status = "completed"
        
        self.learning_cycles.append(cycle)
        
        logger.info(f"Learning cycle {cycle.cycle_id} completed. Adjustments: {adjustments}")
        
        return cycle
    
    def get_strategy_weights(self) -> Dict:
        """Get current strategy weights"""
        return {
            "weights": {k: round(v, 4) for k, v in self.strategy_weights.items()},
            "last_update": datetime.now(timezone.utc).isoformat(),
            "total_strategies": len(self.strategy_weights)
        }
    
    def get_performance_summary(self) -> Dict:
        """Get performance summary for all strategies"""
        summaries = []
        
        for strategy in self.default_strategies:
            perf = self.strategy_performance.get(strategy)
            if perf:
                summaries.append(perf.to_dict())
            else:
                summaries.append({
                    "strategy_name": strategy,
                    "status": "insufficient_data"
                })
        
        return {
            "strategies": summaries,
            "learning_cycles_completed": len(self.learning_cycles),
            "total_trades_recorded": len(self.trade_history)
        }
    
    def get_learning_history(self, limit: int = 10) -> List[Dict]:
        """Get recent learning cycles"""
        return [c.to_dict() for c in self.learning_cycles[-limit:]]
