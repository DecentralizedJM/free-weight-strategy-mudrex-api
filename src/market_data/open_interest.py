"""
Open Interest Analyzer
======================

Tracks and analyzes Open Interest data for market sentiment.
Rising OI + rising price = Strong uptrend
Rising OI + falling price = Strong downtrend
Falling OI = Trend weakening / Position closing
"""

from typing import List, Optional
from dataclasses import dataclass
import statistics


@dataclass
class OISignal:
    """Open Interest signal data."""
    is_rising: bool
    change_pct: float
    z_score: float
    is_extreme: bool
    confirmation: str  # "BULLISH", "BEARISH", or "NEUTRAL"


class OpenInterestAnalyzer:
    """
    Analyzes Open Interest data for trading signals.
    
    Key signals:
    - Rising OI + rising price = Bullish confirmation
    - Rising OI + falling price = Bearish confirmation
    - Falling OI + price move = Weak move (likely reversal)
    - Extreme OI z-score = Potential reversal
    
    Example:
        oi = OpenInterestAnalyzer()
        oi.update(current_oi, current_price)
        signal = oi.get_signal()
        if signal.is_rising and signal.confirmation == "BULLISH":
            # Strong bullish signal
    """
    
    def __init__(
        self,
        lookback_period: int = 20,
        extreme_threshold: float = 2.0,
    ):
        self.lookback_period = lookback_period
        self.extreme_threshold = extreme_threshold
        
        self._oi_history: List[float] = []
        self._price_history: List[float] = []
    
    def update(self, open_interest: float, price: float) -> None:
        """Update with new OI and price data."""
        self._oi_history.append(open_interest)
        self._price_history.append(price)
        
        # Trim to lookback + some buffer
        max_size = self.lookback_period * 2
        if len(self._oi_history) > max_size:
            self._oi_history = self._oi_history[-max_size:]
            self._price_history = self._price_history[-max_size:]
    
    def update_oi_only(self, open_interest: float) -> None:
        """Update with OI only (use when price is tracked separately)."""
        self._oi_history.append(open_interest)
        if len(self._oi_history) > self.lookback_period * 2:
            self._oi_history = self._oi_history[-(self.lookback_period * 2):]
    
    def set_price(self, price: float) -> None:
        """Set current price for confirmation logic."""
        self._price_history.append(price)
        if len(self._price_history) > self.lookback_period * 2:
            self._price_history = self._price_history[-(self.lookback_period * 2):]
    
    def get_signal(self) -> OISignal:
        """Get current OI signal."""
        if len(self._oi_history) < 2:
            return OISignal(
                is_rising=False,
                change_pct=0.0,
                z_score=0.0,
                is_extreme=False,
                confirmation="NEUTRAL"
            )
        
        # Calculate OI change
        current_oi = self._oi_history[-1]
        previous_oi = self._oi_history[-2]
        
        if previous_oi == 0:
            change_pct = 0.0
        else:
            change_pct = ((current_oi - previous_oi) / previous_oi) * 100
        
        is_rising = change_pct > 0
        
        # Calculate z-score for extreme detection
        z_score = self._calculate_z_score()
        is_extreme = abs(z_score) > self.extreme_threshold
        
        # Determine confirmation
        confirmation = self._get_confirmation(is_rising)
        
        return OISignal(
            is_rising=is_rising,
            change_pct=change_pct,
            z_score=z_score,
            is_extreme=is_extreme,
            confirmation=confirmation
        )
    
    def _calculate_z_score(self) -> float:
        """Calculate z-score of current OI vs historical mean."""
        if len(self._oi_history) < self.lookback_period:
            return 0.0
        
        recent = self._oi_history[-self.lookback_period:]
        
        try:
            mean = statistics.mean(recent)
            stdev = statistics.stdev(recent)
            
            if stdev == 0:
                return 0.0
            
            return (self._oi_history[-1] - mean) / stdev
        except statistics.StatisticsError:
            return 0.0
    
    def _get_confirmation(self, oi_rising: bool) -> str:
        """Get trend confirmation based on OI and price movement."""
        if len(self._price_history) < 2:
            return "NEUTRAL"
        
        price_rising = self._price_history[-1] > self._price_history[-2]
        
        if oi_rising:
            if price_rising:
                return "BULLISH"
            else:
                return "BEARISH"
        else:
            # Falling OI = weak signal
            return "NEUTRAL"
    
    def get_oi_change_rate(self, periods: int = 10) -> float:
        """Get OI change rate over last N periods (%)."""
        if len(self._oi_history) < periods + 1:
            return 0.0
        
        old_oi = self._oi_history[-(periods + 1)]
        new_oi = self._oi_history[-1]
        
        if old_oi == 0:
            return 0.0
        
        return ((new_oi - old_oi) / old_oi) * 100
    
    def is_ready(self) -> bool:
        """Check if enough data for valid analysis."""
        return len(self._oi_history) >= self.lookback_period
