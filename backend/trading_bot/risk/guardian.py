"""
Guardian Agent
Risk overlay that approves/modifies/rejects all trades
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from enum import Enum

from trading_bot.config import CONFIG

logger = logging.getLogger(__name__)


class GuardianAction(Enum):
    """Guardian decision actions"""
    APPROVE = "approve"
    MODIFY = "modify"
    REJECT = "reject"
    DELAY = "delay"


@dataclass
class TradeRequest:
    """Trade request to be evaluated by Guardian"""
    symbol: str
    side: str  # BUY or SELL
    quantity: int
    price: float
    strategy: str
    signal_strength: float
    confidence: float


@dataclass
class GuardianDecision:
    """Guardian's decision on a trade"""
    action: GuardianAction
    original_request: TradeRequest
    modified_quantity: Optional[int] = None
    reason: str = ""
    delay_minutes: int = 0
    risk_score: float = 0.0
    checks_passed: List[str] = field(default_factory=list)
    checks_failed: List[str] = field(default_factory=list)


class GuardianAgent:
    """
    Risk overlay that evaluates every trade before execution
    
    Powers:
    - APPROVE: Trade can proceed as-is
    - MODIFY: Reduce size or adjust parameters
    - REJECT: Block trade entirely
    - DELAY: Wait before executing
    """
    
    def __init__(
        self,
        max_drawdown: float = 0.15,
        warning_drawdown: float = 0.10,
        max_position_pct: float = 0.20,
        max_sector_pct: float = 0.30,
        max_daily_trades: int = 50,
        vix_crisis_threshold: float = 40.0,
        vix_caution_threshold: float = 25.0,
        min_rolling_sharpe: float = -0.5
    ):
        self.max_drawdown = max_drawdown
        self.warning_drawdown = warning_drawdown
        self.max_position_pct = max_position_pct
        self.max_sector_pct = max_sector_pct
        self.max_daily_trades = max_daily_trades
        self.vix_crisis_threshold = vix_crisis_threshold
        self.vix_caution_threshold = vix_caution_threshold
        self.min_rolling_sharpe = min_rolling_sharpe
        
        # State tracking
        self.kill_switch_active = False
        self.current_drawdown = 0.0
        self.current_vix = 15.0
        self.rolling_sharpe = 0.0
        self.daily_trades_count = 0
        self.last_reset_date = datetime.now(timezone.utc).date()
        
        # Behavioral tracking
        self.recent_trades: List[Dict] = []
        self.recent_pnl: List[float] = []
        
        # Position tracking
        self.positions: Dict[str, float] = {}  # symbol -> value
        self.sector_exposure: Dict[str, float] = {}  # sector -> value
        self.portfolio_value = 100000.0
        
        logger.info("GuardianAgent initialized")
    
    def evaluate_trade(self, request: TradeRequest) -> GuardianDecision:
        """
        Main entry point: Evaluate a trade request
        
        Returns GuardianDecision with action to take
        """
        checks_passed = []
        checks_failed = []
        risk_score = 0.0
        
        # Reset daily counter if new day
        today = datetime.now(timezone.utc).date()
        if today != self.last_reset_date:
            self.daily_trades_count = 0
            self.last_reset_date = today
        
        # ===== HARD BLOCKS (instant reject) =====
        
        # 1. Kill switch check
        if self.kill_switch_active:
            return GuardianDecision(
                action=GuardianAction.REJECT,
                original_request=request,
                reason="Kill switch is active",
                checks_failed=["kill_switch"]
            )
        
        # 2. Max drawdown check
        if self.current_drawdown >= self.max_drawdown:
            return GuardianDecision(
                action=GuardianAction.REJECT,
                original_request=request,
                reason=f"Max drawdown breached: {self.current_drawdown:.1%} >= {self.max_drawdown:.1%}",
                checks_failed=["max_drawdown"]
            )
        checks_passed.append("max_drawdown")
        
        # 3. Daily trade limit
        if self.daily_trades_count >= self.max_daily_trades:
            return GuardianDecision(
                action=GuardianAction.REJECT,
                original_request=request,
                reason=f"Daily trade limit reached: {self.daily_trades_count}/{self.max_daily_trades}",
                checks_failed=["daily_limit"]
            )
        checks_passed.append("daily_limit")
        
        # ===== RISK CHECKS (may modify) =====
        
        modified_quantity = request.quantity
        modification_reasons = []
        
        # 4. Position size check
        trade_value = request.quantity * request.price
        position_pct = trade_value / self.portfolio_value if self.portfolio_value > 0 else 1.0
        
        if position_pct > self.max_position_pct:
            # Reduce to max allowed
            max_value = self.portfolio_value * self.max_position_pct
            modified_quantity = int(max_value / request.price)
            modification_reasons.append(f"Position size reduced: {position_pct:.1%} -> {self.max_position_pct:.1%}")
            risk_score += 0.2
            checks_failed.append("position_size")
        else:
            checks_passed.append("position_size")
        
        # 5. Warning drawdown check
        if self.current_drawdown >= self.warning_drawdown:
            # Reduce size by 50%
            modified_quantity = int(modified_quantity * 0.5)
            modification_reasons.append(f"Warning drawdown: reducing size 50%")
            risk_score += 0.3
            checks_failed.append("warning_drawdown")
        else:
            checks_passed.append("warning_drawdown")
        
        # ===== MARKET CONDITION CHECKS =====
        
        # 6. VIX/Volatility check
        if self.current_vix >= self.vix_crisis_threshold:
            # Crisis mode: reduce to 25%
            modified_quantity = int(modified_quantity * 0.25)
            modification_reasons.append(f"Crisis mode (VIX={self.current_vix:.0f}): reducing 75%")
            risk_score += 0.4
            checks_failed.append("vix_crisis")
        elif self.current_vix >= self.vix_caution_threshold:
            # Caution mode: reduce to 50%
            modified_quantity = int(modified_quantity * 0.5)
            modification_reasons.append(f"Elevated VIX ({self.current_vix:.0f}): reducing 50%")
            risk_score += 0.2
            checks_failed.append("vix_elevated")
        else:
            checks_passed.append("vix_check")
        
        # ===== BEHAVIORAL CHECKS =====
        
        # 7. Revenge trading detection
        if self._detect_revenge_trading(request):
            return GuardianDecision(
                action=GuardianAction.REJECT,
                original_request=request,
                reason="Behavioral: Revenge trading pattern detected",
                risk_score=0.9,
                checks_failed=["revenge_trading"]
            )
        checks_passed.append("revenge_trading")
        
        # 8. Overconfidence detection
        if self._detect_overconfidence():
            modified_quantity = int(modified_quantity * 0.5)
            modification_reasons.append("Overconfidence detected: reducing 50%")
            risk_score += 0.2
            checks_failed.append("overconfidence")
        else:
            checks_passed.append("overconfidence")
        
        # ===== PERFORMANCE CHECKS =====
        
        # 9. Rolling Sharpe check
        if self.rolling_sharpe < self.min_rolling_sharpe:
            modified_quantity = int(modified_quantity * 0.5)
            modification_reasons.append(f"Poor rolling Sharpe ({self.rolling_sharpe:.2f}): reducing 50%")
            risk_score += 0.2
            checks_failed.append("rolling_sharpe")
        else:
            checks_passed.append("rolling_sharpe")
        
        # ===== FINAL DECISION =====
        
        # Check if quantity reduced to zero
        if modified_quantity <= 0:
            return GuardianDecision(
                action=GuardianAction.REJECT,
                original_request=request,
                reason="Trade reduced to zero quantity",
                risk_score=risk_score,
                checks_passed=checks_passed,
                checks_failed=checks_failed
            )
        
        # Check if modified
        if modified_quantity != request.quantity:
            return GuardianDecision(
                action=GuardianAction.MODIFY,
                original_request=request,
                modified_quantity=modified_quantity,
                reason=" | ".join(modification_reasons),
                risk_score=risk_score,
                checks_passed=checks_passed,
                checks_failed=checks_failed
            )
        
        # All checks passed
        return GuardianDecision(
            action=GuardianAction.APPROVE,
            original_request=request,
            reason="All checks passed",
            risk_score=risk_score,
            checks_passed=checks_passed,
            checks_failed=checks_failed
        )
    
    def _detect_revenge_trading(self, request: TradeRequest) -> bool:
        """
        Detect revenge trading pattern:
        - Recent loss followed by oversized position
        """
        if len(self.recent_pnl) < 2:
            return False
        
        # Check if last trade was a significant loss
        last_pnl = self.recent_pnl[-1] if self.recent_pnl else 0
        if last_pnl >= 0:
            return False
        
        loss_pct = abs(last_pnl) / self.portfolio_value
        
        # Check if current trade is oversized
        trade_value = request.quantity * request.price
        trade_pct = trade_value / self.portfolio_value
        
        # Revenge trading: Loss > 1% followed by trade > 15%
        if loss_pct > 0.01 and trade_pct > 0.15:
            logger.warning(f"Revenge trading detected: {loss_pct:.1%} loss, {trade_pct:.1%} trade")
            return True
        
        return False
    
    def _detect_overconfidence(self) -> bool:
        """
        Detect overconfidence pattern:
        - Winning streak followed by increasing position sizes
        """
        if len(self.recent_pnl) < 5:
            return False
        
        # Check for winning streak (3+ wins in a row)
        recent = self.recent_pnl[-5:]
        wins = sum(1 for p in recent if p > 0)
        
        if wins >= 4:
            logger.warning(f"Overconfidence pattern: {wins}/5 winning trades")
            return True
        
        return False
    
    def update_state(
        self,
        drawdown: float = None,
        vix: float = None,
        sharpe: float = None,
        portfolio_value: float = None,
        positions: Dict[str, float] = None
    ):
        """Update Guardian state with current market/portfolio data"""
        if drawdown is not None:
            self.current_drawdown = drawdown
        if vix is not None:
            self.current_vix = vix
        if sharpe is not None:
            self.rolling_sharpe = sharpe
        if portfolio_value is not None:
            self.portfolio_value = portfolio_value
        if positions is not None:
            self.positions = positions
    
    def record_trade(self, pnl: float):
        """Record completed trade for behavioral tracking"""
        self.recent_pnl.append(pnl)
        self.daily_trades_count += 1
        
        # Keep only last 20 trades
        if len(self.recent_pnl) > 20:
            self.recent_pnl = self.recent_pnl[-20:]
    
    def activate_kill_switch(self, reason: str = ""):
        """Activate kill switch"""
        self.kill_switch_active = True
        logger.critical(f"GUARDIAN: Kill switch activated - {reason}")
    
    def deactivate_kill_switch(self):
        """Deactivate kill switch"""
        self.kill_switch_active = False
        logger.info("GUARDIAN: Kill switch deactivated")
    
    def get_status(self) -> Dict:
        """Get current Guardian status"""
        return {
            "kill_switch_active": self.kill_switch_active,
            "current_drawdown": self.current_drawdown,
            "current_vix": self.current_vix,
            "rolling_sharpe": self.rolling_sharpe,
            "daily_trades": self.daily_trades_count,
            "max_daily_trades": self.max_daily_trades,
            "portfolio_value": self.portfolio_value,
            "recent_trades": len(self.recent_pnl),
            "thresholds": {
                "max_drawdown": self.max_drawdown,
                "warning_drawdown": self.warning_drawdown,
                "vix_crisis": self.vix_crisis_threshold,
                "vix_caution": self.vix_caution_threshold
            }
        }
