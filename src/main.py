"""
Free Weight Strategy - Main Entry Point
========================================

Advanced multi-indicator confluence trading bot for crypto perpetual futures.

Usage:
    python -m src.main              # Live trading
    python -m src.main --dry-run    # Dry run mode (no real orders)
    python -m src.main --config path/to/config.yaml
"""

import asyncio
import argparse
import signal
import sys
import logging
from typing import Optional

from src.config import Config
from src.utils.logger import setup_logging
from src.utils.telegram import TelegramAlerter
from src.bybit_ws.client import BybitWebSocket, OHLCV, Ticker
from src.strategy.engine import StrategyEngine
from src.trading.executor import TradeExecutor
from src.trading.position_manager import PositionManager

logger = logging.getLogger(__name__)


class TradingBot:
    """
    Main trading bot orchestrating all components.
    
    Flow:
    1. Connect to Bybit WebSocket for real-time data
    2. Update indicators on each new candle
    3. Evaluate strategy on candle close
    4. Execute trades via Mudrex API
    5. Send Telegram alerts
    6. Monitor positions
    """
    
    def __init__(self, config: Config):
        self.config = config
        self._running = False
        
        # Initialize components
        self.ws: Optional[BybitWebSocket] = None
        self.engine = StrategyEngine(config)
        self.executor = TradeExecutor(config)
        self.position_manager = PositionManager(config)
        
        # Initialize Telegram alerter
        self.telegram: Optional[TelegramAlerter] = None
        if config.telegram.is_valid():
            self.telegram = TelegramAlerter(
                bot_token=config.telegram.bot_token,
                chat_ids=config.telegram.chat_ids,
            )
            logger.info(f"Telegram alerts enabled for {len(config.telegram.chat_ids)} chats")
    
    async def start(self) -> None:
        """Start the trading bot."""
        logger.info("=" * 60)
        logger.info("Free Weight Strategy - Starting")
        logger.info("=" * 60)
        mode = 'DRY-RUN' if self.config.dry_run else 'LIVE TRADING'
        logger.info(f"Mode: {mode}")
        logger.info(f"Symbols: {len(self.config.symbols)} pairs")
        logger.info(f"Timeframe: {self.config.timeframe}m")
        logger.info(f"Margin %: {self.config.risk.margin_percent}%")
        leverage_range = f"{self.config.risk.min_leverage}-{self.config.risk.max_leverage}x"
        logger.info(f"Leverage: {leverage_range}")
        logger.info(f"Min Order Value: ${self.config.risk.min_order_value}")
        logger.info(f"Min confluence: {self.config.strategy.min_confluence_score}%")
        logger.info(f"Min indicators: {self.config.strategy.min_indicators_aligned}/5")
        logger.info(f"Telegram: {'Enabled ✅' if self.telegram else 'Disabled'}")
        logger.info("=" * 60)
        
        balance = None
        if not self.config.dry_run:
            # Show initial balance
            balance = self.executor.get_balance()
            if balance:
                logger.info(f"Futures Balance: ${balance:.2f}")
                margin_per_trade = balance * (self.config.risk.margin_percent / 100)
                logger.info(f"Margin per trade: ${margin_per_trade:.2f}")
            
            # Sync existing positions
            if self.executor._client:
                self.position_manager.sync_positions(self.executor._client)
                positions = self.position_manager.get_all_positions()
                if positions:
                    logger.info(f"Existing positions: {len(positions)}")
        
        # Send startup alert
        if self.telegram:
            await self.telegram.send_startup(
                mode=mode,
                symbols=self.config.symbols,
                margin_pct=self.config.risk.margin_percent,
                leverage_range=leverage_range,
                balance=balance,
            )
        
        # Initialize WebSocket
        self.ws = BybitWebSocket(
            symbols=self.config.symbols,
            timeframe=str(self.config.timeframe),
            ws_url=self.config.bybit.ws_url,
            ping_interval=self.config.bybit.ping_interval,
            reconnect_delay=self.config.bybit.reconnect_delay,
        )
        
        # Set up callbacks
        self.ws.on_kline = self._on_kline
        self.ws.on_ticker = self._on_ticker
        self.ws.on_connect = self._on_connect
        self.ws.on_disconnect = self._on_disconnect
        
        # Start WebSocket
        self._running = True
        try:
            await self.ws.run_forever()
        except asyncio.CancelledError:
            logger.info("Bot cancelled")
        finally:
            await self.stop()
    
    async def stop(self) -> None:
        """Stop the trading bot gracefully."""
        logger.info("Stopping trading bot...")
        self._running = False
        
        if self.ws:
            await self.ws.close()
        
        # Send shutdown alert
        if self.telegram:
            await self.telegram.send_shutdown()
            await self.telegram.close()
        
        self.executor.close()
        logger.info("Trading bot stopped")
    
    def _on_connect(self) -> None:
        """Handle WebSocket connection."""
        logger.info("WebSocket connected - Receiving market data")
    
    def _on_disconnect(self) -> None:
        """Handle WebSocket disconnection."""
        logger.warning("WebSocket disconnected - Will attempt reconnect")
    
    def _on_kline(self, symbol: str, kline: OHLCV) -> None:
        """Handle new kline data."""
        # Update strategy engine
        self.engine.update_kline(symbol, kline)
        
        # Only evaluate on confirmed (closed) candles
        if kline.confirm:
            # Use asyncio to run async signal evaluation
            asyncio.create_task(self._evaluate_signal_async(symbol))
    
    def _on_ticker(self, ticker: Ticker) -> None:
        """Handle ticker updates."""
        self.engine.update_ticker(ticker)
    
    async def _evaluate_signal_async(self, symbol: str) -> None:
        """Evaluate strategy and potentially execute trade (async for Telegram)."""
        # Check if can open new position
        if not self.position_manager.can_open_position(symbol):
            logger.debug(f"{symbol}: Max positions reached, skipping evaluation")
            return
        
        # Check if already have position in same direction
        existing_side = self.position_manager.get_position_side(symbol)
        
        # Get signal from strategy
        signal = self.engine.evaluate(symbol)
        
        if not signal.is_actionable:
            logger.debug(f"{symbol}: {signal.reason}")
            return
        
        # Skip if signal is same as existing position
        if existing_side and existing_side == signal.side:
            logger.debug(f"{symbol}: Already have {existing_side} position")
            return
        
        # Log signal
        logger.info(f"SIGNAL: {signal}")
        
        # Send Telegram signal alert
        if self.telegram:
            await self.telegram.send_signal(
                symbol=signal.symbol,
                side=signal.side,
                confluence_score=signal.confluence_score,
                entry_price=signal.entry_price,
                stoploss_price=signal.stoploss_price,
                takeprofit_price=signal.takeprofit_price,
            )
        
        # Log indicator values for debugging
        indicator_values = self.engine.get_indicator_values(symbol)
        logger.debug(f"Indicators: {indicator_values}")
        
        # Execute trade
        result = self.executor.execute(signal)
        
        if result.success:
            logger.info(
                f"✅ Trade executed: {result.side} {result.quantity} {result.symbol} | "
                f"Leverage: {result.leverage}x | Margin: ${result.margin_used:.2f} | "
                f"Order ID: {result.order_id}"
            )
            
            # Send Telegram trade alert
            if self.telegram:
                await self.telegram.send_trade_executed(
                    symbol=result.symbol,
                    side=result.side,
                    quantity=result.quantity,
                    leverage=result.leverage,
                    margin_used=result.margin_used,
                    position_value=result.position_value,
                    entry_price=result.entry_price,
                    stoploss_price=result.stoploss_price,
                    takeprofit_price=result.takeprofit_price,
                    order_id=result.order_id,
                )
            
            # Track position (for dry-run, use fake ID)
            if self.config.dry_run:
                self.position_manager.add_position(
                    position_id=result.order_id,
                    symbol=result.symbol,
                    side=result.side,
                    quantity=result.quantity,
                    entry_price=result.entry_price,
                    stoploss_price=result.stoploss_price,
                    takeprofit_price=result.takeprofit_price,
                    leverage=result.leverage,
                )
        else:
            logger.warning(f"⚠️ Trade skipped: {result.error}")
            
            # Send Telegram failure alert
            if self.telegram:
                await self.telegram.send_trade_failed(
                    symbol=signal.symbol,
                    side=signal.side,
                    error=result.error or "Unknown error",
                )


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Free Weight Strategy - Crypto Trading Bot"
    )
    parser.add_argument(
        "--config", "-c",
        default="config.yaml",
        help="Path to config file (default: config.yaml)"
    )
    parser.add_argument(
        "--dry-run", "-d",
        action="store_true",
        help="Run in dry-run mode (no real orders)"
    )
    parser.add_argument(
        "--log-level", "-l",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default=None,
        help="Override log level"
    )
    return parser.parse_args()


