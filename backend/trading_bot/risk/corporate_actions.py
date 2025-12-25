"""
Corporate Actions Handler Module
Critical for accurate P&L calculation and position management

Handles:
- Stock splits (forward and reverse)
- Cash dividends
- Stock dividends
- Position quantity adjustments
- Average cost basis adjustments
- Historical price adjustments for backtesting
"""
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from decimal import Decimal, ROUND_DOWN
import json

logger = logging.getLogger(__name__)


class CorporateActionType(Enum):
    """Types of corporate actions"""
    STOCK_SPLIT = "stock_split"           # 2:1, 3:1, etc.
    REVERSE_SPLIT = "reverse_split"        # 1:5, 1:10, etc.
    CASH_DIVIDEND = "cash_dividend"        # Cash payment
    STOCK_DIVIDEND = "stock_dividend"      # Additional shares
    SPINOFF = "spinoff"                    # Company spinoff
    MERGER = "merger"                      # Company merger
    RIGHTS_ISSUE = "rights_issue"          # Rights offering


@dataclass
class CorporateAction:
    """Represents a corporate action event"""
    action_id: str
    symbol: str
    action_type: CorporateActionType
    ex_date: datetime                      # Date action takes effect
    record_date: Optional[datetime] = None  # Record date for eligibility
    payment_date: Optional[datetime] = None # Payment/effective date
    
    # Split-specific fields
    split_ratio_from: int = 1              # Old shares (e.g., 1 for 2:1)
    split_ratio_to: int = 1                # New shares (e.g., 2 for 2:1)
    
    # Dividend-specific fields
    dividend_amount: float = 0.0           # Per share amount
    dividend_type: str = "cash"            # "cash" or "stock"
    
    # Processing status
    processed: bool = False
    processed_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_id": self.action_id,
            "symbol": self.symbol,
            "action_type": self.action_type.value,
            "ex_date": self.ex_date.isoformat(),
            "record_date": self.record_date.isoformat() if self.record_date else None,
            "payment_date": self.payment_date.isoformat() if self.payment_date else None,
            "split_ratio": f"{self.split_ratio_to}:{self.split_ratio_from}",
            "dividend_amount": self.dividend_amount,
            "dividend_type": self.dividend_type,
            "processed": self.processed,
            "processed_at": self.processed_at.isoformat() if self.processed_at else None
        }


@dataclass
class PositionAdjustment:
    """Result of applying a corporate action to a position"""
    symbol: str
    action_type: CorporateActionType
    original_quantity: int
    new_quantity: int
    original_avg_cost: float
    new_avg_cost: float
    cash_adjustment: float = 0.0           # Cash from dividends or fractional shares
    fractional_shares: float = 0.0         # Fractional shares (usually paid as cash)
    adjustment_description: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "action_type": self.action_type.value,
            "original_quantity": self.original_quantity,
            "new_quantity": self.new_quantity,
            "quantity_change": self.new_quantity - self.original_quantity,
            "original_avg_cost": round(self.original_avg_cost, 4),
            "new_avg_cost": round(self.new_avg_cost, 4),
            "cash_adjustment": round(self.cash_adjustment, 2),
            "fractional_shares": round(self.fractional_shares, 6),
            "adjustment_description": self.adjustment_description
        }


@dataclass
class Position:
    """Current position state"""
    symbol: str
    quantity: int
    avg_cost: float
    market_value: float = 0.0
    unrealized_pnl: float = 0.0


