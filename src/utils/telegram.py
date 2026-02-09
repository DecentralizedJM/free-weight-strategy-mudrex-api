"""
Telegram Alerter
================

Sends trade signals and execution alerts to Telegram.
"""

import logging
import asyncio
from typing import Optional, List
from dataclasses import dataclass, field
import aiohttp

logger = logging.getLogger(__name__)


@dataclass
class TelegramConfig:
    """Telegram configuration."""
    bot_token: str = ""
    chat_ids: List[str] = field(default_factory=list)
    enabled: bool = False
    
    def is_valid(self) -> bool:
        return bool(self.bot_token and self.chat_ids)


class TelegramAlerter:
    """
    Sends alerts to Telegram.
    
    Usage:
        alerter = TelegramAlerter(bot_token, chat_id)
        await alerter.send_signal("BTCUSDT", "LONG", 80, 45000.0)
        await alerter.send_trade_executed(result)
    """
    
    API_URL = "https://api.telegram.org/bot{token}/sendMessage"
    
    def __init__(self, bot_token: str, chat_ids: List[str]):
        self.bot_token = bot_token
        self.chat_ids = chat_ids
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session
    
    async def send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        """Send a message to all configured Telegram chats."""
        if not self.bot_token or not self.chat_ids:
            logger.debug("Telegram not configured, skipping alert")
            return False
        
        try:
            session = await self._get_session()
            url = self.API_URL.format(token=self.bot_token)
            
            success_count = 0
            
            for chat_id in self.chat_ids:
                payload = {
                    "chat_id": chat_id,
                    "text": text,
                    "parse_mode": parse_mode,
                    "disable_web_page_preview": True,
                }
                
                try:
                    async with session.post(url, json=payload) as resp:
                        if resp.status == 200:
                            success_count += 1
                        else:
                            error = await resp.text()
                            logger.error(f"Telegram API error for chat {chat_id}: {resp.status} - {error}")
                except Exception as e:
                    logger.error(f"Failed to send to chat {chat_id}: {e}")
            
            if success_count > 0:
                logger.debug(f"Telegram alert sent to {success_count}/{len(self.chat_ids)} chats")
                return True
            return False
                    
        except Exception as e:
            logger.error(f"Failed to send Telegram alert: {e}")
            return False
    
    async def send_signal(
        self,
        symbol: str,
        side: str,
        confluence_score: int,
        entry_price: float,
        stoploss_price: float,
        takeprofit_price: float,
        reason: str = "",
    ) -> bool:
        """Send a trade signal alert."""
        emoji = "🟢" if side == "LONG" else "🔴"
        
        text = f"""
{emoji} <b>SIGNAL: {side} {symbol}</b>

📊 <b>Confluence:</b> {confluence_score}%
💰 <b>Entry:</b> ${entry_price:,.4f}
🛑 <b>Stop-Loss:</b> ${stoploss_price:,.4f}
🎯 <b>Take-Profit:</b> ${takeprofit_price:,.4f}

{f"📝 {reason}" if reason else ""}
""".strip()
        
        return await self.send_message(text)
    
    async def send_trade_executed(
        self,
        symbol: str,
        side: str,
        quantity: str,
        leverage: int,
        margin_used: float,
        position_value: float,
        entry_price: float,
        stoploss_price: float,
        takeprofit_price: float,
        order_id: str,
    ) -> bool:
        """Send a trade execution alert."""
        emoji = "✅"
        side_emoji = "🟢" if side == "LONG" else "🔴"
        
        text = f"""
{emoji} <b>TRADE EXECUTED</b>

{side_emoji} <b>{side} {symbol}</b>
📦 <b>Quantity:</b> {quantity}
⚡ <b>Leverage:</b> {leverage}x
💵 <b>Margin:</b> ${margin_used:.2f}
📊 <b>Position:</b> ${position_value:.2f}

💰 <b>Entry:</b> ${entry_price:,.4f}
🛑 <b>SL:</b> ${stoploss_price:,.4f}
🎯 <b>TP:</b> ${takeprofit_price:,.4f}

🆔 <code>{order_id}</code>
""".strip()
        
        return await self.send_message(text)
    
    async def send_trade_failed(
        self,
        symbol: str,
        side: str,
        error: str,
    ) -> bool:
        """Send a trade failure alert."""
        text = f"""
❌ <b>TRADE FAILED</b>

📉 <b>{side} {symbol}</b>
⚠️ <b>Error:</b> {error}
""".strip()
        
        return await self.send_message(text)
    
    async def send_startup(
        self,
        mode: str,
        symbols: list,
        margin_pct: float,
        leverage_range: str,
        balance: Optional[float] = None,
    ) -> bool:
        """Send bot startup notification."""
        # Show count instead of listing all symbols to avoid message length limit
        symbols_count = len(symbols)
        
        text = f"""
🚀 <b>Free Weight Strategy Started</b>

🔧 <b>Mode:</b> {mode}
📊 <b>Symbols:</b> {symbols_count} pairs
💰 <b>Margin:</b> {margin_pct}%
⚡ <b>Leverage:</b> {leverage_range}
{f"💵 <b>Balance:</b> ${balance:.2f}" if balance else ""}
""".strip()
        
        return await self.send_message(text)
    
    async def send_shutdown(self) -> bool:
        """Send bot shutdown notification."""
        text = "⏹️ <b>Free Weight Strategy Stopped</b>"
        return await self.send_message(text)
    
    async def close(self) -> None:
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
