"""
Performance Analyzer
Calculates comprehensive performance metrics
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import math


@dataclass
class PerformanceMetrics:
    """Complete performance metrics"""
    # Returns
    total_return: float = 0.0
    annual_return: float = 0.0
    monthly_returns: List[float] = field(default_factory=list)
    
    # Risk-adjusted returns
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    
    # Drawdown
    max_drawdown: float = 0.0
    avg_drawdown: float = 0.0
    max_drawdown_duration_days: int = 0
    
    # Trade statistics
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    largest_win: float = 0.0
    largest_loss: float = 0.0
    avg_trade_pnl: float = 0.0
    
    # Costs
    total_commission: float = 0.0
    total_slippage: float = 0.0
    avg_slippage_pct: float = 0.0
    
    # Benchmark comparison
    alpha: float = 0.0
    beta: float = 0.0
    correlation: float = 0.0
    information_ratio: float = 0.0
    
    # Time metrics
    days_traded: int = 0
    avg_holding_period: float = 0.0
    
    def to_dict(self) -> Dict:
        return {
            "total_return": round(self.total_return * 100, 2),
            "annual_return": round(self.annual_return * 100, 2),
            "sharpe_ratio": round(self.sharpe_ratio, 2),
            "sortino_ratio": round(self.sortino_ratio, 2),
            "calmar_ratio": round(self.calmar_ratio, 2),
            "max_drawdown": round(self.max_drawdown * 100, 2),
            "avg_drawdown": round(self.avg_drawdown * 100, 2),
            "total_trades": self.total_trades,
            "win_rate": round(self.win_rate * 100, 1),
            "profit_factor": round(self.profit_factor, 2),
            "avg_trade_pnl": round(self.avg_trade_pnl, 2),
            "total_commission": round(self.total_commission, 2),
            "total_slippage": round(self.total_slippage, 2),
            "alpha": round(self.alpha * 100, 2),
            "beta": round(self.beta, 2),
            "days_traded": self.days_traded
        }


class PerformanceAnalyzer:
    """
    Analyzes backtest results and calculates performance metrics
    """
    
    def __init__(self, risk_free_rate: float = 0.05):
        """
        Args:
            risk_free_rate: Annual risk-free rate (default 5%)
        """
        self.risk_free_rate = risk_free_rate
    
    def calculate_returns(self, equity_curve: List[float]) -> Tuple[List[float], float]:
        """
        Calculate returns from equity curve
        
        Returns:
            (daily_returns, total_return)
        """
        if len(equity_curve) < 2:
            return [], 0.0
        
        daily_returns = []
        for i in range(1, len(equity_curve)):
            if equity_curve[i-1] > 0:
                ret = (equity_curve[i] - equity_curve[i-1]) / equity_curve[i-1]
                daily_returns.append(ret)
        
        total_return = (equity_curve[-1] - equity_curve[0]) / equity_curve[0] if equity_curve[0] > 0 else 0
        
        return daily_returns, total_return
    
    def calculate_sharpe_ratio(self, returns: List[float], annualize: bool = True) -> float:
        """
        Calculate Sharpe Ratio
        
        Sharpe = (Return - Risk Free) / Std Dev
        """
        if len(returns) < 2:
            return 0.0
        
        mean_return = sum(returns) / len(returns)
        
        # Standard deviation
        variance = sum((r - mean_return) ** 2 for r in returns) / (len(returns) - 1)
        std_dev = math.sqrt(variance)
        
        if std_dev == 0:
            return 0.0
        
        # Daily risk-free rate
        daily_rf = self.risk_free_rate / 252
        
        sharpe = (mean_return - daily_rf) / std_dev
        
        if annualize:
            sharpe *= math.sqrt(252)
        
        return sharpe
    
    def calculate_sortino_ratio(self, returns: List[float], annualize: bool = True) -> float:
        """
        Calculate Sortino Ratio (only penalizes downside volatility)
        
        Sortino = (Return - Risk Free) / Downside Std Dev
        """
        if len(returns) < 2:
            return 0.0
        
        mean_return = sum(returns) / len(returns)
        daily_rf = self.risk_free_rate / 252
        
        # Downside returns only
        downside_returns = [r for r in returns if r < 0]
        
        if len(downside_returns) < 2:
            return 0.0 if mean_return <= daily_rf else float('inf')
        
        # Downside deviation
        downside_variance = sum(r ** 2 for r in downside_returns) / len(downside_returns)
        downside_std = math.sqrt(downside_variance)
        
        if downside_std == 0:
            return 0.0
        
        sortino = (mean_return - daily_rf) / downside_std
        
        if annualize:
            sortino *= math.sqrt(252)
        
        return sortino
    
    def calculate_drawdowns(self, equity_curve: List[float]) -> Tuple[float, float, int]:
        """
        Calculate drawdown metrics
        
        Returns:
            (max_drawdown, avg_drawdown, max_duration_days)
        """
        if len(equity_curve) < 2:
            return 0.0, 0.0, 0
        
        peak = equity_curve[0]
        max_dd = 0.0
        drawdowns = []
        current_dd_start = 0
        max_duration = 0
        current_duration = 0
        
        for i, value in enumerate(equity_curve):
            if value > peak:
                peak = value
                if current_duration > max_duration:
                    max_duration = current_duration
                current_duration = 0
            else:
                dd = (peak - value) / peak if peak > 0 else 0
                drawdowns.append(dd)
                max_dd = max(max_dd, dd)
                current_duration += 1
        
        avg_dd = sum(drawdowns) / len(drawdowns) if drawdowns else 0
        
        return max_dd, avg_dd, max_duration
    
    def calculate_calmar_ratio(self, annual_return: float, max_drawdown: float) -> float:
        """
        Calculate Calmar Ratio
        
        Calmar = Annual Return / Max Drawdown
        """
        if max_drawdown == 0:
            return 0.0
        return annual_return / max_drawdown
    
    def calculate_trade_statistics(self, trades: List[Dict]) -> Dict:
        """
        Calculate trade-level statistics
        
        Args:
            trades: List of trade dicts with 'pnl' field
        """
        if not trades:
            return {
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "win_rate": 0.0,
                "profit_factor": 0.0,
                "avg_win": 0.0,
                "avg_loss": 0.0,
                "largest_win": 0.0,
                "largest_loss": 0.0,
                "avg_trade_pnl": 0.0
            }
        
        pnls = [t.get('pnl', 0) for t in trades]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]
        
        total_trades = len(trades)
        winning_trades = len(wins)
        losing_trades = len(losses)
        
        win_rate = winning_trades / total_trades if total_trades > 0 else 0
        
        gross_profit = sum(wins)
        gross_loss = abs(sum(losses))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf') if gross_profit > 0 else 0
        
        avg_win = sum(wins) / len(wins) if wins else 0
        avg_loss = sum(losses) / len(losses) if losses else 0
        
        return {
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "largest_win": max(wins) if wins else 0,
            "largest_loss": min(losses) if losses else 0,
            "avg_trade_pnl": sum(pnls) / len(pnls) if pnls else 0
        }
    
    def calculate_alpha_beta(
        self,
        portfolio_returns: List[float],
        benchmark_returns: List[float]
    ) -> Tuple[float, float, float]:
        """
        Calculate alpha, beta, and correlation vs benchmark
        
        Uses simple linear regression: Rp = alpha + beta * Rb
        """
        if len(portfolio_returns) != len(benchmark_returns) or len(portfolio_returns) < 10:
            return 0.0, 1.0, 0.0
        
        n = len(portfolio_returns)
        
        # Means
        mean_p = sum(portfolio_returns) / n
        mean_b = sum(benchmark_returns) / n
        
        # Covariance and variance
        cov = sum((portfolio_returns[i] - mean_p) * (benchmark_returns[i] - mean_b) for i in range(n)) / n
        var_b = sum((benchmark_returns[i] - mean_b) ** 2 for i in range(n)) / n
        var_p = sum((portfolio_returns[i] - mean_p) ** 2 for i in range(n)) / n
        
        # Beta
        beta = cov / var_b if var_b > 0 else 1.0
        
        # Alpha (annualized)
        alpha = (mean_p - beta * mean_b) * 252
        
        # Correlation
        std_p = math.sqrt(var_p)
        std_b = math.sqrt(var_b)
        correlation = cov / (std_p * std_b) if std_p > 0 and std_b > 0 else 0
        
        return alpha, beta, correlation
    
    def analyze(
        self,
        equity_curve: List[float],
        trades: List[Dict],
        benchmark_equity: Optional[List[float]] = None,
        total_commission: float = 0.0,
        total_slippage: float = 0.0
    ) -> PerformanceMetrics:
        """
        Comprehensive performance analysis
        
        Args:
            equity_curve: Daily portfolio values
            trades: List of trade records
            benchmark_equity: Optional benchmark equity curve (e.g., SPY)
            total_commission: Total commissions paid
            total_slippage: Total slippage costs
        
        Returns:
            PerformanceMetrics object
        """
        metrics = PerformanceMetrics()
        
        if len(equity_curve) < 2:
            return metrics
        
        # Calculate returns
        daily_returns, total_return = self.calculate_returns(equity_curve)
        metrics.total_return = total_return
        
        # Annualized return
        days = len(equity_curve)
        years = days / 252
        if years > 0 and total_return > -1:
            metrics.annual_return = (1 + total_return) ** (1 / years) - 1
        
        # Risk-adjusted metrics
        metrics.sharpe_ratio = self.calculate_sharpe_ratio(daily_returns)
        metrics.sortino_ratio = self.calculate_sortino_ratio(daily_returns)
        
        # Drawdowns
        metrics.max_drawdown, metrics.avg_drawdown, metrics.max_drawdown_duration_days = \
            self.calculate_drawdowns(equity_curve)
        
        # Calmar ratio
        metrics.calmar_ratio = self.calculate_calmar_ratio(metrics.annual_return, metrics.max_drawdown)
        
        # Trade statistics
        trade_stats = self.calculate_trade_statistics(trades)
        metrics.total_trades = trade_stats["total_trades"]
        metrics.winning_trades = trade_stats["winning_trades"]
        metrics.losing_trades = trade_stats["losing_trades"]
        metrics.win_rate = trade_stats["win_rate"]
        metrics.profit_factor = trade_stats["profit_factor"]
        metrics.avg_win = trade_stats["avg_win"]
        metrics.avg_loss = trade_stats["avg_loss"]
        metrics.largest_win = trade_stats["largest_win"]
        metrics.largest_loss = trade_stats["largest_loss"]
        metrics.avg_trade_pnl = trade_stats["avg_trade_pnl"]
        
        # Costs
        metrics.total_commission = total_commission
        metrics.total_slippage = total_slippage
        
        # Days traded
        metrics.days_traded = days
        
        # Benchmark comparison
        if benchmark_equity and len(benchmark_equity) == len(equity_curve):
            benchmark_returns, _ = self.calculate_returns(benchmark_equity)
            metrics.alpha, metrics.beta, metrics.correlation = \
                self.calculate_alpha_beta(daily_returns, benchmark_returns)
        
        return metrics
