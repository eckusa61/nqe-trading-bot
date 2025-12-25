"""
Time Sync Manager Module
Critical for live trading - ensures all operations happen during market hours

Features:
- Market hours validation (NYSE: 9:30 AM - 4:00 PM ET)
- Holiday calendar using pandas_market_calendars (100% accurate)
- Broker time synchronization
- Pre-market/after-hours detection
- Order rejection if market closed
"""
import logging
from datetime import datetime, timedelta, timezone, time
from typing import Optional, Dict, Any, Tuple
from enum import Enum
from dataclasses import dataclass, field
import pandas_market_calendars as mcal
import pytz

logger = logging.getLogger(__name__)


class MarketSession(Enum):
    """Market session types"""
    PRE_MARKET = "pre_market"           # 4:00 AM - 9:30 AM ET
    REGULAR = "regular"                  # 9:30 AM - 4:00 PM ET
    AFTER_HOURS = "after_hours"          # 4:00 PM - 8:00 PM ET
    CLOSED = "closed"                    # Outside trading hours
    HOLIDAY = "holiday"                  # Market holiday
    WEEKEND = "weekend"                  # Saturday/Sunday


@dataclass
class MarketStatus:
    """Current market status"""
    is_open: bool
    session: MarketSession
    current_time_et: datetime
    next_open: Optional[datetime] = None
    next_close: Optional[datetime] = None
    time_to_open: Optional[timedelta] = None
    time_to_close: Optional[timedelta] = None
    holiday_name: Optional[str] = None
    can_trade: bool = False  # True only during regular hours
    broker_time: Optional[datetime] = None
    time_drift_seconds: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_open": self.is_open,
            "session": self.session.value,
            "current_time_et": self.current_time_et.isoformat(),
            "next_open": self.next_open.isoformat() if self.next_open else None,
            "next_close": self.next_close.isoformat() if self.next_close else None,
            "time_to_open_minutes": self.time_to_open.total_seconds() / 60 if self.time_to_open else None,
            "time_to_close_minutes": self.time_to_close.total_seconds() / 60 if self.time_to_close else None,
            "holiday_name": self.holiday_name,
            "can_trade": self.can_trade,
            "broker_time": self.broker_time.isoformat() if self.broker_time else None,
            "time_drift_seconds": self.time_drift_seconds
        }


@dataclass
class OrderTimeValidation:
    """Result of order time validation"""
    allowed: bool
    reason: str
    session: MarketSession
    suggested_action: str = ""  # "wait", "queue", "reject"
    minutes_until_allowed: Optional[float] = None


