"""
Funding Rate Analyzer
=====================

Analyzes funding rates for perpetual futures sentiment.
- Positive funding = Longs pay shorts (bullish crowd)
- Negative funding = Shorts pay longs (bearish crowd)
- Extreme funding = Potential for squeeze
"""

from typing import List, Optional
from dataclasses import dataclass
import statistics


@dataclass
class FundingSignal:
    """Funding rate signal data."""
    rate: float
    rate_annualized: float  # Annualized as percentage
    z_score: float
    is_extreme_positive: bool
    is_extreme_negative: bool
    sentiment: str  # "LONG_HEAVY", "SHORT_HEAVY", or "NEUTRAL"
    squeeze_risk: str  # "LONG_SQUEEZE", "SHORT_SQUEEZE", or "NONE"


class FundingRateAnalyzer:
    """
    Analyzes funding rate data for contrarian signals.
    
    Key signals:
    - Extreme positive funding = Overcrowded longs, risk of long squeeze
    - Extreme negative funding = Overcrowded shorts, risk of short squeeze
    - Neutral funding = Balanced positioning
    
    Example:
        fr = FundingRateAnalyzer()
        fr.update(funding_rate)
        signal = fr.get_signal()
        if signal.squeeze_risk == "SHORT_SQUEEZE":
            # Consider long position (contrarian)
    """
    
    # Bybit funding is every 8 hours (3x per day)
    FUNDING_PERIODS_PER_DAY = 3
    
    def __init__(
        self,
        lookback_period: int = 50,
        extreme_threshold_z: float = 2.0,
        extreme_threshold_rate: float = 0.0005,  # 0.05% per 8h = ~55% APR
    ):
        self.lookback_period = lookback_period
        self.extreme_threshold_z = extreme_threshold_z
        self.extreme_threshold_rate = extreme_threshold_rate
        
        self._funding_history: List[float] = []
    
    def update(self, funding_rate: float) -> None:
        """Update with new funding rate."""
        self._funding_history.append(funding_rate)
        
        # Trim to lookback + buffer
        max_size = self.lookback_period * 2
        if len(self._funding_history) > max_size:
            self._funding_history = self._funding_history[-max_size:]
    
    def get_signal(self) -> FundingSignal:
        """Get current funding rate signal."""
        if not self._funding_history:
            return FundingSignal(
                rate=0.0,
                rate_annualized=0.0,
                z_score=0.0,
                is_extreme_positive=False,
                is_extreme_negative=False,
                sentiment="NEUTRAL",
                squeeze_risk="NONE"
            )
        
        current_rate = self._funding_history[-1]
        
        # Annualize: rate * 3 periods/day * 365 days
        rate_annualized = current_rate * self.FUNDING_PERIODS_PER_DAY * 365 * 100
        
        # Calculate z-score
        z_score = self._calculate_z_score()
        
        # Determine extremes
        is_extreme_positive = (
            z_score > self.extreme_threshold_z or
            current_rate > self.extreme_threshold_rate
        )
        is_extreme_negative = (
            z_score < -self.extreme_threshold_z or
            current_rate < -self.extreme_threshold_rate
        )
        
        # Sentiment
        if is_extreme_positive:
            sentiment = "LONG_HEAVY"
        elif is_extreme_negative:
            sentiment = "SHORT_HEAVY"
        elif current_rate > 0.0001:
            sentiment = "LONG_HEAVY"
        elif current_rate < -0.0001:
            sentiment = "SHORT_HEAVY"
        else:
            sentiment = "NEUTRAL"
        
        # Squeeze risk (contrarian signal)
        if is_extreme_positive:
            squeeze_risk = "LONG_SQUEEZE"
        elif is_extreme_negative:
            squeeze_risk = "SHORT_SQUEEZE"
        else:
            squeeze_risk = "NONE"
        
        return FundingSignal(
            rate=current_rate,
            rate_annualized=rate_annualized,
            z_score=z_score,
            is_extreme_positive=is_extreme_positive,
            is_extreme_negative=is_extreme_negative,
            sentiment=sentiment,
            squeeze_risk=squeeze_risk
        )
    
    def _calculate_z_score(self) -> float:
        """Calculate z-score of current funding rate."""
        if len(self._funding_history) < self.lookback_period:
            return 0.0
        
        recent = self._funding_history[-self.lookback_period:]
        
        try:
            mean = statistics.mean(recent)
            stdev = statistics.stdev(recent)
            
            if stdev == 0:
                return 0.0
            
            return (self._funding_history[-1] - mean) / stdev
        except statistics.StatisticsError:
            return 0.0
    
    def get_avg_funding(self, periods: int = 10) -> float:
        """Get average funding rate over last N periods."""
        if len(self._funding_history) < periods:
            return 0.0
        
        return statistics.mean(self._funding_history[-periods:])
    
    def is_positive_streak(self, periods: int = 5) -> bool:
        """Check if funding has been positive for last N periods."""
        if len(self._funding_history) < periods:
            return False
        return all(r > 0 for r in self._funding_history[-periods:])
    
    def is_negative_streak(self, periods: int = 5) -> bool:
        """Check if funding has been negative for last N periods."""
        if len(self._funding_history) < periods:
            return False
        return all(r < 0 for r in self._funding_history[-periods:])
    
    def is_ready(self) -> bool:
        """Check if enough data for valid analysis."""
        return len(self._funding_history) >= 5
