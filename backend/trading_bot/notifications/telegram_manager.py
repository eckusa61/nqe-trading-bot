"""
Telegram Manager - Multi-Channel Notification System

Channels:
- Haber: News, social media updates
- Sinyal: Trading signals (BUY/SELL)
- Analiz: Daily/weekly analysis reports
- Optimizasyon: Bot status, errors, AI decisions
"""
import os
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum
import aiohttp

logger = logging.getLogger(__name__)


class TelegramChannel(Enum):
    HABER = "haber"
    SINYAL = "sinyal"
    ANALIZ = "analiz"
    OPTIMIZASYON = "optimizasyon"


@dataclass
class TelegramConfig:
    token: str
    chat_id: str
    name: str


class TelegramManager:
    """
    Manages multiple Telegram bot channels for different notification types
    """
    
    def __init__(self):
        self.channels: Dict[TelegramChannel, TelegramConfig] = {}
        self._load_config()
        self._session: Optional[aiohttp.ClientSession] = None
        logger.info("TelegramManager initialized")
    
    def _load_config(self):
        """Load Telegram configuration from environment variables"""
        
        # Haber Channel
        haber_token = os.environ.get('TELEGRAM_HABER_TOKEN')
        haber_chat = os.environ.get('TELEGRAM_HABER_CHAT_ID')
        if haber_token and haber_chat:
            self.channels[TelegramChannel.HABER] = TelegramConfig(
                token=haber_token, chat_id=haber_chat, name="NQE Haber"
            )
        
        # Sinyal Channel
        sinyal_token = os.environ.get('TELEGRAM_SINYAL_TOKEN')
        sinyal_chat = os.environ.get('TELEGRAM_SINYAL_CHAT_ID')
        if sinyal_token and sinyal_chat:
            self.channels[TelegramChannel.SINYAL] = TelegramConfig(
                token=sinyal_token, chat_id=sinyal_chat, name="NQE Sinyal"
            )
        
        # Analiz Channel
        analiz_token = os.environ.get('TELEGRAM_ANALIZ_TOKEN')
        analiz_chat = os.environ.get('TELEGRAM_ANALIZ_CHAT_ID')
        if analiz_token and analiz_chat:
            self.channels[TelegramChannel.ANALIZ] = TelegramConfig(
                token=analiz_token, chat_id=analiz_chat, name="NQE Analiz"
            )
        
        # Optimizasyon Channel
        opt_token = os.environ.get('TELEGRAM_OPTIMIZASYON_TOKEN')
        opt_chat = os.environ.get('TELEGRAM_OPTIMIZASYON_CHAT_ID')
        if opt_token and opt_chat:
            self.channels[TelegramChannel.OPTIMIZASYON] = TelegramConfig(
                token=opt_token, chat_id=opt_chat, name="NQE Optimizasyon"
            )
        
        logger.info(f"Loaded {len(self.channels)} Telegram channels")
    
    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session
    
    async def send_message(
        self,
        channel: TelegramChannel,
        message: str,
        parse_mode: str = "HTML"
    ) -> bool:
        """
        Send message to a specific Telegram channel
        
        Args:
            channel: Which channel to send to
            message: Message text (supports HTML formatting)
            parse_mode: 'HTML' or 'Markdown'
        """
        if channel not in self.channels:
            logger.warning(f"Channel {channel.value} not configured")
            return False
        
        config = self.channels[channel]
        url = f"https://api.telegram.org/bot{config.token}/sendMessage"
        
        payload = {
            "chat_id": config.chat_id,
            "text": message,
            "parse_mode": parse_mode
        }
        
        try:
            session = await self._get_session()
            async with session.post(url, json=payload) as response:
                if response.status == 200:
                    logger.info(f"Message sent to {config.name}")
                    return True
                else:
                    error = await response.text()
                    logger.error(f"Telegram error: {error}")
                    return False
        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")
            return False
    
    # ===== HABER CHANNEL =====
    
    async def send_news(self, title: str, source: str, summary: str, sentiment: str = "neutral"):
        """Send news update to Haber channel"""
        emoji = {"bullish": "🟢", "bearish": "🔴", "neutral": "⚪"}.get(sentiment, "⚪")
        
        message = f"""
{emoji} <b>HABER</b> | {source}

<b>{title}</b>

{summary}

<i>{datetime.now().strftime('%H:%M:%S')}</i>
"""
        return await self.send_message(TelegramChannel.HABER, message)
    
    async def send_social_update(self, platform: str, content: str, sentiment: float):
        """Send social media update"""
        emoji = "🐦" if platform == "twitter" else "🤖" if platform == "reddit" else "📱"
        sent_emoji = "🟢" if sentiment > 0.3 else "🔴" if sentiment < -0.3 else "⚪"
        
        message = f"""
{emoji} <b>{platform.upper()}</b> {sent_emoji}

{content[:500]}...

Sentiment: <b>{sentiment:.2f}</b>
"""
        return await self.send_message(TelegramChannel.HABER, message)
    
    # ===== SINYAL CHANNEL =====
    
    async def send_signal(
        self,
        symbol: str,
        action: str,  # BUY, SELL, HOLD
        price: float,
        target: Optional[float] = None,
        stop_loss: Optional[float] = None,
        confidence: float = 0.0,
        reason: str = ""
    ):
        """Send trading signal to Sinyal channel"""
        emoji = {"BUY": "🟢", "SELL": "🔴", "HOLD": "🟡"}.get(action, "⚪")
        
        message = f"""
{emoji} <b>{action} {symbol}</b>

💰 Fiyat: <code>${price:.2f}</code>
"""
        if target:
            message += f"🎯 Hedef: <code>${target:.2f}</code>\n"
        if stop_loss:
            message += f"🛑 Stop Loss: <code>${stop_loss:.2f}</code>\n"
        
        message += f"""
📊 Güven: <b>{confidence*100:.0f}%</b>

📝 {reason}

<i>{datetime.now().strftime('%H:%M:%S')}</i>
"""
        return await self.send_message(TelegramChannel.SINYAL, message)
    
    async def send_position_update(self, symbol: str, action: str, qty: int, price: float, pnl: float):
        """Send position update (open/close)"""
        emoji = "📈" if pnl >= 0 else "📉"
        pnl_emoji = "🟢" if pnl >= 0 else "🔴"
        
        message = f"""
{emoji} <b>POZİSYON {action}</b>

{symbol}: {qty} adet @ ${price:.2f}
{pnl_emoji} P&L: <b>${pnl:+.2f}</b>

<i>{datetime.now().strftime('%H:%M:%S')}</i>
"""
        return await self.send_message(TelegramChannel.SINYAL, message)
    
    # ===== ANALIZ CHANNEL =====
    
    async def send_daily_report(self, report: Dict[str, Any]):
        """Send daily analysis report"""
        pnl = report.get('daily_pnl', 0)
        pnl_emoji = "🟢" if pnl >= 0 else "🔴"
        
        message = f"""
📊 <b>GÜNLÜK RAPOR</b> | {datetime.now().strftime('%d.%m.%Y')}

{pnl_emoji} Günlük P&L: <b>${pnl:+.2f}</b>
📈 Toplam İşlem: {report.get('total_trades', 0)}
✅ Kazanan: {report.get('winning_trades', 0)}
❌ Kaybeden: {report.get('losing_trades', 0)}
📊 Win Rate: {report.get('win_rate', 0)*100:.1f}%

<b>Rejim:</b> {report.get('regime', 'N/A')}
<b>Aktif Strateji:</b> {report.get('active_strategy', 'N/A')}

<b>Portföy Değeri:</b> ${report.get('portfolio_value', 0):,.2f}
"""
        return await self.send_message(TelegramChannel.ANALIZ, message)
    
    async def send_regime_change(self, old_regime: str, new_regime: str, confidence: float):
        """Send regime change notification"""
        emoji = {"bull": "🐂", "bear": "🐻", "sideways": "➡️", "crisis": "🚨"}
        
        message = f"""
🔄 <b>REJİM DEĞİŞİKLİĞİ</b>

{emoji.get(old_regime, '⚪')} {old_regime.upper()} → {emoji.get(new_regime, '⚪')} <b>{new_regime.upper()}</b>

📊 Güven: {confidence*100:.0f}%

<i>Strateji ağırlıkları otomatik olarak ayarlandı.</i>
"""
        return await self.send_message(TelegramChannel.ANALIZ, message)
    
    # ===== OPTIMIZASYON CHANNEL =====
    
    async def send_bot_status(self, status: str, details: str = ""):
        """Send bot status update"""
        emoji = {"running": "🟢", "stopped": "🔴", "warning": "🟡", "error": "❌"}
        
        message = f"""
{emoji.get(status, '⚪')} <b>BOT DURUMU: {status.upper()}</b>

{details}

<i>{datetime.now().strftime('%H:%M:%S')}</i>
"""
        return await self.send_message(TelegramChannel.OPTIMIZASYON, message)
    
    async def send_error(self, error_type: str, error_message: str, severity: str = "medium"):
        """Send error notification"""
        emoji = {"low": "⚠️", "medium": "🔶", "high": "🔴", "critical": "🚨"}
        
        message = f"""
{emoji.get(severity, '⚠️')} <b>HATA - {severity.upper()}</b>

<b>Tip:</b> {error_type}
<b>Mesaj:</b> {error_message}

<i>{datetime.now().strftime('%H:%M:%S')}</i>
"""
        return await self.send_message(TelegramChannel.OPTIMIZASYON, message)
    
    async def send_ai_decision(self, decision: str, reasoning: str, action_taken: str):
        """Send AI Supervisor decision"""
        message = f"""
🧠 <b>AI KARAR</b>

<b>Karar:</b> {decision}

<b>Gerekçe:</b>
{reasoning}

<b>Yapılan İşlem:</b>
{action_taken}

<i>{datetime.now().strftime('%H:%M:%S')}</i>
"""
        return await self.send_message(TelegramChannel.OPTIMIZASYON, message)
    
    async def send_strategy_update(self, old_strategy: str, new_strategy: str, reason: str):
        """Send strategy change notification"""
        message = f"""
⚙️ <b>STRATEJİ DEĞİŞİKLİĞİ</b>

{old_strategy} → <b>{new_strategy}</b>

<b>Sebep:</b> {reason}

<i>{datetime.now().strftime('%H:%M:%S')}</i>
"""
        return await self.send_message(TelegramChannel.OPTIMIZASYON, message)
    
    # ===== UTILITY =====
    
    async def test_all_channels(self):
        """Test all configured channels"""
        results = {}
        
        for channel in TelegramChannel:
            if channel in self.channels:
                success = await self.send_message(
                    channel,
                    f"✅ <b>Test Mesajı</b>\n\n{self.channels[channel].name} kanalı aktif!\n\n<i>{datetime.now().strftime('%H:%M:%S')}</i>"
                )
                results[channel.value] = success
            else:
                results[channel.value] = False
        
        return results
    
    def get_status(self) -> Dict[str, Any]:
        """Get Telegram manager status"""
        return {
            "configured_channels": [c.value for c in self.channels.keys()],
            "channel_count": len(self.channels),
            "channels": {
                channel.value: {
                    "name": config.name,
                    "configured": True
                }
                for channel, config in self.channels.items()
            }
        }
    
    async def close(self):
        """Close the HTTP session"""
        if self._session and not self._session.closed:
            await self._session.close()


# Singleton instance
telegram_manager = TelegramManager()