class CorporateActionsHandler:
    """
    Handles all corporate actions for positions and historical data
    
    Key responsibilities:
    1. Process stock splits (adjust quantity, avg cost)
    2. Process dividends (add cash to account)
    3. Adjust historical prices for backtesting
    4. Maintain audit trail of all adjustments
    """
    
    def __init__(self):
        self._pending_actions: Dict[str, List[CorporateAction]] = {}  # symbol -> actions
        self._processed_actions: List[CorporateAction] = []
        self._adjustment_history: List[PositionAdjustment] = []
        self._cash_balance_adjustment: float = 0.0
        
        logger.info("CorporateActionsHandler initialized")
    
    def add_corporate_action(self, action: CorporateAction) -> bool:
        """
        Add a corporate action to be processed
        
        Args:
            action: CorporateAction to add
            
        Returns:
            True if added successfully
        """
        symbol = action.symbol
        
        if symbol not in self._pending_actions:
            self._pending_actions[symbol] = []
        
        # Check for duplicates
        for existing in self._pending_actions[symbol]:
            if existing.action_id == action.action_id:
                logger.warning(f"Duplicate action ID: {action.action_id}")
                return False
        
        self._pending_actions[symbol].append(action)
        logger.info(f"Added corporate action: {action.action_type.value} for {symbol}")
        return True
    
    def process_split(
        self,
        position: Position,
        action: CorporateAction
    ) -> PositionAdjustment:
        """
        Process a stock split for a position
        
        For a 2:1 split:
        - Quantity doubles
        - Average cost halves
        - Total position value stays the same
        
        For a 1:5 reverse split:
        - Quantity divides by 5
        - Average cost multiplies by 5
        - Fractional shares paid as cash
        """
        original_qty = position.quantity
        original_cost = position.avg_cost
        
        # Calculate split multiplier
        # For 2:1 split: ratio_to=2, ratio_from=1 -> multiplier=2
        # For 1:5 reverse: ratio_to=1, ratio_from=5 -> multiplier=0.2
        multiplier = Decimal(str(action.split_ratio_to)) / Decimal(str(action.split_ratio_from))
        
        # Calculate new quantity
        new_qty_decimal = Decimal(str(original_qty)) * multiplier
        new_qty = int(new_qty_decimal.to_integral_value(rounding=ROUND_DOWN))
        
        # Fractional shares (paid as cash at current market price)
        fractional = float(new_qty_decimal - Decimal(str(new_qty)))
        
        # Adjust average cost (inverse of quantity multiplier)
        new_cost = float(Decimal(str(original_cost)) / multiplier)
        
        # Cash for fractional shares (estimate using adjusted cost)
        cash_for_fractional = fractional * new_cost if fractional > 0 else 0
        
        description = f"{action.split_ratio_to}:{action.split_ratio_from} split"
        if action.action_type == CorporateActionType.REVERSE_SPLIT:
            description = f"1:{action.split_ratio_from // action.split_ratio_to} reverse split"
        
        adjustment = PositionAdjustment(
            symbol=position.symbol,
            action_type=action.action_type,
            original_quantity=original_qty,
            new_quantity=new_qty,
            original_avg_cost=original_cost,
            new_avg_cost=new_cost,
            cash_adjustment=cash_for_fractional,
            fractional_shares=fractional,
            adjustment_description=description
        )
        
        # Update cash balance
        self._cash_balance_adjustment += cash_for_fractional
        
        # Track adjustment
        self._adjustment_history.append(adjustment)
        
        logger.info(
            f"Processed {description} for {position.symbol}: "
            f"{original_qty} -> {new_qty} shares, "
            f"${original_cost:.2f} -> ${new_cost:.2f} avg cost"
        )
        
        return adjustment
    
    def process_dividend(
        self,
        position: Position,
        action: CorporateAction,
        current_price: Optional[float] = None
    ) -> PositionAdjustment:
        """
        Process a dividend payment for a position
        
        Cash dividend:
        - Add cash to account
        - Position unchanged
        
        Stock dividend:
        - Add shares to position
        - Adjust average cost
        """
        original_qty = position.quantity
        original_cost = position.avg_cost
        
        if action.dividend_type == "cash":
            # Cash dividend - simple cash addition
            cash_payment = original_qty * action.dividend_amount
            
            adjustment = PositionAdjustment(
                symbol=position.symbol,
                action_type=action.action_type,
                original_quantity=original_qty,
                new_quantity=original_qty,  # No change
                original_avg_cost=original_cost,
                new_avg_cost=original_cost,  # No change
                cash_adjustment=cash_payment,
                adjustment_description=f"Cash dividend: ${action.dividend_amount}/share"
            )
            
            self._cash_balance_adjustment += cash_payment
            
            logger.info(
                f"Processed cash dividend for {position.symbol}: "
                f"${cash_payment:.2f} ({original_qty} x ${action.dividend_amount})"
            )
            
        else:
            # Stock dividend - add shares
            # dividend_amount represents percentage (e.g., 0.05 = 5% stock dividend)
            additional_shares = int(original_qty * action.dividend_amount)
            new_qty = original_qty + additional_shares
            
            # Adjust cost basis
            # Total cost stays the same, spread over more shares
            total_cost = original_qty * original_cost
            new_cost = total_cost / new_qty if new_qty > 0 else original_cost
            
            adjustment = PositionAdjustment(
                symbol=position.symbol,
                action_type=action.action_type,
                original_quantity=original_qty,
                new_quantity=new_qty,
                original_avg_cost=original_cost,
                new_avg_cost=new_cost,
                cash_adjustment=0,
                adjustment_description=f"Stock dividend: {action.dividend_amount * 100:.1f}% ({additional_shares} shares)"
            )
            
            logger.info(
                f"Processed stock dividend for {position.symbol}: "
                f"{original_qty} -> {new_qty} shares"
            )
        
        self._adjustment_history.append(adjustment)
        return adjustment
    
    def apply_action_to_position(
        self,
        position: Position,
        action: CorporateAction,
        current_price: Optional[float] = None
    ) -> Tuple[Position, PositionAdjustment]:
        """
        Apply a corporate action to a position and return updated position
        
        Args:
            position: Current position
            action: Corporate action to apply
            current_price: Current market price (for fractional share valuation)
            
        Returns:
            Tuple of (updated_position, adjustment_details)
        """
        if action.action_type in [CorporateActionType.STOCK_SPLIT, CorporateActionType.REVERSE_SPLIT]:
            adjustment = self.process_split(position, action)
        elif action.action_type in [CorporateActionType.CASH_DIVIDEND, CorporateActionType.STOCK_DIVIDEND]:
            adjustment = self.process_dividend(position, action, current_price)
        else:
            # Unsupported action type - no change
            logger.warning(f"Unsupported action type: {action.action_type}")
            adjustment = PositionAdjustment(
                symbol=position.symbol,
                action_type=action.action_type,
                original_quantity=position.quantity,
                new_quantity=position.quantity,
                original_avg_cost=position.avg_cost,
                new_avg_cost=position.avg_cost,
                adjustment_description=f"Unsupported action: {action.action_type.value}"
            )
        
        # Mark action as processed
        action.processed = True
        action.processed_at = datetime.now(timezone.utc)
        self._processed_actions.append(action)
        
        # Create updated position
        updated_position = Position(
            symbol=position.symbol,
            quantity=adjustment.new_quantity,
            avg_cost=adjustment.new_avg_cost
        )
        
        return updated_position, adjustment
    
    def adjust_historical_price(
        self,
        price: float,
        action: CorporateAction
    ) -> float:
        """
        Adjust a historical price for a corporate action
        Used for backtesting to ensure apples-to-apples comparison
        
        For a 2:1 split:
        - Pre-split prices should be halved
        
        Args:
            price: Original historical price
            action: Corporate action that occurred after this price
            
        Returns:
            Adjusted price
        """
        if action.action_type == CorporateActionType.STOCK_SPLIT:
            multiplier = action.split_ratio_from / action.split_ratio_to
            return price * multiplier
        
        elif action.action_type == CorporateActionType.REVERSE_SPLIT:
            multiplier = action.split_ratio_to / action.split_ratio_from
            return price * multiplier
        
        # Dividends don't affect historical prices for backtesting
        return price
    
    def adjust_historical_volume(
        self,
        volume: int,
        action: CorporateAction
    ) -> int:
        """
        Adjust historical volume for a corporate action
        
        Args:
            volume: Original historical volume
            action: Corporate action that occurred after this volume
            
        Returns:
            Adjusted volume
        """
        if action.action_type == CorporateActionType.STOCK_SPLIT:
            multiplier = action.split_ratio_to / action.split_ratio_from
            return int(volume * multiplier)
        
        elif action.action_type == CorporateActionType.REVERSE_SPLIT:
            multiplier = action.split_ratio_from / action.split_ratio_to
            return int(volume * multiplier)
        
        return volume
    
    def get_pending_actions(self, symbol: Optional[str] = None) -> List[CorporateAction]:
        """
        Get pending corporate actions
        
        Args:
            symbol: Optional symbol filter
            
        Returns:
            List of pending actions
        """
        if symbol:
            return self._pending_actions.get(symbol, [])
        
        all_actions = []
        for actions in self._pending_actions.values():
            all_actions.extend(actions)
        return all_actions
    
    def get_actions_for_date(
        self,
        date: datetime,
        symbol: Optional[str] = None
    ) -> List[CorporateAction]:
        """
        Get corporate actions effective on a specific date
        
        Args:
            date: Date to check
            symbol: Optional symbol filter
            
        Returns:
            List of actions effective on that date
        """
        result = []
        actions = self.get_pending_actions(symbol)
        
        for action in actions:
            if action.ex_date.date() == date.date():
                result.append(action)
        
        return result
    
    def get_cash_adjustment(self) -> float:
        """
        Get total cash adjustment from corporate actions
        (dividends + fractional share payments)
        """
        return self._cash_balance_adjustment
    
    def reset_cash_adjustment(self) -> float:
        """
        Get and reset cash adjustment (for after applying to account)
        """
        adjustment = self._cash_balance_adjustment
        self._cash_balance_adjustment = 0.0
        return adjustment
    
    def get_adjustment_history(
        self,
        symbol: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get history of position adjustments
        
        Args:
            symbol: Optional symbol filter
            limit: Maximum number of records
            
        Returns:
            List of adjustment records
        """
        history = self._adjustment_history
        
        if symbol:
            history = [h for h in history if h.symbol == symbol]
        
        return [h.to_dict() for h in history[-limit:]]
    
    def get_status(self) -> Dict[str, Any]:
        """Get handler status"""
        pending_by_symbol = {
            symbol: len(actions) 
            for symbol, actions in self._pending_actions.items()
        }
        
        return {
            "pending_actions_count": sum(pending_by_symbol.values()),
            "pending_by_symbol": pending_by_symbol,
            "processed_actions_count": len(self._processed_actions),
            "total_adjustments": len(self._adjustment_history),
            "pending_cash_adjustment": round(self._cash_balance_adjustment, 2),
            "last_adjustment": self._adjustment_history[-1].to_dict() if self._adjustment_history else None
        }
    
    def create_split_action(
        self,
        symbol: str,
        ratio_to: int,
        ratio_from: int,
        ex_date: datetime,
        action_id: Optional[str] = None
    ) -> CorporateAction:
        """
        Helper to create a stock split action
        
        Args:
            symbol: Stock symbol
            ratio_to: New share count (e.g., 2 for 2:1)
            ratio_from: Old share count (e.g., 1 for 2:1)
            ex_date: Ex-dividend date
            action_id: Optional custom ID
            
        Returns:
            CorporateAction for the split
        """
        is_reverse = ratio_to < ratio_from
        action_type = CorporateActionType.REVERSE_SPLIT if is_reverse else CorporateActionType.STOCK_SPLIT
        
        return CorporateAction(
            action_id=action_id or f"{symbol}_SPLIT_{ex_date.strftime('%Y%m%d')}",
            symbol=symbol,
            action_type=action_type,
            ex_date=ex_date,
            split_ratio_from=ratio_from,
            split_ratio_to=ratio_to
        )
    
    def create_dividend_action(
        self,
        symbol: str,
        amount: float,
        ex_date: datetime,
        payment_date: Optional[datetime] = None,
        is_stock_dividend: bool = False,
        action_id: Optional[str] = None
    ) -> CorporateAction:
        """
        Helper to create a dividend action
        
        Args:
            symbol: Stock symbol
            amount: Dividend amount per share (or percentage for stock dividend)
            ex_date: Ex-dividend date
            payment_date: Payment date
            is_stock_dividend: True if stock dividend
            action_id: Optional custom ID
            
        Returns:
            CorporateAction for the dividend
        """
        action_type = CorporateActionType.STOCK_DIVIDEND if is_stock_dividend else CorporateActionType.CASH_DIVIDEND
        dividend_type = "stock" if is_stock_dividend else "cash"
        
        return CorporateAction(
            action_id=action_id or f"{symbol}_DIV_{ex_date.strftime('%Y%m%d')}",
            symbol=symbol,
            action_type=action_type,
            ex_date=ex_date,
            payment_date=payment_date,
            dividend_amount=amount,
            dividend_type=dividend_type
        )


# Singleton instance
corporate_actions_handler = CorporateActionsHandler()
