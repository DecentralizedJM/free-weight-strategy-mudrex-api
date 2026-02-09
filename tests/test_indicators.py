"""
Unit Tests for Technical Indicators
====================================
"""

import pytest
from src.indicators.ema import calculate_ema, EMAIndicator
from src.indicators.rsi import calculate_rsi, RSIIndicator
from src.indicators.macd import calculate_macd, MACDIndicator
from src.indicators.atr import calculate_atr, ATRIndicator


class TestEMA:
    """Tests for EMA calculations."""
    
    def test_calculate_ema_insufficient_data(self):
        """EMA should return NaN for insufficient data."""
        prices = [100, 101, 102]
        result = calculate_ema(prices, period=5)
        assert all(x != x for x in result)  # All NaN
    
    def test_calculate_ema_basic(self):
        """EMA calculation should work correctly."""
        prices = [44, 44.5, 45, 43.5, 44, 44.5, 44.5, 44.25, 43.25, 44.5]
        result = calculate_ema(prices, period=5)
        
        # First valid EMA should be at index 4 (SMA of first 5)
        assert result[4] == pytest.approx(44.2, rel=0.01)
        assert len(result) == len(prices)
    
    def test_ema_indicator_crossover(self):
        """EMA indicator should detect crossovers."""
        ema = EMAIndicator(fast_period=3, slow_period=5)
        
        # Uptrend prices (fast should cross above slow)
        prices = [100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110]
        for p in prices:
            ema.update(p)
        
        assert ema.is_ready()
        assert ema.is_bullish()
    
    def test_ema_indicator_bearish(self):
        """EMA indicator should detect bearish trend."""
        ema = EMAIndicator(fast_period=3, slow_period=5)
        
        # Downtrend prices
        prices = [110, 109, 108, 107, 106, 105, 104, 103, 102, 101, 100]
        for p in prices:
            ema.update(p)
        
        assert ema.is_ready()
        assert ema.is_bearish()


class TestRSI:
    """Tests for RSI calculations."""
    
    def test_calculate_rsi_basic(self):
        """RSI should return values between 0 and 100."""
        # Create some price data with ups and downs
        prices = [44, 44.25, 44.5, 43.75, 44.5, 44.5, 44.25, 44.75, 
                  43.5, 44.5, 44.25, 44.5, 45, 44.75, 45.25, 46]
        
        result = calculate_rsi(prices, period=14)
        
        # First valid RSI should be at index 14
        valid_rsi = [r for r in result if r == r]  # Filter NaN
        assert len(valid_rsi) > 0
        assert all(0 <= r <= 100 for r in valid_rsi)
    
    def test_rsi_indicator_oversold(self):
        """RSI indicator should detect oversold conditions."""
        rsi = RSIIndicator(period=5, oversold=30, overbought=70)
        
        # Strong downtrend prices
        prices = [100, 98, 96, 94, 92, 90, 88, 86]
        for p in prices:
            rsi.update(p)
        
        assert rsi.is_ready()
        assert rsi.value is not None
        # After strong downtrend, RSI should be low
        assert rsi.value < 50
    
    def test_rsi_indicator_overbought(self):
        """RSI indicator should detect overbought conditions."""
        rsi = RSIIndicator(period=5, oversold=30, overbought=70)
        
        # Strong uptrend prices
        prices = [100, 102, 104, 106, 108, 110, 112, 114]
        for p in prices:
            rsi.update(p)
        
        assert rsi.is_ready()
        assert rsi.value is not None
        # After strong uptrend, RSI should be high
        assert rsi.value > 50


class TestMACD:
    """Tests for MACD calculations."""
    
    def test_calculate_macd_basic(self):
        """MACD calculation should return three lists."""
        # Generate enough prices
        prices = list(range(100, 150))
        
        macd_line, signal_line, histogram = calculate_macd(
            prices, fast_period=12, slow_period=26, signal_period=9
        )
        
        assert len(macd_line) == len(prices)
        assert len(signal_line) == len(prices)
        assert len(histogram) == len(prices)
    
    def test_macd_indicator_bullish(self):
        """MACD indicator should detect bullish conditions."""
        macd = MACDIndicator(fast_period=5, slow_period=10, signal_period=3)
        
        # Strong uptrend
        prices = list(range(100, 150))
        for p in prices:
            macd.update(p)
        
        assert macd.is_ready()
        # In uptrend, MACD should be above signal
        assert macd.is_bullish()
    
    def test_macd_indicator_histogram(self):
        """MACD histogram should exist when ready."""
        macd = MACDIndicator(fast_period=5, slow_period=10, signal_period=3)
        
        prices = list(range(100, 130))
        for p in prices:
            macd.update(p)
        
        assert macd.histogram is not None


class TestATR:
    """Tests for ATR calculations."""
    
    def test_calculate_atr_basic(self):
        """ATR calculation should work correctly."""
        # Sample OHLC data
        highs = [50, 51, 52, 51, 53, 54, 53, 55, 54, 56, 55, 57, 56, 58, 57, 59]
        lows = [48, 49, 50, 49, 51, 52, 51, 53, 52, 54, 53, 55, 54, 56, 55, 57]
        closes = [49, 50, 51, 50, 52, 53, 52, 54, 53, 55, 54, 56, 55, 57, 56, 58]
        
        result = calculate_atr(highs, lows, closes, period=5)
        
        valid_atr = [a for a in result if a == a]  # Filter NaN
        assert len(valid_atr) > 0
        assert all(a > 0 for a in valid_atr)
    
    def test_atr_indicator_stoploss(self):
        """ATR indicator should calculate stop-loss correctly."""
        atr = ATRIndicator(period=5)
        
        # Add data
        for i in range(10):
            high = 100 + i + 2
            low = 100 + i - 2
            close = 100 + i
            atr.update(high, low, close)
        
        assert atr.is_ready()
        assert atr.value is not None
        
        # Test stop-loss calculation
        entry = 110.0
        sl = atr.calculate_stoploss(entry, "LONG", multiplier=1.5)
        assert sl is not None
        assert sl < entry  # SL should be below entry for LONG
        
        sl_short = atr.calculate_stoploss(entry, "SHORT", multiplier=1.5)
        assert sl_short > entry  # SL should be above entry for SHORT
    
    def test_atr_indicator_takeprofit(self):
        """ATR indicator should calculate take-profit correctly."""
        atr = ATRIndicator(period=5)
        
        for i in range(10):
            atr.update(100 + i + 2, 100 + i - 2, 100 + i)
        
        entry = 110.0
        tp = atr.calculate_takeprofit(entry, "LONG", risk_reward=2.0)
        assert tp is not None
        assert tp > entry  # TP should be above entry for LONG


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
