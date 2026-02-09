"""
Position Manager
================

Manages open positions with risk controls and tracking.
"""

import logging
import time
from typing import Dict, List, Optional
from dataclasses import dataclass, field

from src.config import Config

logger = logging.getLogger(__name__)


@dataclass
class TrackedPosition:
    """A tracked open position."""
    position_id: str
    symbol: str
    side: str  # "LONG" or "SHORT"
    quantity: str
    entry_price: float
    stoploss_price: Optional[float] = None
    takeprofit_price: Optional[float] = None
    leverage: int = 1
    opened_at: float = field(default_factory=time.time)
    last_updated: float = field(default_factory=time.time)
    unrealized_pnl: float = 0.0


class PositionManager:
    """
    Manages open positions and enforces risk limits.
    
    Features:
    - Track open positions per symbol
    - Enforce max positions per symbol
    - Monitor PnL and update SL/TP
    - Sync with exchange positions
    
    Example:
        pm = PositionManager(config)
        
        # Check if can open new position
        if pm.can_open_position("BTCUSDT"):
            # Execute trade...
            pm.add_position(position)
        
        # Update from exchange
        pm.sync_positions(client)
    """
    
    def __init__(self, config: Config):
        self.config = config
        self._positions: Dict[str, TrackedPosition] = {}  # position_id -> position
        self._symbol_positions: Dict[str, List[str]] = {}  # symbol -> [position_ids]
    
    def add_position(
        self,
        position_id: str,
        symbol: str,
        side: str,
        quantity: str,
        entry_price: float,
        stoploss_price: Optional[float] = None,
        takeprofit_price: Optional[float] = None,
        leverage: int = 1,
    ) -> None:
        """Add a new position to track."""
        position = TrackedPosition(
            position_id=position_id,
            symbol=symbol,
            side=side,
            quantity=quantity,
            entry_price=entry_price,
            stoploss_price=stoploss_price,
            takeprofit_price=takeprofit_price,
            leverage=leverage,
        )
        
        self._positions[position_id] = position
        
        if symbol not in self._symbol_positions:
            self._symbol_positions[symbol] = []
        self._symbol_positions[symbol].append(position_id)
        
        logger.info(f"Tracking position: {position_id} ({side} {quantity} {symbol})")
    
    def remove_position(self, position_id: str) -> None:
        """Remove a closed position."""
        if position_id not in self._positions:
            return
        
        position = self._positions[position_id]
        symbol = position.symbol
        
        del self._positions[position_id]
        
        if symbol in self._symbol_positions:
            self._symbol_positions[symbol] = [
                pid for pid in self._symbol_positions[symbol] 
                if pid != position_id
            ]
        
        logger.info(f"Removed position: {position_id}")
    
    def can_open_position(self, symbol: str) -> bool:
        """Check if a new position can be opened for symbol."""
        current_count = len(self._symbol_positions.get(symbol, []))
        max_allowed = self.config.strategy.max_positions_per_symbol
        return current_count < max_allowed
    
    def get_position(self, position_id: str) -> Optional[TrackedPosition]:
        """Get a tracked position by ID."""
        return self._positions.get(position_id)
    
    def get_positions_for_symbol(self, symbol: str) -> List[TrackedPosition]:
        """Get all positions for a symbol."""
        position_ids = self._symbol_positions.get(symbol, [])
        return [self._positions[pid] for pid in position_ids if pid in self._positions]
    
    def get_all_positions(self) -> List[TrackedPosition]:
        """Get all tracked positions."""
        return list(self._positions.values())
    
    def has_open_position(self, symbol: str) -> bool:
        """Check if there's any open position for symbol."""
        return len(self._symbol_positions.get(symbol, [])) > 0
    
    def get_position_side(self, symbol: str) -> Optional[str]:
        """Get the side of existing position (if any)."""
        positions = self.get_positions_for_symbol(symbol)
        if positions:
            return positions[0].side
        return None
    
    def update_pnl(self, position_id: str, unrealized_pnl: float) -> None:
        """Update unrealized PnL for a position."""
        if position_id in self._positions:
            self._positions[position_id].unrealized_pnl = unrealized_pnl
            self._positions[position_id].last_updated = time.time()
    
    def sync_positions(self, client) -> None:
        """Sync positions with exchange."""
        if client is None:
            return
        
        try:
            exchange_positions = client.positions.list_open()
            
            # Track exchange position IDs
            exchange_ids = set()
            
            for pos in exchange_positions:
                exchange_ids.add(pos.position_id)
                
                if pos.position_id not in self._positions:
                    # New position found on exchange
                    self.add_position(
                        position_id=pos.position_id,
                        symbol=pos.symbol,
                        side=pos.side.value if hasattr(pos.side, 'value') else pos.side,
                        quantity=pos.quantity,
                        entry_price=float(pos.entry_price),
                        stoploss_price=float(pos.stoploss_price) if pos.stoploss_price else None,
                        takeprofit_price=float(pos.takeprofit_price) if pos.takeprofit_price else None,
                        leverage=int(pos.leverage),
                    )
                else:
                    # Update existing
                    self.update_pnl(pos.position_id, float(pos.unrealized_pnl))
            
            # Remove positions that are no longer on exchange
            closed_ids = set(self._positions.keys()) - exchange_ids
            for position_id in closed_ids:
                self.remove_position(position_id)
            
            logger.debug(f"Synced {len(exchange_positions)} positions from exchange")
            
        except Exception as e:
            logger.error(f"Failed to sync positions: {e}")
    
    def get_total_exposure(self) -> float:
        """Get total exposure across all positions (in USD)."""
        total = 0.0
        for position in self._positions.values():
            qty = float(position.quantity)
            price = position.entry_price
            total += qty * price
        return total
    
    def get_total_pnl(self) -> float:
        """Get total unrealized PnL."""
        return sum(p.unrealized_pnl for p in self._positions.values())
    
    def clear(self) -> None:
        """Clear all tracked positions."""
        self._positions.clear()
        self._symbol_positions.clear()
