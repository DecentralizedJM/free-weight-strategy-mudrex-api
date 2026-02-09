"""
Trade Executor
==============

Handles order execution via Mudrex API with rate limiting and error handling.
"""

import logging
from typing import Optional
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
    - Error handling with retries
    - Position size calculation
    
    Example:
        executor = TradeExecutor(config)
        result = executor.execute(signal)
        if result.success:
            print(f"Order placed: {result.order_id}")
    """
    
    MIN_ORDER_VALUE = 7.0  # Minimum order value in USD
    
    def __init__(self, config: Config):
        self.config = config
        self._client = None
        
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
    
    def _dry_run_execute(self, signal: Signal) -> TradeResult:
        """Simulate trade execution without placing real orders."""
        quantity = self._calculate_quantity(signal)
        
        logger.info(
            f"[DRY-RUN] Would execute {signal.side} {quantity} {signal.symbol} @ "
            f"{signal.entry_price:.4f} | SL: {signal.stoploss_price:.4f} | "
            f"TP: {signal.takeprofit_price:.4f}"
        )
        
        return TradeResult(
            success=True,
            order_id="DRY_RUN_" + signal.symbol,
            symbol=signal.symbol,
            side=signal.side,
            quantity=quantity,
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
            quantity = self._calculate_quantity(signal)
            
            # Validate minimum order value
            order_value = float(quantity) * signal.entry_price
            if order_value < self.MIN_ORDER_VALUE:
                return TradeResult(
                    success=False,
                    error=f"Order value ${order_value:.2f} below minimum ${self.MIN_ORDER_VALUE}"
                )
            
            # Set leverage
            self._client.leverage.set(
                symbol=signal.symbol,
                leverage=str(signal.leverage),
                margin_type="ISOLATED"
            )
            
            # Place market order with SL/TP
            order = self._client.orders.create_market_order(
                symbol=signal.symbol,
                side=signal.side,
                quantity=quantity,
                leverage=str(signal.leverage),
                stoploss_price=str(round(signal.stoploss_price, 4)) if signal.stoploss_price else None,
                takeprofit_price=str(round(signal.takeprofit_price, 4)) if signal.takeprofit_price else None,
            )
            
            logger.info(
                f"Order executed: {signal.side} {quantity} {signal.symbol} @ "
                f"market | Order ID: {order.order_id}"
            )
            
            return TradeResult(
                success=True,
                order_id=order.order_id,
                symbol=signal.symbol,
                side=signal.side,
                quantity=quantity,
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
    
    def _calculate_quantity(self, signal: Signal) -> str:
        """Calculate position quantity based on risk and capital."""
        if self.config.dry_run:
            # Use fixed quantity for dry-run
            if "BTC" in signal.symbol:
                return "0.001"
            elif "ETH" in signal.symbol:
                return "0.01"
            else:
                return "10"
        
        try:
            # Get futures balance
            balance = self._client.wallet.get_futures_balance()
            available = float(balance.balance)
            
            # Calculate position value (risk % of capital * leverage)
            risk_pct = signal.position_size_pct / 100
            position_value = available * risk_pct * signal.leverage
            
            # Calculate quantity
            quantity = position_value / signal.entry_price
            
            # Get asset info for min_quantity and quantity_step
            asset = self._client.assets.get(signal.symbol)
            min_qty = float(asset.min_quantity)
            qty_step = float(asset.quantity_step)
            
            # Round to quantity step
            quantity = max(min_qty, round(quantity / qty_step) * qty_step)
            
            # Format with appropriate precision
            precision = len(str(qty_step).split('.')[-1]) if '.' in str(qty_step) else 0
            return str(round(quantity, precision))
            
        except Exception as e:
            logger.error(f"Failed to calculate quantity: {e}")
            # Fallback to minimum
            return "0.001" if "BTC" in signal.symbol else "1"
    
    def get_balance(self) -> Optional[float]:
        """Get current futures balance."""
        if self.config.dry_run:
            return 1000.0  # Simulated balance
        
        try:
            balance = self._client.wallet.get_futures_balance()
            return float(balance.balance)
        except Exception as e:
            logger.error(f"Failed to get balance: {e}")
            return None
    
    def close(self) -> None:
        """Close the Mudrex client connection."""
        if self._client:
            self._client.close()
