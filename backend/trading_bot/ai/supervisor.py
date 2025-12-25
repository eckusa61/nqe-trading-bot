"""
AI Supervisor - Autonomous Trading Bot Controller

Features:
- Monitors all bot activities
- Detects errors and anomalies
- Makes autonomous decisions
- Self-healing capabilities
- Reports via Telegram
"""
import os
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum
import traceback

from .llm_client import LLMClient, LLMProvider
from ..notifications import telegram_manager

logger = logging.getLogger(__name__)


class SupervisorAction(Enum):
    HOLD = "hold"
    ADJUST_STRATEGY = "adjust_strategy"
    REDUCE_EXPOSURE = "reduce_exposure"
    INCREASE_EXPOSURE = "increase_exposure"
    CLOSE_ALL = "close_all"
    RESTART_SERVICE = "restart_service"
    ALERT_USER = "alert_user"


@dataclass
class SupervisorDecision:
    action: SupervisorAction
    confidence: float
    reasoning: str
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    executed: bool = False


class AISupervisor:
    """
    Autonomous AI that supervises the trading bot
    
    Responsibilities:
    1. Monitor system health
    2. Analyze performance
    3. Detect anomalies
    4. Make strategic decisions
    5. Self-heal on errors
    6. Report to user
    """
    
    def __init__(self):
        self.llm = LLMClient(primary_provider=LLMProvider.OPENAI)
        self.is_running = False
        self.check_interval = 300  # 5 minutes
        self.last_check: Optional[datetime] = None
        self.decisions_history: List[SupervisorDecision] = []
        self.error_count = 0
        self.consecutive_losses = 0
        self.daily_pnl = 0.0
        
        # Thresholds
        self.max_daily_loss = -500  # $500 max daily loss
        self.max_consecutive_losses = 5
        self.max_drawdown_pct = 10.0  # 10% drawdown triggers alert
        
        logger.info("AI Supervisor initialized")
    
    async def start(self):
        """Start the supervisor loop"""
        self.is_running = True
        logger.info("AI Supervisor started")
        
        await telegram_manager.send_bot_status(
            "running",
            "🧠 AI Supervisor aktif. Sistem izleniyor."
        )
        
        while self.is_running:
            try:
                await self._supervisor_cycle()
            except Exception as e:
                logger.error(f"Supervisor cycle error: {e}")
                await self._handle_supervisor_error(e)
            
            await asyncio.sleep(self.check_interval)
    
    async def stop(self):
        """Stop the supervisor"""
        self.is_running = False
        await telegram_manager.send_bot_status(
            "stopped",
            "🛑 AI Supervisor durduruldu."
        )
    
    async def _supervisor_cycle(self):
        """Main supervisor cycle - runs every interval"""
        self.last_check = datetime.now(timezone.utc)
        
        # 1. Collect system state
        system_state = await self._collect_system_state()
        
        # 2. Check for critical issues
        critical_issues = await self._check_critical_issues(system_state)
        
        if critical_issues:
            await self._handle_critical_issues(critical_issues)
            return
        
        # 3. Analyze performance
        performance = await self._analyze_performance(system_state)
        
        # 4. Get AI recommendation
        decision = await self._get_ai_recommendation(system_state, performance)
        
        # 5. Execute decision if needed
        if decision.action != SupervisorAction.HOLD:
            await self._execute_decision(decision)
        
        # 6. Store decision
        self.decisions_history.append(decision)
        if len(self.decisions_history) > 100:
            self.decisions_history = self.decisions_history[-100:]
    
    async def _collect_system_state(self) -> Dict[str, Any]:
        """Collect current system state"""
        # This will be connected to actual trading state
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "bot_running": True,
            "connection_status": "connected",
            "regime": "unknown",
            "positions": [],
            "daily_pnl": self.daily_pnl,
            "error_count": self.error_count,
            "consecutive_losses": self.consecutive_losses
        }
    
    async def _check_critical_issues(self, state: Dict[str, Any]) -> List[str]:
        """Check for critical issues requiring immediate action"""
        issues = []
        
        # Check daily loss limit
        if state.get('daily_pnl', 0) < self.max_daily_loss:
            issues.append(f"Daily loss exceeded: ${state['daily_pnl']:.2f}")
        
        # Check consecutive losses
        if state.get('consecutive_losses', 0) >= self.max_consecutive_losses:
            issues.append(f"Consecutive losses: {state['consecutive_losses']}")
        
        # Check connection
        if state.get('connection_status') != 'connected':
            issues.append(f"Connection issue: {state.get('connection_status')}")
        
        return issues
    
    async def _handle_critical_issues(self, issues: List[str]):
        """Handle critical issues"""
        issue_text = "\n".join(f"• {i}" for i in issues)
        
        # Send alert
        await telegram_manager.send_error(
            "CRITICAL ISSUES",
            issue_text,
            "critical"
        )
        
        # Auto-decision: Reduce exposure or close all
        decision = SupervisorDecision(
            action=SupervisorAction.REDUCE_EXPOSURE,
            confidence=0.95,
            reasoning=f"Critical issues detected: {issue_text}",
            details={"issues": issues}
        )
        
        await self._execute_decision(decision)
    
    async def _analyze_performance(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze recent performance"""
        return {
            "daily_pnl": state.get('daily_pnl', 0),
            "win_rate": 0.5,  # Will be calculated from actual trades
            "sharpe_ratio": 0.0,
            "max_drawdown": 0.0,
            "regime_accuracy": 0.0
        }
    
    async def _get_ai_recommendation(
        self,
        state: Dict[str, Any],
        performance: Dict[str, Any]
    ) -> SupervisorDecision:
        """Get AI recommendation based on current state"""
        
        analysis = await self.llm.analyze_market(
            market_data=state,
            regime=state.get('regime', 'unknown'),
            positions=state.get('positions', []),
            performance=performance
        )
        
        # Map AI response to action
        action_map = {
            "hold": SupervisorAction.HOLD,
            "increase_exposure": SupervisorAction.INCREASE_EXPOSURE,
            "reduce_exposure": SupervisorAction.REDUCE_EXPOSURE,
            "close_all": SupervisorAction.CLOSE_ALL
        }
        
        action = action_map.get(analysis.get('action', 'hold'), SupervisorAction.HOLD)
        
        return SupervisorDecision(
            action=action,
            confidence=analysis.get('confidence', 0.5),
            reasoning=analysis.get('reasoning', 'No reasoning provided'),
            details=analysis
        )
    
    async def _execute_decision(self, decision: SupervisorDecision):
        """Execute a supervisor decision"""
        logger.info(f"Executing decision: {decision.action.value}")
        
        # Send notification
        action_desc = {
            SupervisorAction.HOLD: "Pozisyon korunuyor",
            SupervisorAction.ADJUST_STRATEGY: "Strateji ayarlanıyor",
            SupervisorAction.REDUCE_EXPOSURE: "Pozisyon azaltılıyor",
            SupervisorAction.INCREASE_EXPOSURE: "Pozisyon artırılıyor",
            SupervisorAction.CLOSE_ALL: "TÜM POZİSYONLAR KAPATILIYOR",
            SupervisorAction.RESTART_SERVICE: "Servis yeniden başlatılıyor",
            SupervisorAction.ALERT_USER: "Kullanıcı uyarılıyor"
        }
        
        await telegram_manager.send_ai_decision(
            decision=action_desc.get(decision.action, decision.action.value),
            reasoning=decision.reasoning,
            action_taken=f"Güven: {decision.confidence*100:.0f}%"
        )
        
        # Execute action (will be connected to trading engine)
        if decision.action == SupervisorAction.CLOSE_ALL:
            # TODO: Connect to trading engine to close all positions
            pass
        elif decision.action == SupervisorAction.REDUCE_EXPOSURE:
            # TODO: Reduce position sizes
            pass
        
        decision.executed = True
    
    async def _handle_supervisor_error(self, error: Exception):
        """Handle errors in the supervisor itself"""
        self.error_count += 1
        
        await telegram_manager.send_error(
            "AI Supervisor Error",
            f"{type(error).__name__}: {str(error)}\n\n{traceback.format_exc()[-500:]}",
            "high"
        )
        
        # Self-healing: If too many errors, notify user
        if self.error_count >= 5:
            await telegram_manager.send_bot_status(
                "warning",
                f"⚠️ AI Supervisor {self.error_count} hata ile karşılaştı. Kontrol gerekebilir."
            )
    
    # ===== External Integration =====
    
    async def report_trade(self, trade: Dict[str, Any]):
        """Report a trade to the supervisor"""
        pnl = trade.get('pnl', 0)
        self.daily_pnl += pnl
        
        if pnl < 0:
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0
        
        # Send to Telegram
        await telegram_manager.send_position_update(
            symbol=trade.get('symbol', 'UNKNOWN'),
            action=trade.get('action', 'TRADE'),
            qty=trade.get('quantity', 0),
            price=trade.get('price', 0),
            pnl=pnl
        )
    
    async def report_signal(self, signal: Dict[str, Any]):
        """Report a trading signal"""
        await telegram_manager.send_signal(
            symbol=signal.get('symbol', 'UNKNOWN'),
            action=signal.get('action', 'HOLD'),
            price=signal.get('price', 0),
            target=signal.get('target'),
            stop_loss=signal.get('stop_loss'),
            confidence=signal.get('confidence', 0),
            reason=signal.get('reason', '')
        )
    
    async def report_regime_change(self, old_regime: str, new_regime: str, confidence: float):
        """Report regime change"""
        await telegram_manager.send_regime_change(old_regime, new_regime, confidence)
    
    async def send_daily_report(self, report: Dict[str, Any]):
        """Send daily report"""
        await telegram_manager.send_daily_report(report)
        # Reset daily counters
        self.daily_pnl = 0.0
        self.consecutive_losses = 0
    
    def get_status(self) -> Dict[str, Any]:
        """Get supervisor status"""
        return {
            "is_running": self.is_running,
            "last_check": self.last_check.isoformat() if self.last_check else None,
            "check_interval_seconds": self.check_interval,
            "error_count": self.error_count,
            "daily_pnl": self.daily_pnl,
            "consecutive_losses": self.consecutive_losses,
            "decisions_count": len(self.decisions_history),
            "last_decision": self.decisions_history[-1].action.value if self.decisions_history else None,
            "llm_status": self.llm.get_status(),
            "thresholds": {
                "max_daily_loss": self.max_daily_loss,
                "max_consecutive_losses": self.max_consecutive_losses,
                "max_drawdown_pct": self.max_drawdown_pct
            }
        }


# Singleton instance
ai_supervisor = AISupervisor()
