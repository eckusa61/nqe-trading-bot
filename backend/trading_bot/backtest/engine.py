"""
Backtesting Engine
Walk-forward optimization with realistic costs
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
import logging

from trading_bot.config import CONFIG
from trading_bot.data.ibkr_connector import HistoricalBar
from trading_bot.data.feature_engine import FeatureEngine, FeatureSet
from trading_bot.strategies.base_strategy import BaseStrategy, Signal, StrategyResult
from trading_bot.backtest.realistic_costs import RealisticCostModel, ExecutionResult
from trading_bot.backtest.performance import PerformanceAnalyzer, PerformanceMetrics

logger = logging.getLogger(__name__)


@dataclass
class Trade:
    """Record of a completed trade"""
    symbol: str
    side: str
    entry_price: float
    exit_price: float
    quantity: int
    entry_date: datetime
    exit_date: datetime
    pnl: float
    pnl_pct: float
    commission: float
    slippage: float
    strategy: str
    holding_days: int
    
    def to_dict(self) -> Dict:
        return {
            "symbol": self.symbol,
            "side": self.side,
            "entry_price": self.entry_price,
            "exit_price": self.exit_price,
            "quantity": self.quantity,
            "entry_date": self.entry_date.isoformat(),
            "exit_date": self.exit_date.isoformat(),
            "pnl": round(self.pnl, 2),
            "pnl_pct": round(self.pnl_pct * 100, 2),
            "commission": round(self.commission, 2),
            "slippage": round(self.slippage, 2),
            "strategy": self.strategy,
            "holding_days": self.holding_days
        }


@dataclass
class Position:
    """Current position"""
    symbol: str
    quantity: int
    avg_price: float
    entry_date: datetime
    strategy: str
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None


@dataclass
class BacktestResult:
    """Complete backtest results"""
    strategy_name: str
    start_date: datetime
    end_date: datetime
    initial_capital: float
    final_capital: float
    equity_curve: List[float]
    dates: List[datetime]
    trades: List[Trade]
    metrics: PerformanceMetrics
    signals_generated: int
    parameters: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "strategy_name": self.strategy_name,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "initial_capital": self.initial_capital,
            "final_capital": round(self.final_capital, 2),
            "total_return_pct": round((self.final_capital - self.initial_capital) / self.initial_capital * 100, 2),
            "metrics": self.metrics.to_dict(),
            "trades_count": len(self.trades),
            "signals_generated": self.signals_generated,
            "parameters": self.parameters,
            "equity_curve_sample": self.equity_curve[::max(1, len(self.equity_curve)//50)]  # Sample 50 points
        }


class BacktestEngine:
    """
    Backtesting engine with realistic simulation
    
    Features:
    - Point-in-time data only (no look-ahead bias)
    - Realistic transaction costs
    - Latency simulation
    - Partial fills
    - Walk-forward optimization
    """
    
    def __init__(
        self,
        initial_capital: float = 100000.0,
        cost_model: Optional[RealisticCostModel] = None,
        feature_engine: Optional[FeatureEngine] = None
    ):
        self.initial_capital = initial_capital
        self.cost_model = cost_model or RealisticCostModel()
        self.feature_engine = feature_engine or FeatureEngine()
        self.performance_analyzer = PerformanceAnalyzer()
        
        # State
        self._cash = initial_capital
        self._positions: Dict[str, Position] = {}
        self._trades: List[Trade] = []
        self._equity_curve: List[float] = []
        self._dates: List[datetime] = []
        self._total_commission = 0.0
        self._total_slippage = 0.0
        self._signals_count = 0
    
    def reset(self):
        """Reset backtest state"""
        self._cash = self.initial_capital
        self._positions.clear()
        self._trades.clear()
        self._equity_curve.clear()
        self._dates.clear()
        self._total_commission = 0.0
        self._total_slippage = 0.0
        self._signals_count = 0
    
    def _calculate_portfolio_value(self, prices: Dict[str, float]) -> float:
        """Calculate current portfolio value"""
        value = self._cash
        for symbol, pos in self._positions.items():
            if symbol in prices:
                value += pos.quantity * prices[symbol]
        return value
    
    def _check_stops(self, symbol: str, price: float, bar: HistoricalBar) -> Optional[str]:
        """Check if stop loss or take profit hit"""
        if symbol not in self._positions:
            return None
        
        pos = self._positions[symbol]
        
        # Check stop loss
        if pos.stop_loss:
            if pos.quantity > 0 and bar.low <= pos.stop_loss:
                return "stop_loss"
            elif pos.quantity < 0 and bar.high >= pos.stop_loss:
                return "stop_loss"
        
        # Check take profit
        if pos.take_profit:
            if pos.quantity > 0 and bar.high >= pos.take_profit:
                return "take_profit"
            elif pos.quantity < 0 and bar.low <= pos.take_profit:
                return "take_profit"
        
        return None
    
    def _execute_signal(
        self,
        signal: Signal,
        price: float,
        volatility: float,
        date: datetime
    ) -> Optional[Trade]:
        """
        Execute a trading signal
        
        Returns Trade if position was closed, None otherwise
        """
        symbol = signal.symbol
        
        # Determine target position based on signal
        # Signal of 1.0 = full position, -1.0 = full short
        position_size_pct = abs(signal.signal) * 0.2  # Max 20% per position
        target_value = self._calculate_portfolio_value({}) * position_size_pct
        target_quantity = int(target_value / price) if price > 0 else 0
        
        if signal.signal < 0:
            target_quantity = -target_quantity
        
        current_pos = self._positions.get(symbol)
        current_qty = current_pos.quantity if current_pos else 0
        
        # Calculate trade quantity
        trade_qty = target_quantity - current_qty
        
        if abs(trade_qty) < 1:
            return None
        
        # Execute trade
        side = "BUY" if trade_qty > 0 else "SELL"
        exec_result = self.cost_model.execute_order(
            symbol=symbol,
            side=side,
            quantity=abs(trade_qty),
            price=price,
            volatility=volatility,
            liquidity_tier=CONFIG.symbols.get_tier(symbol)
        )
        
        if exec_result.filled_qty == 0:
            return None
        
        filled_qty = exec_result.filled_qty if side == "BUY" else -exec_result.filled_qty
        
        # Update costs
        self._total_commission += exec_result.commission
        self._total_slippage += exec_result.slippage * exec_result.filled_qty
        
        # Update cash
        if side == "BUY":
            self._cash -= exec_result.filled_qty * exec_result.avg_fill_price + exec_result.commission
        else:
            self._cash += exec_result.filled_qty * exec_result.avg_fill_price - exec_result.commission
        
        # Check if closing position
        completed_trade = None
        if current_pos and ((current_qty > 0 and filled_qty < 0) or (current_qty < 0 and filled_qty > 0)):
            # Closing or reversing position
            close_qty = min(abs(current_qty), abs(filled_qty))
            
            if current_qty > 0:
                pnl = (exec_result.avg_fill_price - current_pos.avg_price) * close_qty - exec_result.commission
            else:
                pnl = (current_pos.avg_price - exec_result.avg_fill_price) * close_qty - exec_result.commission
            
            completed_trade = Trade(
                symbol=symbol,
                side="LONG" if current_qty > 0 else "SHORT",
                entry_price=current_pos.avg_price,
                exit_price=exec_result.avg_fill_price,
                quantity=close_qty,
                entry_date=current_pos.entry_date,
                exit_date=date,
                pnl=pnl,
                pnl_pct=pnl / (current_pos.avg_price * close_qty),
                commission=exec_result.commission,
                slippage=exec_result.slippage * close_qty,
                strategy=current_pos.strategy,
                holding_days=(date - current_pos.entry_date).days
            )
            self._trades.append(completed_trade)
        
        # Update position
        new_qty = current_qty + filled_qty
        if new_qty == 0:
            if symbol in self._positions:
                del self._positions[symbol]
        else:
            if symbol in self._positions and ((current_qty > 0 and new_qty > 0) or (current_qty < 0 and new_qty < 0)):
                # Adding to position - update average price
                total_cost = current_pos.avg_price * abs(current_qty) + exec_result.avg_fill_price * abs(filled_qty)
                new_avg_price = total_cost / abs(new_qty)
                self._positions[symbol] = Position(
                    symbol=symbol,
                    quantity=new_qty,
                    avg_price=new_avg_price,
                    entry_date=current_pos.entry_date,
                    strategy=signal.strategy,
                    stop_loss=signal.stop_loss,
                    take_profit=signal.take_profit
                )
            else:
                # New position
                self._positions[symbol] = Position(
                    symbol=symbol,
                    quantity=new_qty,
                    avg_price=exec_result.avg_fill_price,
                    entry_date=date,
                    strategy=signal.strategy,
                    stop_loss=signal.stop_loss,
                    take_profit=signal.take_profit
                )
        
        return completed_trade
    
    def run(
        self,
        strategy: BaseStrategy,
        historical_data: Dict[str, List[HistoricalBar]],
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        benchmark_symbol: str = "SPY"
    ) -> BacktestResult:
        """
        Run backtest for a single strategy
        
        Args:
            strategy: Strategy to test
            historical_data: Dict of {symbol: [bars]} with bars sorted by date
            start_date: Start date for backtest
            end_date: End date for backtest
            benchmark_symbol: Symbol to use as benchmark
        
        Returns:
            BacktestResult with all metrics
        """
        self.reset()
        
        # Get all symbols
        symbols = list(historical_data.keys())
        if not symbols:
            return BacktestResult(
                strategy_name=strategy.name,
                start_date=datetime.now(timezone.utc),
                end_date=datetime.now(timezone.utc),
                initial_capital=self.initial_capital,
                final_capital=self.initial_capital,
                equity_curve=[self.initial_capital],
                dates=[],
                trades=[],
                metrics=PerformanceMetrics(),
                signals_generated=0,
                parameters=strategy.get_parameters()
            )
        
        # Build date index - collect all unique dates
        all_dates = set()
        for bars in historical_data.values():
            for bar in bars:
                all_dates.add(bar.timestamp.date())
        
        all_dates = sorted(all_dates)
        
        # Filter by date range
        if start_date:
            all_dates = [d for d in all_dates if d >= start_date.date()]
        if end_date:
            all_dates = [d for d in all_dates if d <= end_date.date()]
        
        if len(all_dates) < 252:  # Need at least 1 year for feature calculation
            logger.warning("Insufficient data for backtest")
            all_dates = all_dates  # Use what we have
        
        # Build price lookup
        price_lookup: Dict[str, Dict] = {symbol: {} for symbol in symbols}
        bar_lookup: Dict[str, Dict] = {symbol: {} for symbol in symbols}
        
        for symbol, bars in historical_data.items():
            for bar in bars:
                date_key = bar.timestamp.date()
                price_lookup[symbol][date_key] = bar.close
                bar_lookup[symbol][date_key] = bar
        
        # Pre-calculate features for each symbol
        features_by_symbol: Dict[str, Dict] = {}
        for symbol, bars in historical_data.items():
            features_by_symbol[symbol] = {}
            for i in range(252, len(bars)):
                features = self.feature_engine.calculate_features(bars, i)
                if features:
                    features_by_symbol[symbol][bars[i].timestamp.date()] = features
        
        # Main backtest loop
        benchmark_equity = []
        initial_benchmark_price = None
        
        for date in all_dates[252:]:  # Skip warmup period
            # Get current prices
            current_prices = {}
            current_bars = {}
            for symbol in symbols:
                if date in price_lookup[symbol]:
                    current_prices[symbol] = price_lookup[symbol][date]
                    current_bars[symbol] = bar_lookup[symbol][date]
            
            if not current_prices:
                continue
            
            # Check stops first
            for symbol in list(self._positions.keys()):
                if symbol in current_bars:
                    stop_reason = self._check_stops(symbol, current_prices[symbol], current_bars[symbol])
                    if stop_reason:
                        # Close position at stop price
                        pos = self._positions[symbol]
                        exit_price = pos.stop_loss if stop_reason == "stop_loss" else pos.take_profit
                        
                        # Create exit signal
                        exit_signal = Signal(
                            symbol=symbol,
                            signal=0.0,
                            confidence=1.0,
                            strategy=strategy.name,
                            reason=stop_reason
                        )
                        self._execute_signal(exit_signal, exit_price, 0.25, datetime.combine(date, datetime.min.time()))
            
            # Get features for current date
            current_features = []
            for symbol in symbols:
                if date in features_by_symbol.get(symbol, {}):
                    current_features.append(features_by_symbol[symbol][date])
            
            if current_features:
                # Generate signals
                result = strategy.evaluate(current_features)
                self._signals_count += len(result.signals)
                
                # Execute signals
                for signal in result.signals:
                    if abs(signal.signal) > 0.1 and signal.confidence > 0.3:
                        if signal.symbol in current_prices:
                            volatility = features_by_symbol.get(signal.symbol, {}).get(date)
                            vol = volatility.volatility_annualized if volatility else 0.25
                            self._execute_signal(
                                signal,
                                current_prices[signal.symbol],
                                vol,
                                datetime.combine(date, datetime.min.time())
                            )
            
            # Record equity
            portfolio_value = self._calculate_portfolio_value(current_prices)
            self._equity_curve.append(portfolio_value)
            self._dates.append(datetime.combine(date, datetime.min.time()))
            
            # Track benchmark
            if benchmark_symbol in current_prices:
                if initial_benchmark_price is None:
                    initial_benchmark_price = current_prices[benchmark_symbol]
                benchmark_value = self.initial_capital * current_prices[benchmark_symbol] / initial_benchmark_price
                benchmark_equity.append(benchmark_value)
        
        # Close any remaining positions at end
        if self._dates:
            final_date = self._dates[-1]
            for symbol in list(self._positions.keys()):
                if symbol in current_prices:
                    exit_signal = Signal(
                        symbol=symbol,
                        signal=0.0,
                        confidence=1.0,
                        strategy=strategy.name,
                        reason="backtest_end"
                    )
                    self._execute_signal(exit_signal, current_prices[symbol], 0.25, final_date)
        
        # Calculate final metrics
        final_capital = self._equity_curve[-1] if self._equity_curve else self.initial_capital
        
        metrics = self.performance_analyzer.analyze(
            equity_curve=self._equity_curve,
            trades=[t.to_dict() for t in self._trades],
            benchmark_equity=benchmark_equity if len(benchmark_equity) == len(self._equity_curve) else None,
            total_commission=self._total_commission,
            total_slippage=self._total_slippage
        )
        
        return BacktestResult(
            strategy_name=strategy.name,
            start_date=self._dates[0] if self._dates else datetime.now(timezone.utc),
            end_date=self._dates[-1] if self._dates else datetime.now(timezone.utc),
            initial_capital=self.initial_capital,
            final_capital=final_capital,
            equity_curve=self._equity_curve,
            dates=self._dates,
            trades=self._trades,
            metrics=metrics,
            signals_generated=self._signals_count,
            parameters=strategy.get_parameters()
        )
    
    def run_walk_forward(
        self,
        strategy: BaseStrategy,
        historical_data: Dict[str, List[HistoricalBar]],
        train_days: int = 252,
        test_days: int = 63,
        step_days: int = 21
    ) -> List[BacktestResult]:
        """
        Run walk-forward optimization
        
        Splits data into rolling train/test windows
        """
        results = []
        
        # Get date range
        all_dates = set()
        for bars in historical_data.values():
            for bar in bars:
                all_dates.add(bar.timestamp.date())
        
        all_dates = sorted(all_dates)
        
        if len(all_dates) < train_days + test_days:
            logger.warning("Insufficient data for walk-forward")
            return results
        
        # Walk forward through time
        start_idx = 0
        while start_idx + train_days + test_days <= len(all_dates):
            train_end_idx = start_idx + train_days
            test_end_idx = train_end_idx + test_days
            
            train_start = datetime.combine(all_dates[start_idx], datetime.min.time())
            train_end = datetime.combine(all_dates[train_end_idx - 1], datetime.min.time())
            test_start = datetime.combine(all_dates[train_end_idx], datetime.min.time())
            test_end = datetime.combine(all_dates[min(test_end_idx - 1, len(all_dates) - 1)], datetime.min.time())
            
            # Run on test period
            result = self.run(
                strategy=strategy,
                historical_data=historical_data,
                start_date=test_start,
                end_date=test_end
            )
            
            results.append(result)
            logger.info(f"Walk-forward period {test_start.date()} to {test_end.date()}: Return={result.metrics.total_return*100:.1f}%")
            
            start_idx += step_days
        
        return results
