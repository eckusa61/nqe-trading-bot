"""
Reconciliation Engine
Ensures system state matches broker state
"""
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


class DiscrepancySeverity(Enum):
    """Severity levels for discrepancies"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class Discrepancy:
    """Position or cash discrepancy"""
    timestamp: datetime
    discrepancy_type: str  # "position" or "cash"
    symbol: Optional[str]
    broker_value: float
    system_value: float
    difference: float
    severity: DiscrepancySeverity
    resolved: bool = False
    resolution: str = ""


class ReconciliationEngine:
    """
    Reconciles system state with broker state
    
    Every 5 minutes:
    - Compare positions
    - Compare cash
    - Alert on discrepancies
    - Auto-correct system state (broker is source of truth)
    """
    
    def __init__(
        self,
        position_tolerance: int = 1,  # Shares tolerance
        cash_tolerance: float = 10.0,  # Dollar tolerance
        critical_position_diff: int = 10,
        critical_cash_diff: float = 1000.0
    ):
        self.position_tolerance = position_tolerance
        self.cash_tolerance = cash_tolerance
        self.critical_position_diff = critical_position_diff
        self.critical_cash_diff = critical_cash_diff
        
        self.discrepancy_history: List[Discrepancy] = []
        self.last_reconciliation: Optional[datetime] = None
        self.consecutive_failures = 0
        
        logger.info("ReconciliationEngine initialized")
    
    def reconcile_positions(
        self,
        broker_positions: Dict[str, int],
        system_positions: Dict[str, int]
    ) -> Tuple[List[Discrepancy], Dict[str, int]]:
        """
        Reconcile positions between broker and system
        
        Args:
            broker_positions: {symbol: quantity} from broker
            system_positions: {symbol: quantity} from our system
        
        Returns:
            (discrepancies, corrected_positions)
        """
        discrepancies = []
        corrected_positions = broker_positions.copy()  # Broker is source of truth
        
        # Get all symbols from both sources
        all_symbols = set(broker_positions.keys()) | set(system_positions.keys())
        
        for symbol in all_symbols:
            broker_qty = broker_positions.get(symbol, 0)
            system_qty = system_positions.get(symbol, 0)
            
            diff = broker_qty - system_qty
            
            if abs(diff) > self.position_tolerance:
                # Determine severity
                if abs(diff) >= self.critical_position_diff:
                    severity = DiscrepancySeverity.CRITICAL
                elif abs(diff) > self.position_tolerance * 2:
                    severity = DiscrepancySeverity.WARNING
                else:
                    severity = DiscrepancySeverity.INFO
                
                discrepancy = Discrepancy(
                    timestamp=datetime.now(timezone.utc),
                    discrepancy_type="position",
                    symbol=symbol,
                    broker_value=float(broker_qty),
                    system_value=float(system_qty),
                    difference=float(diff),
                    severity=severity,
                    resolution=f"System adjusted from {system_qty} to {broker_qty}"
                )
                
                discrepancies.append(discrepancy)
                self.discrepancy_history.append(discrepancy)
                
                logger.log(
                    logging.CRITICAL if severity == DiscrepancySeverity.CRITICAL else logging.WARNING,
                    f"Position discrepancy [{severity.value}]: {symbol} - "
                    f"Broker: {broker_qty}, System: {system_qty}, Diff: {diff}"
                )
        
        return discrepancies, corrected_positions
    
    def reconcile_cash(
        self,
        broker_cash: float,
        system_cash: float
    ) -> Tuple[Optional[Discrepancy], float]:
        """
        Reconcile cash between broker and system
        
        Returns:
            (discrepancy if any, corrected_cash)
        """
        diff = broker_cash - system_cash
        
        if abs(diff) > self.cash_tolerance:
            # Determine severity
            if abs(diff) >= self.critical_cash_diff:
                severity = DiscrepancySeverity.CRITICAL
            elif abs(diff) > self.cash_tolerance * 10:
                severity = DiscrepancySeverity.WARNING
            else:
                severity = DiscrepancySeverity.INFO
            
            discrepancy = Discrepancy(
                timestamp=datetime.now(timezone.utc),
                discrepancy_type="cash",
                symbol=None,
                broker_value=broker_cash,
                system_value=system_cash,
                difference=diff,
                severity=severity,
                resolution=f"System adjusted from ${system_cash:.2f} to ${broker_cash:.2f}"
            )
            
            self.discrepancy_history.append(discrepancy)
            
            logger.log(
                logging.CRITICAL if severity == DiscrepancySeverity.CRITICAL else logging.WARNING,
                f"Cash discrepancy [{severity.value}]: "
                f"Broker: ${broker_cash:.2f}, System: ${system_cash:.2f}, Diff: ${diff:.2f}"
            )
            
            return discrepancy, broker_cash
        
        return None, system_cash
    
    def full_reconciliation(
        self,
        broker_positions: Dict[str, int],
        system_positions: Dict[str, int],
        broker_cash: float,
        system_cash: float
    ) -> Dict:
        """
        Perform full reconciliation
        
        Returns dict with:
        - position_discrepancies
        - cash_discrepancy
        - corrected_positions
        - corrected_cash
        - has_critical_issues
        - should_halt_trading
        """
        self.last_reconciliation = datetime.now(timezone.utc)
        
        # Reconcile positions
        position_discrepancies, corrected_positions = self.reconcile_positions(
            broker_positions, system_positions
        )
        
        # Reconcile cash
        cash_discrepancy, corrected_cash = self.reconcile_cash(broker_cash, system_cash)
        
        # Check for critical issues
        has_critical = any(d.severity == DiscrepancySeverity.CRITICAL for d in position_discrepancies)
        if cash_discrepancy and cash_discrepancy.severity == DiscrepancySeverity.CRITICAL:
            has_critical = True
        
        # Determine if should halt trading
        should_halt = has_critical and self.consecutive_failures >= 2
        
        if has_critical:
            self.consecutive_failures += 1
        else:
            self.consecutive_failures = 0
        
        result = {
            "timestamp": self.last_reconciliation.isoformat(),
            "position_discrepancies": [
                {
                    "symbol": d.symbol,
                    "broker": d.broker_value,
                    "system": d.system_value,
                    "diff": d.difference,
                    "severity": d.severity.value
                }
                for d in position_discrepancies
            ],
            "cash_discrepancy": {
                "broker": cash_discrepancy.broker_value if cash_discrepancy else broker_cash,
                "system": cash_discrepancy.system_value if cash_discrepancy else system_cash,
                "diff": cash_discrepancy.difference if cash_discrepancy else 0,
                "severity": cash_discrepancy.severity.value if cash_discrepancy else "none"
            } if cash_discrepancy else None,
            "corrected_positions": corrected_positions,
            "corrected_cash": corrected_cash,
            "has_critical_issues": has_critical,
            "should_halt_trading": should_halt,
            "consecutive_failures": self.consecutive_failures
        }
        
        if should_halt:
            logger.critical("RECONCILIATION: Multiple critical failures - HALT TRADING")
        
        return result
    
    def get_history(self, limit: int = 50) -> List[Dict]:
        """Get recent discrepancy history"""
        recent = self.discrepancy_history[-limit:]
        return [
            {
                "timestamp": d.timestamp.isoformat(),
                "type": d.discrepancy_type,
                "symbol": d.symbol,
                "broker": d.broker_value,
                "system": d.system_value,
                "diff": d.difference,
                "severity": d.severity.value,
                "resolution": d.resolution
            }
            for d in recent
        ]
    
    def get_status(self) -> Dict:
        """Get reconciliation status"""
        critical_count = sum(
            1 for d in self.discrepancy_history[-20:]
            if d.severity == DiscrepancySeverity.CRITICAL
        )
        
        return {
            "last_reconciliation": self.last_reconciliation.isoformat() if self.last_reconciliation else None,
            "consecutive_failures": self.consecutive_failures,
            "total_discrepancies": len(self.discrepancy_history),
            "recent_critical_count": critical_count,
            "is_healthy": self.consecutive_failures == 0 and critical_count == 0
        }
