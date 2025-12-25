"""
PDT Rule Enforcer
Pattern Day Trader rules for US accounts < $25K
"""
import logging
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class DayTrade:
    """Record of a day trade"""
    symbol: str
    buy_time: datetime
    sell_time: datetime
    quantity: int
    buy_price: float
    sell_price: float


class PDTEnforcer:
    """
    Enforces Pattern Day Trader rules
    
    Rules:
    - Account < $25K: Max 3 day trades per 5 business days
    - 4th day trade = account marked as PDT → 90-day restriction
    
    Day trade = Buy and sell same security same day
    """
    
    def __init__(
        self,
        pdt_threshold: float = 25000.0,
        max_day_trades: int = 3,
        lookback_days: int = 5
    ):
        self.pdt_threshold = pdt_threshold
        self.max_day_trades = max_day_trades
        self.lookback_days = lookback_days
        
        # Track day trades
        self.day_trades: List[DayTrade] = []
        
        # Track open positions (for detecting same-day sells)
        self.intraday_buys: Dict[str, List[Dict]] = {}  # symbol -> [{time, qty, price}]
        
        logger.info("PDTEnforcer initialized")
    
    def _get_recent_day_trades(self) -> List[DayTrade]:
        """Get day trades in last 5 business days"""
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)  # Extra buffer for weekends
        
        recent = [
            dt for dt in self.day_trades
            if dt.sell_time >= cutoff
        ]
        
        # Only count business days
        business_day_trades = []
        for dt in recent:
            # Simple weekday check (Mon=0, Sun=6)
            if dt.sell_time.weekday() < 5:
                business_day_trades.append(dt)
        
        return business_day_trades[-self.max_day_trades * 2:]  # Keep reasonable limit
    
    def get_day_trade_count(self) -> int:
        """Get number of day trades in lookback period"""
        return len(self._get_recent_day_trades())
    
    def can_day_trade(self, account_value: float) -> Dict:
        """
        Check if account can make another day trade
        
        Returns:
            {
                "allowed": bool,
                "reason": str,
                "day_trades_used": int,
                "day_trades_remaining": int,
                "is_pdt_account": bool
            }
        """
        day_trade_count = self.get_day_trade_count()
        
        # Account >= $25K: No PDT restrictions
        if account_value >= self.pdt_threshold:
            return {
                "allowed": True,
                "reason": f"Account value ${account_value:,.0f} >= ${self.pdt_threshold:,.0f} PDT threshold",
                "day_trades_used": day_trade_count,
                "day_trades_remaining": float('inf'),
                "is_pdt_account": False
            }
        
        # Account < $25K: PDT rules apply
        remaining = self.max_day_trades - day_trade_count
        
        if day_trade_count >= self.max_day_trades:
            return {
                "allowed": False,
                "reason": f"PDT limit reached: {day_trade_count}/{self.max_day_trades} day trades in last {self.lookback_days} days",
                "day_trades_used": day_trade_count,
                "day_trades_remaining": 0,
                "is_pdt_account": True
            }
        
        return {
            "allowed": True,
            "reason": f"PDT compliant: {day_trade_count}/{self.max_day_trades} day trades used",
            "day_trades_used": day_trade_count,
            "day_trades_remaining": remaining,
            "is_pdt_account": True
        }
    
    def check_before_trade(
        self,
        symbol: str,
        side: str,
        account_value: float
    ) -> Dict:
        """
        Check if trade would create a day trade
        
        Call this BEFORE placing a sell order
        """
        if side.upper() != "SELL":
            return {"allowed": True, "reason": "Buy orders don't trigger PDT"}
        
        # Check if we have same-day buys for this symbol
        if symbol not in self.intraday_buys:
            return {"allowed": True, "reason": "No intraday buys for this symbol"}
        
        today = datetime.now(timezone.utc).date()
        todays_buys = [
            b for b in self.intraday_buys[symbol]
            if b["time"].date() == today
        ]
        
        if not todays_buys:
            return {"allowed": True, "reason": "No same-day buys for this symbol"}
        
        # This would be a day trade - check if allowed
        pdt_check = self.can_day_trade(account_value)
        
        if not pdt_check["allowed"]:
            return {
                "allowed": False,
                "reason": f"BLOCKED: Selling {symbol} would trigger PDT violation. {pdt_check['reason']}",
                "would_be_day_trade": True,
                "pdt_status": pdt_check
            }
        
        return {
            "allowed": True,
            "reason": f"Day trade allowed ({pdt_check['day_trades_used'] + 1}/{self.max_day_trades})",
            "would_be_day_trade": True,
            "pdt_status": pdt_check
        }
    
    def record_buy(self, symbol: str, quantity: int, price: float):
        """Record a buy for intraday tracking"""
        if symbol not in self.intraday_buys:
            self.intraday_buys[symbol] = []
        
        self.intraday_buys[symbol].append({
            "time": datetime.now(timezone.utc),
            "qty": quantity,
            "price": price
        })
        
        logger.debug(f"PDT: Recorded buy {quantity} {symbol} @ ${price}")
    
    def record_sell(self, symbol: str, quantity: int, price: float):
        """
        Record a sell and check if it completes a day trade
        """
        if symbol not in self.intraday_buys:
            return
        
        now = datetime.now(timezone.utc)
        today = now.date()
        
        # Find matching same-day buy
        todays_buys = [
            b for b in self.intraday_buys[symbol]
            if b["time"].date() == today
        ]
        
        if todays_buys:
            # This is a day trade
            buy = todays_buys[0]  # Match FIFO
            
            day_trade = DayTrade(
                symbol=symbol,
                buy_time=buy["time"],
                sell_time=now,
                quantity=min(quantity, buy["qty"]),
                buy_price=buy["price"],
                sell_price=price
            )
            
            self.day_trades.append(day_trade)
            logger.warning(f"PDT: Day trade recorded - {symbol}")
            
            # Remove matched buy
            self.intraday_buys[symbol].remove(buy)
    
    def cleanup_old_data(self):
        """Clean up old tracking data"""
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        
        # Clean day trades
        self.day_trades = [
            dt for dt in self.day_trades
            if dt.sell_time >= cutoff
        ]
        
        # Clean intraday buys (only keep today)
        today = datetime.now(timezone.utc).date()
        for symbol in list(self.intraday_buys.keys()):
            self.intraday_buys[symbol] = [
                b for b in self.intraday_buys[symbol]
                if b["time"].date() == today
            ]
            if not self.intraday_buys[symbol]:
                del self.intraday_buys[symbol]
    
    def get_status(self, account_value: float) -> Dict:
        """Get current PDT status"""
        pdt_check = self.can_day_trade(account_value)
        
        return {
            "account_value": account_value,
            "pdt_threshold": self.pdt_threshold,
            "is_pdt_restricted": account_value < self.pdt_threshold,
            "day_trades_count": self.get_day_trade_count(),
            "max_day_trades": self.max_day_trades,
            "day_trades_remaining": pdt_check["day_trades_remaining"],
            "can_day_trade": pdt_check["allowed"],
            "recent_day_trades": [
                {
                    "symbol": dt.symbol,
                    "date": dt.sell_time.date().isoformat(),
                    "quantity": dt.quantity
                }
                for dt in self._get_recent_day_trades()
            ]
        }
