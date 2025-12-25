"""
Pydantic Models for Alerts API
"""
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from datetime import datetime


class WebhookConfigRequest(BaseModel):
    """Request to configure webhooks"""
    slack_url: Optional[str] = Field(None, description="Slack webhook URL")
    discord_url: Optional[str] = Field(None, description="Discord webhook URL")
    enabled: Optional[bool] = Field(None, description="Enable/disable alerts")


class WebhookConfigResponse(BaseModel):
    """Webhook configuration response"""
    slack_configured: bool
    discord_configured: bool
    enabled: bool
    rate_limit: int
    enabled_alerts: List[str]


class AlertResponse(BaseModel):
    """Single alert response"""
    alert_type: str
    level: str
    title: str
    message: str
    timestamp: str
    data: Optional[Dict] = None


class AlertHistoryResponse(BaseModel):
    """Alert history response"""
    alerts: List[AlertResponse]
    total: int


class TestAlertRequest(BaseModel):
    """Request to send test alert"""
    alert_type: str = Field(default="test", description="Type of test alert to send")