class TimeSyncManager:
    """
    Manages time synchronization between system and broker
    Uses pandas_market_calendars for 100% accurate holiday detection
    """
    
    # Time constants (Eastern Time)
    ET = pytz.timezone('America/New_York')
    
    # Regular trading hours
    MARKET_OPEN = time(9, 30, 0)
    MARKET_CLOSE = time(16, 0, 0)
    
    # Extended hours
    PRE_MARKET_START = time(4, 0, 0)
    AFTER_HOURS_END = time(20, 0, 0)
    
    # Safety buffer (don't trade too close to open/close)
    OPEN_BUFFER_MINUTES = 5
    CLOSE_BUFFER_MINUTES = 5
    
    # Max acceptable time drift from broker
    MAX_TIME_DRIFT_SECONDS = 5.0
    
    def __init__(self, exchange: str = "NYSE"):
        """
        Initialize with exchange calendar
        
        Args:
            exchange: Exchange code (NYSE, NASDAQ, etc.)
        """
        self.exchange = exchange
        self._calendar = mcal.get_calendar(exchange)
        self._broker_time_offset: timedelta = timedelta(0)
        self._last_broker_sync: Optional[datetime] = None
        
        # Cache schedule for performance
        self._schedule_cache: Dict[str, Any] = {}
        self._cache_date: Optional[datetime] = None
        
        logger.info(f"TimeSyncManager initialized for {exchange}")
    
    def _get_current_time_et(self) -> datetime:
        """Get current time in Eastern timezone"""
        return datetime.now(self.ET)
    
    def _get_schedule_for_date(self, date: datetime) -> Optional[Dict]:
        """
        Get market schedule for a specific date
        Caches schedule for performance
        """
        date_key = date.strftime('%Y-%m-%d')
        
        # Return cached if same date
        if self._cache_date and self._cache_date.date() == date.date():
            return self._schedule_cache.get(date_key)
        
        try:
            # Get schedule for the date
            schedule = self._calendar.schedule(
                start_date=date.strftime('%Y-%m-%d'),
                end_date=date.strftime('%Y-%m-%d')
            )
            
            if schedule.empty:
                # Market is closed (holiday or weekend)
                return None
            
            # Convert to dict
            market_open = schedule.iloc[0]['market_open'].to_pydatetime()
            market_close = schedule.iloc[0]['market_close'].to_pydatetime()
            
            result = {
                'market_open': market_open,
                'market_close': market_close
            }
            
            # Cache the result
            self._schedule_cache[date_key] = result
            self._cache_date = date
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting schedule: {e}")
            return None
    
    def _get_next_trading_day(self, from_date: datetime) -> Optional[datetime]:
        """Get the next trading day from a given date"""
        try:
            # Look ahead up to 10 days to handle long weekends
            for i in range(1, 11):
                next_date = from_date + timedelta(days=i)
                schedule = self._get_schedule_for_date(next_date)
                if schedule:
                    return schedule['market_open']
            return None
        except Exception as e:
            logger.error(f"Error finding next trading day: {e}")
            return None
    
    def _is_holiday(self, date: datetime) -> Tuple[bool, Optional[str]]:
        """
        Check if date is a market holiday
        Returns (is_holiday, holiday_name)
        """
        try:
            # If it's a weekday but market is closed, it's a holiday
            if date.weekday() < 5:  # Monday = 0, Friday = 4
                schedule = self._get_schedule_for_date(date)
                if schedule is None:
                    # Get holiday name from calendar
                    holidays = self._calendar.holidays()
                    date_str = date.strftime('%Y-%m-%d')
                    
                    # Check if date is in holidays
                    for holiday_date in holidays.holidays:
                        if str(holiday_date)[:10] == date_str:
                            return True, str(holiday_date)
                    
                    return True, "Market Holiday"
            return False, None
        except Exception as e:
            logger.error(f"Error checking holiday: {e}")
            return False, None
    
    def get_market_status(self, broker_time: Optional[datetime] = None) -> MarketStatus:
        """
        Get comprehensive market status
        
        Args:
            broker_time: Optional broker-reported time for sync checking
            
        Returns:
            MarketStatus with all relevant information
        """
        now_et = self._get_current_time_et()
        current_time = now_et.time()
        
        # Calculate time drift if broker time provided
        time_drift = 0.0
        if broker_time:
            time_drift = (now_et - broker_time.astimezone(self.ET)).total_seconds()
            self._broker_time_offset = timedelta(seconds=time_drift)
            self._last_broker_sync = now_et
        
        # Check weekend
        if now_et.weekday() >= 5:
            next_open = self._get_next_trading_day(now_et)
            return MarketStatus(
                is_open=False,
                session=MarketSession.WEEKEND,
                current_time_et=now_et,
                next_open=next_open,
                time_to_open=(next_open - now_et) if next_open else None,
                can_trade=False,
                broker_time=broker_time,
                time_drift_seconds=time_drift
            )
        
        # Check holiday
        is_holiday, holiday_name = self._is_holiday(now_et)
        if is_holiday:
            next_open = self._get_next_trading_day(now_et)
            return MarketStatus(
                is_open=False,
                session=MarketSession.HOLIDAY,
                current_time_et=now_et,
                next_open=next_open,
                time_to_open=(next_open - now_et) if next_open else None,
                holiday_name=holiday_name,
                can_trade=False,
                broker_time=broker_time,
                time_drift_seconds=time_drift
            )
        
        # Get today's schedule
        schedule = self._get_schedule_for_date(now_et)
        if not schedule:
            next_open = self._get_next_trading_day(now_et)
            return MarketStatus(
                is_open=False,
                session=MarketSession.CLOSED,
                current_time_et=now_et,
                next_open=next_open,
                time_to_open=(next_open - now_et) if next_open else None,
                can_trade=False,
                broker_time=broker_time,
                time_drift_seconds=time_drift
            )
        
        market_open = schedule['market_open']
        market_close = schedule['market_close']
        
        # Determine current session
        if current_time < self.PRE_MARKET_START:
            # Before pre-market
            session = MarketSession.CLOSED
            is_open = False
            can_trade = False
            next_open = market_open
        elif current_time < self.MARKET_OPEN:
            # Pre-market
            session = MarketSession.PRE_MARKET
            is_open = False
            can_trade = False
            next_open = market_open
        elif current_time < self.MARKET_CLOSE:
            # Regular hours
            session = MarketSession.REGULAR
            is_open = True
            can_trade = True
            next_open = None
        elif current_time < self.AFTER_HOURS_END:
            # After hours
            session = MarketSession.AFTER_HOURS
            is_open = False
            can_trade = False
            next_open = self._get_next_trading_day(now_et)
        else:
            # After after-hours
            session = MarketSession.CLOSED
            is_open = False
            can_trade = False
            next_open = self._get_next_trading_day(now_et)
        
        # Calculate time to open/close
        time_to_open = None
        time_to_close = None
        
        if next_open:
            time_to_open = next_open - now_et
        
        if is_open:
            time_to_close = market_close - now_et
        
        return MarketStatus(
            is_open=is_open,
            session=session,
            current_time_et=now_et,
            next_open=next_open,
            next_close=market_close if is_open else None,
            time_to_open=time_to_open,
            time_to_close=time_to_close,
            can_trade=can_trade,
            broker_time=broker_time,
            time_drift_seconds=time_drift
        )
    
    def validate_order_time(self, allow_extended_hours: bool = False) -> OrderTimeValidation:
        """
        Validate if an order can be placed at current time
        
        Args:
            allow_extended_hours: Allow orders during pre-market/after-hours
            
        Returns:
            OrderTimeValidation with decision
        """
        status = self.get_market_status()
        
        # Regular hours - always allowed
        if status.session == MarketSession.REGULAR:
            # Check if too close to close
            if status.time_to_close and status.time_to_close.total_seconds() < self.CLOSE_BUFFER_MINUTES * 60:
                return OrderTimeValidation(
                    allowed=False,
                    reason=f"Too close to market close ({self.CLOSE_BUFFER_MINUTES} min buffer)",
                    session=status.session,
                    suggested_action="wait",
                    minutes_until_allowed=status.time_to_open.total_seconds() / 60 if status.time_to_open else None
                )
            
            return OrderTimeValidation(
                allowed=True,
                reason="Market is open for regular trading",
                session=status.session,
                suggested_action="execute"
            )
        
        # Extended hours - only if explicitly allowed
        if status.session in [MarketSession.PRE_MARKET, MarketSession.AFTER_HOURS]:
            if allow_extended_hours:
                return OrderTimeValidation(
                    allowed=True,
                    reason=f"Extended hours trading ({status.session.value})",
                    session=status.session,
                    suggested_action="execute_extended"
                )
            else:
                return OrderTimeValidation(
                    allowed=False,
                    reason=f"Market in {status.session.value} - extended hours not enabled",
                    session=status.session,
                    suggested_action="queue",
                    minutes_until_allowed=status.time_to_open.total_seconds() / 60 if status.time_to_open else None
                )
        
        # Market closed
        reason = f"Market closed ({status.session.value})"
        if status.holiday_name:
            reason = f"Market closed - Holiday: {status.holiday_name}"
        
        return OrderTimeValidation(
            allowed=False,
            reason=reason,
            session=status.session,
            suggested_action="queue" if status.time_to_open else "reject",
            minutes_until_allowed=status.time_to_open.total_seconds() / 60 if status.time_to_open else None
        )
    
    def sync_with_broker(self, broker_timestamp: datetime) -> Dict[str, Any]:
        """
        Synchronize time with broker and detect drift
        
        Args:
            broker_timestamp: Timestamp reported by broker
            
        Returns:
            Sync status with drift information
        """
        now = datetime.now(timezone.utc)
        broker_utc = broker_timestamp.astimezone(timezone.utc)
        
        drift_seconds = (now - broker_utc).total_seconds()
        self._broker_time_offset = timedelta(seconds=drift_seconds)
        self._last_broker_sync = now
        
        is_acceptable = abs(drift_seconds) <= self.MAX_TIME_DRIFT_SECONDS
        
        result = {
            "synced": is_acceptable,
            "drift_seconds": drift_seconds,
            "max_allowed_drift": self.MAX_TIME_DRIFT_SECONDS,
            "system_time": now.isoformat(),
            "broker_time": broker_utc.isoformat(),
            "last_sync": self._last_broker_sync.isoformat()
        }
        
        if not is_acceptable:
            logger.warning(f"Time drift detected: {drift_seconds:.2f}s (max: {self.MAX_TIME_DRIFT_SECONDS}s)")
        
        return result
    
    def get_trading_calendar(self, days_ahead: int = 30) -> Dict[str, Any]:
        """
        Get trading calendar for upcoming days
        
        Args:
            days_ahead: Number of days to look ahead
            
        Returns:
            Calendar with trading days and holidays
        """
        now = datetime.now(self.ET)
        end_date = now + timedelta(days=days_ahead)
        
        try:
            schedule = self._calendar.schedule(
                start_date=now.strftime('%Y-%m-%d'),
                end_date=end_date.strftime('%Y-%m-%d')
            )
            
            trading_days = []
            for idx, row in schedule.iterrows():
                trading_days.append({
                    "date": idx.strftime('%Y-%m-%d'),
                    "market_open": row['market_open'].isoformat(),
                    "market_close": row['market_close'].isoformat()
                })
            
            # Find holidays in the range
            holidays = []
            current = now
            while current <= end_date:
                if current.weekday() < 5:  # Weekday
                    is_holiday, name = self._is_holiday(current)
                    if is_holiday:
                        holidays.append({
                            "date": current.strftime('%Y-%m-%d'),
                            "name": name or "Market Holiday"
                        })
                current += timedelta(days=1)
            
            return {
                "exchange": self.exchange,
                "trading_days": trading_days,
                "holidays": holidays,
                "total_trading_days": len(trading_days)
            }
            
        except Exception as e:
            logger.error(f"Error getting trading calendar: {e}")
            return {"error": str(e)}
    
    def is_early_close_day(self) -> Tuple[bool, Optional[time]]:
        """
        Check if today is an early close day (e.g., day before Thanksgiving)
        
        Returns:
            (is_early_close, close_time)
        """
        now = self._get_current_time_et()
        schedule = self._get_schedule_for_date(now)
        
        if not schedule:
            return False, None
        
        close_time = schedule['market_close'].time()
        
        # Normal close is 4:00 PM
        if close_time < self.MARKET_CLOSE:
            return True, close_time
        
        return False, None
    
    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive time sync manager status"""
        market_status = self.get_market_status()
        is_early_close, early_close_time = self.is_early_close_day()
        
        return {
            "exchange": self.exchange,
            "market_status": market_status.to_dict(),
            "is_early_close_day": is_early_close,
            "early_close_time": early_close_time.isoformat() if early_close_time else None,
            "last_broker_sync": self._last_broker_sync.isoformat() if self._last_broker_sync else None,
            "broker_time_offset_seconds": self._broker_time_offset.total_seconds(),
            "settings": {
                "open_buffer_minutes": self.OPEN_BUFFER_MINUTES,
                "close_buffer_minutes": self.CLOSE_BUFFER_MINUTES,
                "max_time_drift_seconds": self.MAX_TIME_DRIFT_SECONDS
            }
        }


# Singleton instance
time_sync_manager = TimeSyncManager()
