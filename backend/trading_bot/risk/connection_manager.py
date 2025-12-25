"""
Connection Manager
Handles IBKR connection resilience
"""
import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, Callable
from enum import Enum

logger = logging.getLogger(__name__)


class ConnectionState(Enum):
    """Connection states"""
    CONNECTED = "connected"
    CONNECTING = "connecting"
    DISCONNECTED = "disconnected"
    RECONNECTING = "reconnecting"
    EMERGENCY = "emergency"


@dataclass
class ConnectionEvent:
    """Connection event record"""
    timestamp: datetime
    event_type: str
    details: str
    duration_seconds: Optional[float] = None


class ConnectionManager:
    """
    Manages IBKR connection with resilience
    
    Features:
    - Heartbeat monitoring
    - Auto-reconnection
    - Emergency shutdown on prolonged loss
    - Alert integration
    """
    
    def __init__(
        self,
        heartbeat_interval: int = 10,
        reconnect_delay: int = 5,
        max_reconnect_attempts: int = 10,
        emergency_threshold_seconds: int = 60,
        on_connection_lost: Optional[Callable] = None,
        on_connection_restored: Optional[Callable] = None,
        on_emergency: Optional[Callable] = None
    ):
        self.heartbeat_interval = heartbeat_interval
        self.reconnect_delay = reconnect_delay
        self.max_reconnect_attempts = max_reconnect_attempts
        self.emergency_threshold_seconds = emergency_threshold_seconds
        
        # Callbacks
        self.on_connection_lost = on_connection_lost
        self.on_connection_restored = on_connection_restored
        self.on_emergency = on_emergency
        
        # State
        self.state = ConnectionState.DISCONNECTED
        self.connection_lost_time: Optional[datetime] = None
        self.last_heartbeat: Optional[datetime] = None
        self.reconnect_attempts = 0
        self.event_history: list[ConnectionEvent] = []
        
        # Monitoring task
        self._monitor_task: Optional[asyncio.Task] = None
        self._running = False
        
        logger.info("ConnectionManager initialized")
    
    def record_event(self, event_type: str, details: str, duration: float = None):
        """Record a connection event"""
        event = ConnectionEvent(
            timestamp=datetime.now(timezone.utc),
            event_type=event_type,
            details=details,
            duration_seconds=duration
        )
        self.event_history.append(event)
        
        # Keep only last 100 events
        if len(self.event_history) > 100:
            self.event_history = self.event_history[-100:]
        
        logger.info(f"Connection event: {event_type} - {details}")
    
    async def start_monitoring(self, connector):
        """Start heartbeat monitoring"""
        self._running = True
        self._monitor_task = asyncio.create_task(self._heartbeat_loop(connector))
        logger.info("Connection monitoring started")
    
    async def stop_monitoring(self):
        """Stop heartbeat monitoring"""
        self._running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        logger.info("Connection monitoring stopped")
    
    async def _heartbeat_loop(self, connector):
        """Main heartbeat monitoring loop"""
        while self._running:
            try:
                # Check connection
                is_connected = connector.is_connected
                
                if is_connected:
                    # Connection OK
                    self.last_heartbeat = datetime.now(timezone.utc)
                    
                    if self.state != ConnectionState.CONNECTED:
                        # Connection restored
                        duration = None
                        if self.connection_lost_time:
                            duration = (datetime.now(timezone.utc) - self.connection_lost_time).total_seconds()
                        
                        self.state = ConnectionState.CONNECTED
                        self.connection_lost_time = None
                        self.reconnect_attempts = 0
                        
                        self.record_event("restored", "Connection restored", duration)
                        
                        if self.on_connection_restored:
                            await self._call_async_or_sync(self.on_connection_restored)
                
                else:
                    # Connection lost
                    if self.state == ConnectionState.CONNECTED:
                        self.connection_lost_time = datetime.now(timezone.utc)
                        self.state = ConnectionState.DISCONNECTED
                        self.record_event("lost", "Connection lost")
                        
                        if self.on_connection_lost:
                            await self._call_async_or_sync(self.on_connection_lost)
                    
                    # Check emergency threshold
                    if self.connection_lost_time:
                        lost_duration = (datetime.now(timezone.utc) - self.connection_lost_time).total_seconds()
                        
                        if lost_duration >= self.emergency_threshold_seconds:
                            if self.state != ConnectionState.EMERGENCY:
                                self.state = ConnectionState.EMERGENCY
                                self.record_event("emergency", f"Connection lost for {lost_duration:.0f}s")
                                
                                if self.on_emergency:
                                    await self._call_async_or_sync(self.on_emergency)
                        
                        else:
                            # Try to reconnect
                            if self.reconnect_attempts < self.max_reconnect_attempts:
                                self.state = ConnectionState.RECONNECTING
                                self.reconnect_attempts += 1
                                
                                logger.info(f"Reconnection attempt {self.reconnect_attempts}/{self.max_reconnect_attempts}")
                                
                                try:
                                    await connector.connect()
                                except Exception as e:
                                    logger.error(f"Reconnection failed: {e}")
                
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")
            
            await asyncio.sleep(self.heartbeat_interval)
    
    async def _call_async_or_sync(self, callback):
        """Call callback whether async or sync"""
        if asyncio.iscoroutinefunction(callback):
            await callback()
        else:
            callback()
    
    def get_status(self) -> Dict:
        """Get connection status"""
        lost_duration = None
        if self.connection_lost_time:
            lost_duration = (datetime.now(timezone.utc) - self.connection_lost_time).total_seconds()
        
        return {
            "state": self.state.value,
            "is_connected": self.state == ConnectionState.CONNECTED,
            "is_emergency": self.state == ConnectionState.EMERGENCY,
            "last_heartbeat": self.last_heartbeat.isoformat() if self.last_heartbeat else None,
            "connection_lost_time": self.connection_lost_time.isoformat() if self.connection_lost_time else None,
            "lost_duration_seconds": lost_duration,
            "reconnect_attempts": self.reconnect_attempts,
            "max_reconnect_attempts": self.max_reconnect_attempts
        }
    
    def get_history(self, limit: int = 20) -> list[Dict]:
        """Get recent connection events"""
        recent = self.event_history[-limit:]
        return [
            {
                "timestamp": e.timestamp.isoformat(),
                "event_type": e.event_type,
                "details": e.details,
                "duration_seconds": e.duration_seconds
            }
            for e in recent
        ]
