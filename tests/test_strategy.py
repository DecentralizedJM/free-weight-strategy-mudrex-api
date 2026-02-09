"""
Unit Tests for Strategy Engine
==============================
"""

import pytest
from src.strategy.signals import Signal, SignalType, IndicatorStatus
from src.strategy.engine import StrategyEngine, SymbolState
from src.config import Config, IndicatorsConfig, StrategyConfig, RiskConfig


class TestSignal:
    """Tests for Signal class."""
    
    def test_signal_actionable(self):
        """Test signal actionability detection."""
        long_signal = Signal(
            symbol="BTCUSDT",
            signal_type=SignalType.LONG,
            confluence_score=70,
            indicators_aligned=4,
        )
        assert long_signal.is_actionable
        assert long_signal.is_long
        assert not long_signal.is_short
        assert long_signal.side == "LONG"
        
        neutral_signal = Signal(
            symbol="BTCUSDT",
            signal_type=SignalType.NEUTRAL,
            confluence_score=0,
            indicators_aligned=0,
        )
        assert not neutral_signal.is_actionable
    
    def test_signal_to_dict(self):
        """Test signal serialization."""
        signal = Signal(
            symbol="ETHUSDT",
            signal_type=SignalType.SHORT,
            confluence_score=65,
            indicators_aligned=3,
            entry_price=3000.0,
            stoploss_price=3100.0,
            takeprofit_price=2800.0,
        )
        
        d = signal.to_dict()
        assert d["symbol"] == "ETHUSDT"
        assert d["type"] == "SHORT"
        assert d["confluence_score"] == 65


class TestIndicatorStatus:
    """Tests for IndicatorStatus class."""
    
    def test_indicator_status_defaults(self):
        """Test default values."""
        status = IndicatorStatus()
        assert not status.ema_bullish
        assert not status.rsi_oversold
        assert status.oi_confirmation == "NEUTRAL"


class TestStrategyEngine:
    """Tests for StrategyEngine."""
    
    @pytest.fixture
    def config(self):
        """Create test configuration."""
        cfg = Config()
        cfg.symbols = ["BTCUSDT", "ETHUSDT"]
        cfg.timeframe = 5
        cfg.strategy.min_confluence_score = 60
        cfg.strategy.min_indicators_aligned = 3
        return cfg
    
    def test_engine_initialization(self, config):
        """Test engine initializes correctly."""
        engine = StrategyEngine(config)
        
        # Should have symbol states
        assert "BTCUSDT" in engine._symbols
        assert "ETHUSDT" in engine._symbols
    
    def test_engine_neutral_when_not_ready(self, config):
        """Engine should return neutral signal when indicators not ready."""
        engine = StrategyEngine(config)
        
        signal = engine.evaluate("BTCUSDT")
        
        assert signal.signal_type == SignalType.NEUTRAL
        assert "warming up" in signal.reason.lower()
    
    def test_engine_cooldown(self, config):
        """Engine should respect trade cooldown."""
        engine = StrategyEngine(config)
        state = engine._symbols["BTCUSDT"]
        
        # Simulate recent trade
        import time
        state.last_signal_time = time.time()
        
        # Update indicators with enough data
        prices = list(range(100, 200))
        for p in prices:
            state.ema.update(p)
            state.rsi.update(p)
            state.macd.update(p)
            state.atr.update(p + 2, p - 2, p)
        
        signal = engine.evaluate("BTCUSDT")
        
        assert signal.signal_type == SignalType.NEUTRAL
        assert "cooldown" in signal.reason.lower()
    
    def test_evaluate_indicators(self, config):
        """Test indicator evaluation."""
        engine = StrategyEngine(config)
        state = engine._symbols["BTCUSDT"]
        
        # Add sufficient data
        for i in range(50):
            state.ema.update(100 + i)
            state.rsi.update(100 + i)
            state.macd.update(100 + i)
            state.atr.update(102 + i, 98 + i, 100 + i)
        
        status = engine._evaluate_indicators(state)
        
        # In an uptrend, EMA should be bullish
        assert isinstance(status, IndicatorStatus)
    
    def test_confluence_scoring(self, config):
        """Test confluence score calculation."""
        engine = StrategyEngine(config)
        
        # All bullish indicators
        status = IndicatorStatus(
            ema_bullish=True,
            rsi_recovering=True,
            macd_bullish=True,
            oi_rising=True,
            oi_confirmation="BULLISH",
            funding_squeeze_risk="SHORT_SQUEEZE",
        )
        
        score, aligned = engine._calculate_long_score(status)
        
        assert score == 100  # All indicators aligned
        assert aligned == 5
    
    def test_get_indicator_values(self, config):
        """Test getting indicator values for debugging."""
        engine = StrategyEngine(config)
        state = engine._symbols["BTCUSDT"]
        
        # Add data
        for i in range(30):
            state.ema.update(100 + i)
        state.last_price = 129
        
        values = engine.get_indicator_values("BTCUSDT")
        
        assert "price" in values
        assert values["price"] == 129


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
