"""
Alerting Module
Webhook alerts for Slack/Discord
"""
import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Callable
from enum import Enum
import aiohttp
import json

logger = logging.getLogger(__name__)


class AlertLevel(Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertType(Enum):
    """Types of alerts"""
    DRAWDOWN_WARNING = "drawdown_warning"
    DRAWDOWN_CRITICAL = "drawdown_critical"
    KILL_SWITCH_TRIGGERED = "kill_switch_triggered"
    CONNECTION_LOST = "connection_lost"
    CONNECTION_RESTORED = "connection_restored"
    DATA_ANOMALY = "data_anomaly"
    STRATEGY_FAILURE = "strategy_failure"
    TRADE_EXECUTED = "trade_executed"
    SYSTEM_ERROR = "system_error"


@dataclass
class Alert:
    """Alert data structure"""
    alert_type: AlertType
    level: AlertLevel
    title: str
    message: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    data: Optional[Dict] = None
    
    def to_dict(self) -> Dict:
        return {
            "alert_type": self.alert_type.value,
            "level": self.level.value,
            "title": self.title,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data
        }


@dataclass
class WebhookConfig:
    """Webhook configuration"""
    slack_url: Optional[str] = None
    discord_url: Optional[str] = None
    enabled: bool = True
    
    # Alert level thresholds
    min_level: AlertLevel = AlertLevel.WARNING
    
    # Rate limiting (alerts per minute)
    rate_limit: int = 10
    
    # Which alert types to send
    enabled_alerts: List[AlertType] = field(default_factory=lambda: [
        AlertType.DRAWDOWN_WARNING,
        AlertType.DRAWDOWN_CRITICAL,
        AlertType.KILL_SWITCH_TRIGGERED,
        AlertType.CONNECTION_LOST,
        AlertType.DATA_ANOMALY,
        AlertType.STRATEGY_FAILURE,
    ])


class AlertManager:
    """
    Manages alert delivery to Slack/Discord webhooks
    """
    
    def __init__(self, config: Optional[WebhookConfig] = None):
        self.config = config or WebhookConfig()
        self._alert_history: List[Alert] = []
        self._rate_limit_window: List[datetime] = []
        self._session: Optional[aiohttp.ClientSession] = None
        logger.info("AlertManager initialized")
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session
    
    async def close(self):
        """Close the session"""
        if self._session and not self._session.closed:
            await self._session.close()
    
    def _check_rate_limit(self) -> bool:
        """Check if we're within rate limits"""
        now = datetime.now(timezone.utc)
        # Remove old entries (older than 1 minute)
        self._rate_limit_window = [
            t for t in self._rate_limit_window
            if (now - t).total_seconds() < 60
        ]
        
        if len(self._rate_limit_window) >= self.config.rate_limit:
            logger.warning("Alert rate limit exceeded")
            return False
        
        self._rate_limit_window.append(now)
        return True
    
    def _should_send_alert(self, alert: Alert) -> bool:
        """Check if alert should be sent based on config"""
        if not self.config.enabled:
            return False
        
        if alert.alert_type not in self.config.enabled_alerts:
            return False
        
        # Check level threshold
        level_order = {AlertLevel.INFO: 0, AlertLevel.WARNING: 1, AlertLevel.CRITICAL: 2}
        if level_order[alert.level] < level_order[self.config.min_level]:
            return False
        
        return self._check_rate_limit()
    
    def _format_slack_message(self, alert: Alert) -> Dict:
        """Format alert for Slack webhook"""
        color_map = {
            AlertLevel.INFO: "#3b82f6",      # Blue
            AlertLevel.WARNING: "#f59e0b",    # Yellow/Orange
            AlertLevel.CRITICAL: "#ef4444"    # Red
        }
        
        emoji_map = {
            AlertType.DRAWDOWN_WARNING: "⚠️",
            AlertType.DRAWDOWN_CRITICAL: "🔴",
            AlertType.KILL_SWITCH_TRIGGERED: "🛑",
            AlertType.CONNECTION_LOST: "🔌",
            AlertType.CONNECTION_RESTORED: "✅",
            AlertType.DATA_ANOMALY: "📊",
            AlertType.STRATEGY_FAILURE: "❌",
            AlertType.TRADE_EXECUTED: "💹",
            AlertType.SYSTEM_ERROR: "🚨",
        }
        
        emoji = emoji_map.get(alert.alert_type, "📢")
        
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{emoji} {alert.title}",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": alert.message
                }
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Level:* {alert.level.value.upper()} | *Time:* {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}"
                    }
                ]
            }
        ]
        
        # Add data fields if present
        if alert.data:
            fields_text = "\n".join([f"• *{k}:* {v}" for k, v in alert.data.items()])
            blocks.insert(2, {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": fields_text
                }
            })
        
        return {
            "attachments": [{
                "color": color_map[alert.level],
                "blocks": blocks
            }]
        }
    
    def _format_discord_message(self, alert: Alert) -> Dict:
        """Format alert for Discord webhook"""
        color_map = {
            AlertLevel.INFO: 3447003,      # Blue
            AlertLevel.WARNING: 16776960,   # Yellow
            AlertLevel.CRITICAL: 15548997   # Red
        }
        
        emoji_map = {
            AlertType.DRAWDOWN_WARNING: "⚠️",
            AlertType.DRAWDOWN_CRITICAL: "🔴",
            AlertType.KILL_SWITCH_TRIGGERED: "🛑",
            AlertType.CONNECTION_LOST: "🔌",
            AlertType.CONNECTION_RESTORED: "✅",
            AlertType.DATA_ANOMALY: "📊",
            AlertType.STRATEGY_FAILURE: "❌",
            AlertType.TRADE_EXECUTED: "💹",
            AlertType.SYSTEM_ERROR: "🚨",
        }
        
        emoji = emoji_map.get(alert.alert_type, "📢")
        
        embed = {
            "title": f"{emoji} {alert.title}",
            "description": alert.message,
            "color": color_map[alert.level],
            "timestamp": alert.timestamp.isoformat(),
            "footer": {
                "text": f"TradingBot | {alert.level.value.upper()}"
            }
        }
        
        # Add data fields if present
        if alert.data:
            embed["fields"] = [
                {"name": k, "value": str(v), "inline": True}
                for k, v in alert.data.items()
            ]
        
        return {
            "embeds": [embed]
        }
    
    async def send_alert(self, alert: Alert) -> bool:
        """
        Send alert to configured webhooks
        Returns True if at least one webhook succeeded
        """
        if not self._should_send_alert(alert):
            return False
        
        self._alert_history.append(alert)
        
        # Keep only last 100 alerts in history
        if len(self._alert_history) > 100:
            self._alert_history = self._alert_history[-100:]
        
        session = await self._get_session()
        success = False
        
        # Send to Slack
        if self.config.slack_url:
            try:
                payload = self._format_slack_message(alert)
                async with session.post(
                    self.config.slack_url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status == 200:
                        logger.info(f"Slack alert sent: {alert.title}")
                        success = True
                    else:
                        logger.error(f"Slack webhook failed: {resp.status}")
            except Exception as e:
                logger.error(f"Slack webhook error: {e}")
        
        # Send to Discord
        if self.config.discord_url:
            try:
                payload = self._format_discord_message(alert)
                async with session.post(
                    self.config.discord_url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status in [200, 204]:
                        logger.info(f"Discord alert sent: {alert.title}")
                        success = True
                    else:
                        logger.error(f"Discord webhook failed: {resp.status}")
            except Exception as e:
                logger.error(f"Discord webhook error: {e}")
        
        return success
    
    # ===== Convenience methods for common alerts =====
    
    async def alert_drawdown_warning(self, current_drawdown: float, threshold: float = 10.0):
        """Send drawdown warning alert (>10%)"""
        await self.send_alert(Alert(
            alert_type=AlertType.DRAWDOWN_WARNING,
            level=AlertLevel.WARNING,
            title="Drawdown Warning",
            message=f"Portfolio drawdown has exceeded {threshold}% threshold.",
            data={
                "Current Drawdown": f"{current_drawdown:.2f}%",
                "Threshold": f"{threshold}%",
                "Action": "Leverage reduced automatically"
            }
        ))
    
    async def alert_drawdown_critical(self, current_drawdown: float, threshold: float = 15.0):
        """Send critical drawdown alert (>15%) - kill switch triggered"""
        await self.send_alert(Alert(
            alert_type=AlertType.DRAWDOWN_CRITICAL,
            level=AlertLevel.CRITICAL,
            title="CRITICAL: Kill Switch Triggered",
            message=f"Portfolio drawdown exceeded {threshold}%. Trading has been HALTED.",
            data={
                "Current Drawdown": f"{current_drawdown:.2f}%",
                "Max Allowed": f"{threshold}%",
                "Status": "KILL SWITCH ACTIVE",
                "Action Required": "Review positions manually"
            }
        ))
    
    async def alert_connection_lost(self, broker: str = "IBKR"):
        """Send connection lost alert"""
        await self.send_alert(Alert(
            alert_type=AlertType.CONNECTION_LOST,
            level=AlertLevel.CRITICAL,
            title="Broker Connection Lost",
            message=f"Lost connection to {broker}. Attempting to reconnect...",
            data={
                "Broker": broker,
                "Status": "DISCONNECTED"
            }
        ))
    
    async def alert_connection_restored(self, broker: str = "IBKR"):
        """Send connection restored alert"""
        await self.send_alert(Alert(
            alert_type=AlertType.CONNECTION_RESTORED,
            level=AlertLevel.INFO,
            title="Connection Restored",
            message=f"Successfully reconnected to {broker}.",
            data={
                "Broker": broker,
                "Status": "CONNECTED"
            }
        ))
    
    async def alert_data_anomaly(self, symbol: str, issue: str, details: Optional[Dict] = None):
        """Send data anomaly alert"""
        await self.send_alert(Alert(
            alert_type=AlertType.DATA_ANOMALY,
            level=AlertLevel.WARNING,
            title="Data Anomaly Detected",
            message=f"Anomaly detected in {symbol} data: {issue}",
            data=details or {"Symbol": symbol, "Issue": issue}
        ))
    
    async def alert_strategy_failure(self, strategy: str, error: str):
        """Send strategy failure alert"""
        await self.send_alert(Alert(
            alert_type=AlertType.STRATEGY_FAILURE,
            level=AlertLevel.CRITICAL,
            title="Strategy Failure",
            message=f"Strategy '{strategy}' encountered an error and has been disabled.",
            data={
                "Strategy": strategy,
                "Error": error,
                "Status": "DISABLED"
            }
        ))
    
    async def alert_trade_executed(self, symbol: str, side: str, qty: int, price: float, strategy: str = None):
        """Send trade execution alert (optional, for significant trades)"""
        await self.send_alert(Alert(
            alert_type=AlertType.TRADE_EXECUTED,
            level=AlertLevel.INFO,
            title="Trade Executed",
            message=f"{side} {qty} {symbol} @ ${price:.2f}",
            data={
                "Symbol": symbol,
                "Side": side,
                "Quantity": qty,
                "Price": f"${price:.2f}",
                "Strategy": strategy or "Manual"
            }
        ))
    
    def get_alert_history(self, limit: int = 50) -> List[Dict]:
        """Get recent alert history"""
        return [a.to_dict() for a in self._alert_history[-limit:]]
    
    def update_config(
        self,
        slack_url: Optional[str] = None,
        discord_url: Optional[str] = None,
        enabled: Optional[bool] = None
    ):
        """Update webhook configuration"""
        if slack_url is not None:
            self.config.slack_url = slack_url
        if discord_url is not None:
            self.config.discord_url = discord_url
        if enabled is not None:
            self.config.enabled = enabled
        
        logger.info(f"Webhook config updated: slack={bool(self.config.slack_url)}, discord={bool(self.config.discord_url)}, enabled={self.config.enabled}")


# Global alert manager instance
alert_manager = AlertManager()