async def main_async(args: argparse.Namespace) -> None:
    """Async main entry point."""
    # Load configuration
    config = Config.load(args.config)
    
    # Apply CLI overrides
    if args.dry_run:
        config.dry_run = True
    if args.log_level:
        config.logging.level = args.log_level
    
    # Setup logging
    setup_logging(
        level=config.logging.level,
        log_file=config.logging.file,
        max_size_mb=config.logging.max_size,
        backup_count=config.logging.backup_count,
    )
    
    # Fetch all symbols if not specified
    if not config.symbols:
        from src.utils.symbols import fetch_all_symbols
        logger.info("Fetching available symbols...")
        config.symbols = await fetch_all_symbols(config.mudrex_api_secret)
        logger.info(f"Loaded {len(config.symbols)} symbols")
    
    # Validate configuration
    if not config.validate():
        logger.error("Configuration validation failed")
        sys.exit(1)
    
    # Create and run bot
    bot = TradingBot(config)
    
    # Handle shutdown signals
    loop = asyncio.get_event_loop()
    
    def shutdown_handler():
        logger.info("Shutdown signal received")
        asyncio.create_task(bot.stop())
    
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, shutdown_handler)
    
    try:
        await bot.start()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    finally:
        await bot.stop()


def main() -> None:
    """Main entry point."""
    args = parse_args()
    
    try:
        asyncio.run(main_async(args))
    except KeyboardInterrupt:
        print("\nShutdown complete")


if __name__ == "__main__":
    main()
