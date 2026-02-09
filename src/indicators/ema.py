"""
Exponential Moving Average (EMA)
================================

Fast-response moving average that weights recent prices more heavily.
"""

from typing import List, Optional
from dataclasses import dataclass


def calculate_ema(prices: List[float], period: int) -> List[float]:
    """
    Calculate Exponential Moving Average.
    
    Args:
        prices: List of price values (oldest to newest)
        period: EMA period
        
    Returns:
        List of EMA values (same length as input, with NaN for insufficient data)
    """
    if len(prices) < period:
        return [float('nan')] * len(prices)
    
    ema_values = []
    multiplier = 2 / (period + 1)
    
    # First EMA is SMA of first 'period' prices
    sma = sum(prices[:period]) / period
    ema_values.extend([float('nan')] * (period - 1))
    ema_values.append(sma)
    
    # Calculate remaining EMAs
    for price in prices[period:]:
        ema = (price - ema_values[-1]) * multiplier + ema_values[-1]
        ema_values.append(ema)
    
    return ema_values


@dataclass
class EMAIndicator:
    """
    EMA indicator with crossover detection.
    
    Example:
        ema = EMAIndicator(fast_period=9, slow_period=21)
        ema.update(price)
        if ema.is_bullish_crossover():
            # Fast EMA crossed above slow EMA
    """
    
    fast_period: int = 9
    slow_period: int = 21
    
    def __post_init__(self):
        self._prices: List[float] = []
        self._fast_ema: List[float] = []
        self._slow_ema: List[float] = []
        self._prev_fast: Optional[float] = None
        self._prev_slow: Optional[float] = None
    
    def update(self, price: float) -> None:
        """Add new price and recalculate EMAs."""
        self._prices.append(price)
        
        # Store previous values for crossover detection
        if self._fast_ema:
            self._prev_fast = self._fast_ema[-1]
        if self._slow_ema:
            self._prev_slow = self._slow_ema[-1]
        
        # Recalculate EMAs
        self._fast_ema = calculate_ema(self._prices, self.fast_period)
        self._slow_ema = calculate_ema(self._prices, self.slow_period)
        
        # Trim to last 500 values to prevent memory growth
        if len(self._prices) > 500:
            self._prices = self._prices[-500:]
            self._fast_ema = self._fast_ema[-500:]
            self._slow_ema = self._slow_ema[-500:]
    
    def update_batch(self, prices: List[float]) -> None:
        """Batch update with multiple prices."""
        self._prices = prices[-500:]
        self._fast_ema = calculate_ema(self._prices, self.fast_period)
        self._slow_ema = calculate_ema(self._prices, self.slow_period)
    
    @property
    def fast_value(self) -> Optional[float]:
        """Get current fast EMA value."""
        if self._fast_ema and not self._is_nan(self._fast_ema[-1]):
            return self._fast_ema[-1]
        return None
    
    @property
    def slow_value(self) -> Optional[float]:
        """Get current slow EMA value."""
        if self._slow_ema and not self._is_nan(self._slow_ema[-1]):
            return self._slow_ema[-1]
        return None
    
    def is_bullish(self) -> bool:
        """Check if fast EMA is above slow EMA (uptrend)."""
        if self.fast_value is None or self.slow_value is None:
            return False
        return self.fast_value > self.slow_value
    
    def is_bearish(self) -> bool:
        """Check if fast EMA is below slow EMA (downtrend)."""
        if self.fast_value is None or self.slow_value is None:
            return False
        return self.fast_value < self.slow_value
    
    def is_bullish_crossover(self) -> bool:
        """Check if fast EMA just crossed above slow EMA."""
        if (self._prev_fast is None or self._prev_slow is None or
            self.fast_value is None or self.slow_value is None):
            return False
        
        was_below = self._prev_fast <= self._prev_slow
        is_above = self.fast_value > self.slow_value
        return was_below and is_above
    
    def is_bearish_crossover(self) -> bool:
        """Check if fast EMA just crossed below slow EMA."""
        if (self._prev_fast is None or self._prev_slow is None or
            self.fast_value is None or self.slow_value is None):
            return False
        
        was_above = self._prev_fast >= self._prev_slow
        is_below = self.fast_value < self.slow_value
        return was_above and is_below
    
    def is_ready(self) -> bool:
        """Check if enough data for valid calculation."""
        return (self.fast_value is not None and 
                self.slow_value is not None)
    
    @staticmethod
    def _is_nan(value: float) -> bool:
        return value != value  # NaN != NaN
