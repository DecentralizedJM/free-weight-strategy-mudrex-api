"""
Trade Executor
==============

Handles order execution via Mudrex API with rate limiting and error handling.
Includes auto-leverage scaling to meet minimum order value.
"""

import logging
import math
from typing import Optional, Tuple
from dataclasses import dataclass

from src.config import Config
from src.strategy.signals import Signal

logger = logging.getLogger(__name__)


@dataclass
class TradeResult:
    """Result of a trade execution."""
    success: bool
    order_id: Optional[str] = None
    symbol: str = ""
    side: str = ""
    quantity: str = ""
    leverage: int = 1
    margin_used: float = 0.0
    position_value: float = 0.0
    entry_price: Optional[float] = None
    stoploss_price: Optional[float] = None
    takeprofit_price: Optional[float] = None
    error: Optional[str] = None


class TradeExecutor:
    """
    Executes trades via Mudrex API.
    
    Features:
    - Dry-run mode for testing
    - Rate limit awareness
    - Auto-leverage scaling to meet min order value
    - Margin percentage based position sizing
    
    Example:
        executor = TradeExecutor(config)
        result = executor.execute(signal)
        if result.success:
            print(f"Order placed: {result.order_id}")
    """
    
    def __init__(self, config: Config):
        self.config = config
        self._client = None
        self._balance_cache: Optional[float] = None
        
        if not config.dry_run:
            self._init_client()
    
    def _init_client(self) -> None:
        """Initialize Mudrex client."""
        try:
            from mudrex import MudrexClient
            self._client = MudrexClient(api_secret=self.config.mudrex_api_secret)
            logger.info("Mudrex client initialized")
        except ImportError:
            logger.error("Mudrex SDK not installed. Install with: pip install git+https://github.com/DecentralizedJM/mudrex-api-trading-python-sdk.git")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize Mudrex client: {e}")
            raise
    
    def execute(self, signal: Signal) -> TradeResult:
        """
        Execute a trade based on signal.
        
        Args:
            signal: Trading signal with entry, SL, TP
            
        Returns:
            TradeResult with execution details
        """
        if not signal.is_actionable:
            return TradeResult(
                success=False,
                error="Signal is not actionable"
            )
        
        # Dry-run mode
        if self.config.dry_run:
            return self._dry_run_execute(signal)
        
        # Live execution
        return self._live_execute(signal)
    
    def _calculate_position(self, signal: Signal, balance: float) -> Tuple[str, int, float, float]:
        """
        Calculate position size with auto-leverage scaling.
        
        Returns:
            Tuple of (quantity, leverage, margin_used, position_value)
        """
        risk_cfg = self.config.risk
        
        # Calculate margin amount (% of balance)
        margin_amount = balance * (risk_cfg.margin_percent / 100)
        
        # Start with default leverage
        leverage = risk_cfg.default_leverage
        
        # Calculate position value
        position_value = margin_amount * leverage
        
        # Check if we meet minimum order value
        min_order = risk_cfg.min_order_value
        
        if position_value < min_order:
            # Scale up leverage to meet minimum
            required_leverage = math.ceil(min_order / margin_amount)
            
            if required_leverage <= risk_cfg.max_leverage:
                leverage = required_leverage
                position_value = margin_amount * leverage
                logger.info(
                    f"Auto-scaled leverage to {leverage}x to meet min order ${min_order}"
                )
            else:
                # Cannot meet minimum even with max leverage
                leverage = risk_cfg.max_leverage
                position_value = margin_amount * leverage
                logger.warning(
                    f"Cannot meet min order ${min_order} even with max leverage "
                    f"{risk_cfg.max_leverage}x. Position value: ${position_value:.2f}"
                )
        
        # Calculate quantity
        if not signal.entry_price or signal.entry_price <= 0:
            logger.warning(f"Invalid entry price {signal.entry_price} for {signal.symbol}, skipping")
            return 0, leverage, margin_amount, position_value
        quantity = position_value / signal.entry_price
        
        return quantity, leverage, margin_amount, position_value
    
    def _format_quantity(self, quantity: float, symbol: str) -> str:
        """Format quantity with appropriate precision."""
        if self._client:
            try:
                asset = self._client.assets.get(symbol)
                min_qty = float(asset.min_quantity)
                qty_step = float(asset.quantity_step)
                
                # Round to quantity step
                quantity = max(min_qty, round(quantity / qty_step) * qty_step)
                
                # Format with appropriate precision
                precision = len(str(qty_step).split('.')[-1]) if '.' in str(qty_step) else 0
                return str(round(quantity, precision))
            except Exception as e:
                logger.warning(f"Could not get asset info: {e}")
        
        # Fallback formatting
        if "BTC" in symbol:
            return f"{quantity:.5f}"
        elif "ETH" in symbol:
            return f"{quantity:.4f}"
        else:
            return f"{quantity:.2f}"
    
    def _dry_run_execute(self, signal: Signal) -> TradeResult:
        """Simulate trade execution without placing real orders."""
        # Use simulated balance
        balance = 1000.0
        
        quantity, leverage, margin_used, position_value = self._calculate_position(
            signal, balance
        )
        
        quantity_str = self._format_quantity(quantity, signal.symbol)
        
        logger.info(
            f"[DRY-RUN] {signal.side} {quantity_str} {signal.symbol} | "
            f"Leverage: {leverage}x | Margin: ${margin_used:.2f} | "
            f"Position: ${position_value:.2f} | "
            f"Entry: {signal.entry_price:.4f} | SL: {signal.stoploss_price:.4f} | "
            f"TP: {signal.takeprofit_price:.4f}"
        )
        
        return TradeResult(
            success=True,
            order_id="DRY_RUN_" + signal.symbol,
            symbol=signal.symbol,
            side=signal.side,
            quantity=quantity_str,
            leverage=leverage,
            margin_used=margin_used,
            position_value=position_value,
            entry_price=signal.entry_price,
            stoploss_price=signal.stoploss_price,
            takeprofit_price=signal.takeprofit_price,
        )
    
    def _live_execute(self, signal: Signal) -> TradeResult:
        """Execute live trade via Mudrex API."""
        if not self._client:
            return TradeResult(
                success=False,
                error="Mudrex client not initialized"
            )
        
        try:
            # Get current balance
            balance = self.get_balance()
            if balance is None or balance <= 0:
                return TradeResult(
                    success=False,
                    error="Could not get balance or balance is zero"
                )
            
            # Calculate position with auto-leverage
            quantity, leverage, margin_used, position_value = self._calculate_position(
                signal, balance
            )
            
            # Guard: skip if quantity is zero (invalid entry price)
            if quantity <= 0:
                return TradeResult(
                    success=False,
                    symbol=signal.symbol,
                    error=f"Invalid quantity for {signal.symbol} (entry_price={signal.entry_price})"
                )
            
            # Final validation
            min_order = self.config.risk.min_order_value
            if position_value < min_order:
                return TradeResult(
                    success=False,
                    error=f"Position value ${position_value:.2f} below minimum ${min_order}"
                )
            
            # Format quantity
            quantity_str = self._format_quantity(quantity, signal.symbol)
            
            # Set leverage
            self._client.leverage.set(
                symbol=signal.symbol,
                leverage=str(leverage),
                margin_type="ISOLATED"
            )
            
            # Place market order with SL/TP
            order = self._client.orders.create_market_order(
                symbol=signal.symbol,
                side=signal.side,
                quantity=quantity_str,
                leverage=str(leverage),
                stoploss_price=str(round(signal.stoploss_price, 4)) if signal.stoploss_price else None,
                takeprofit_price=str(round(signal.takeprofit_price, 4)) if signal.takeprofit_price else None,
            )
            
            logger.info(
                f"✅ Order executed: {signal.side} {quantity_str} {signal.symbol} | "
                f"Leverage: {leverage}x | Margin: ${margin_used:.2f} | "
                f"Position: ${position_value:.2f} | Order ID: {order.order_id}"
            )
            
            return TradeResult(
                success=True,
                order_id=order.order_id,
                symbol=signal.symbol,
                side=signal.side,
                quantity=quantity_str,
                leverage=leverage,
                margin_used=margin_used,
                position_value=position_value,
                entry_price=signal.entry_price,
                stoploss_price=signal.stoploss_price,
                takeprofit_price=signal.takeprofit_price,
            )
            
        except Exception as e:
            logger.error(f"Trade execution failed: {e}")
            return TradeResult(
                success=False,
                symbol=signal.symbol,
                side=signal.side,
                error=str(e)
            )
    
    def get_balance(self) -> Optional[float]:
        """Get current futures balance."""
        if self.config.dry_run:
            return 1000.0  # Simulated balance
        
        try:
            balance = self._client.wallet.get_futures_balance()
            self._balance_cache = float(balance.balance)
            return self._balance_cache
        except Exception as e:
            logger.error(f"Failed to get balance: {e}")
            return self._balance_cache  # Return cached if available
    
    def close(self) -> None:
        """Close the Mudrex client connection."""
        if self._client:
            self._client.close()
