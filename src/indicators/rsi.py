"""
Relative Strength Index (RSI)
=============================

Momentum oscillator measuring speed and magnitude of price movements.
Values range from 0-100, with <30 oversold and >70 overbought.
"""

from typing import List, Optional
from dataclasses import dataclass


def calculate_rsi(prices: List[float], period: int = 14) -> List[float]:
    """
    Calculate RSI using Wilder's smoothing method.
    
    Args:
        prices: List of price values (oldest to newest)
        period: RSI period (default: 14)
        
    Returns:
        List of RSI values (0-100)
    """
    if len(prices) < period + 1:
        return [float('nan')] * len(prices)
    
    # Calculate price changes
    changes = []
    for i in range(1, len(prices)):
        changes.append(prices[i] - prices[i - 1])
    
    # Separate gains and losses
    gains = [max(0, c) for c in changes]
    losses = [abs(min(0, c)) for c in changes]
    
    rsi_values = [float('nan')] * period
    
    # First average gain/loss (SMA)
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    
    # Calculate first RSI
    if avg_loss == 0:
        rsi_values.append(100.0)
    else:
        rs = avg_gain / avg_loss
        rsi_values.append(100 - (100 / (1 + rs)))
    
    # Calculate remaining RSI values using Wilder's smoothing
    for i in range(period, len(changes)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        
        if avg_loss == 0:
            rsi_values.append(100.0)
        else:
            rs = avg_gain / avg_loss
            rsi_values.append(100 - (100 / (1 + rs)))
    
    return rsi_values


@dataclass
class RSIIndicator:
    """
    RSI indicator with overbought/oversold detection.
    
    Example:
        rsi = RSIIndicator(period=14, oversold=30, overbought=70)
        rsi.update(price)
        if rsi.is_oversold():
            # Potential buying opportunity
    """
    
    period: int = 14
    oversold: float = 30.0
    overbought: float = 70.0
    
    def __post_init__(self):
        self._prices: List[float] = []
        self._rsi_values: List[float] = []
        self._prev_rsi: Optional[float] = None
    
    def update(self, price: float) -> None:
        """Add new price and recalculate RSI."""
        self._prices.append(price)
        
        # Store previous value
        if self._rsi_values and not self._is_nan(self._rsi_values[-1]):
            self._prev_rsi = self._rsi_values[-1]
        
        # Recalculate
        self._rsi_values = calculate_rsi(self._prices, self.period)
        
        # Trim to last 500 values
        if len(self._prices) > 500:
            self._prices = self._prices[-500:]
            self._rsi_values = self._rsi_values[-500:]
    
    def update_batch(self, prices: List[float]) -> None:
        """Batch update with multiple prices."""
        self._prices = prices[-500:]
        self._rsi_values = calculate_rsi(self._prices, self.period)
    
    @property
    def value(self) -> Optional[float]:
        """Get current RSI value."""
        if self._rsi_values and not self._is_nan(self._rsi_values[-1]):
            return self._rsi_values[-1]
        return None
    
    @property
    def previous_value(self) -> Optional[float]:
        """Get previous RSI value."""
        return self._prev_rsi
    
    def is_oversold(self) -> bool:
        """Check if RSI is in oversold zone (<30)."""
        return self.value is not None and self.value < self.oversold
    
    def is_overbought(self) -> bool:
        """Check if RSI is in overbought zone (>70)."""
        return self.value is not None and self.value > self.overbought
    
    def is_recovering_from_oversold(self) -> bool:
        """Check if RSI is rising from oversold conditions."""
        if self.value is None or self._prev_rsi is None:
            return False
        return (self._prev_rsi < self.oversold and 
                self.value > self._prev_rsi and
                self.value < 50)
    
    def is_falling_from_overbought(self) -> bool:
        """Check if RSI is falling from overbought conditions."""
        if self.value is None or self._prev_rsi is None:
            return False
        return (self._prev_rsi > self.overbought and 
                self.value < self._prev_rsi and
                self.value > 50)
    
    def is_bullish_zone(self) -> bool:
        """Check if RSI is in bullish zone (>50)."""
        return self.value is not None and self.value > 50
    
    def is_bearish_zone(self) -> bool:
        """Check if RSI is in bearish zone (<50)."""
        return self.value is not None and self.value < 50
    
    def is_ready(self) -> bool:
        """Check if enough data for valid calculation."""
        return self.value is not None
    
    @staticmethod
    def _is_nan(value: float) -> bool:
        return value != value
