"""
Strategy Engine
===============

Core strategy logic that combines all indicators and generates trading signals.
Uses multi-indicator confluence for high-probability trade setups.
"""

import logging
import time
from typing import Dict, List, Optional
from dataclasses import dataclass, field

from src.config import Config
from src.indicators import EMAIndicator, RSIIndicator, MACDIndicator, ATRIndicator
from src.market_data import OpenInterestAnalyzer, FundingRateAnalyzer
from src.strategy.signals import Signal, SignalType, IndicatorStatus
from src.bybit_ws.client import OHLCV, Ticker

logger = logging.getLogger(__name__)


@dataclass
class SymbolState:
    """State tracking for a single symbol."""
    ema: EMAIndicator = field(default_factory=EMAIndicator)
    rsi: RSIIndicator = field(default_factory=RSIIndicator)
    macd: MACDIndicator = field(default_factory=MACDIndicator)
    atr: ATRIndicator = field(default_factory=ATRIndicator)
    oi: OpenInterestAnalyzer = field(default_factory=OpenInterestAnalyzer)
    funding: FundingRateAnalyzer = field(default_factory=FundingRateAnalyzer)
    
    last_price: float = 0.0
    last_signal_time: float = 0.0
    last_signal_type: SignalType = SignalType.NEUTRAL


class StrategyEngine:
    """
    Multi-indicator confluence strategy engine.
    
    Indicator Weights:
    - EMA Trend: 20%
    - RSI Momentum: 20%
    - MACD Confirmation: 20%
    - Open Interest: 20%
    - Funding Rate: 20%
    
    Total confluence score: 0-100%
    Minimum for entry: configurable (default 60%)
    
    Example:
        engine = StrategyEngine(config)
        engine.update_kline("BTCUSDT", kline)
        engine.update_ticker("BTCUSDT", ticker)
        signal = engine.evaluate("BTCUSDT")
        if signal.is_actionable:
            # Execute trade
    """
    
    # Indicator weights (must sum to 100)
    WEIGHT_EMA = 20
    WEIGHT_RSI = 20
    WEIGHT_MACD = 20
    WEIGHT_OI = 20
    WEIGHT_FUNDING = 20
    
    def __init__(self, config: Config):
        self.config = config
        self._symbols: Dict[str, SymbolState] = {}
        
        # Initialize state for each symbol
        for symbol in config.symbols:
            self._init_symbol(symbol)
    
    def _init_symbol(self, symbol: str) -> None:
        """Initialize indicators for a symbol."""
        cfg = self.config.indicators
        
        state = SymbolState(
            ema=EMAIndicator(
                fast_period=cfg.ema.fast_period,
                slow_period=cfg.ema.slow_period
            ),
            rsi=RSIIndicator(
                period=cfg.rsi.period,
                oversold=cfg.rsi.oversold,
                overbought=cfg.rsi.overbought
            ),
            macd=MACDIndicator(
                fast_period=cfg.macd.fast_period,
                slow_period=cfg.macd.slow_period,
                signal_period=cfg.macd.signal_period
            ),
            atr=ATRIndicator(period=cfg.atr.period),
            oi=OpenInterestAnalyzer(),
            funding=FundingRateAnalyzer(),
        )
        
        self._symbols[symbol] = state
        logger.debug(f"Initialized indicators for {symbol}")
    
    def update_kline(self, symbol: str, kline: OHLCV) -> None:
        """Update indicators with new kline data."""
        if symbol not in self._symbols:
            self._init_symbol(symbol)
        
        state = self._symbols[symbol]
        state.last_price = kline.close
        
        # Update technical indicators
        state.ema.update(kline.close)
        state.rsi.update(kline.close)
        state.macd.update(kline.close)
        state.atr.update(kline.high, kline.low, kline.close)
        
        # Update OI with price for confirmation
        state.oi.set_price(kline.close)
    
    def update_ticker(self, ticker: Ticker) -> None:
        """Update market data from ticker."""
        symbol = ticker.symbol
        
        if symbol not in self._symbols:
            self._init_symbol(symbol)
        
        state = self._symbols[symbol]
        state.last_price = ticker.last_price
        
        # Update OI
        state.oi.update_oi_only(ticker.open_interest)
        
        # Update funding rate
        state.funding.update(ticker.funding_rate)
    
    def update_batch(
        self,
        symbol: str,
        klines: List[OHLCV]
    ) -> None:
        """Batch update indicators with historical kline data."""
        if symbol not in self._symbols:
            self._init_symbol(symbol)
        
        state = self._symbols[symbol]
        
        closes = [k.close for k in klines]
        highs = [k.high for k in klines]
        lows = [k.low for k in klines]
        
        state.ema.update_batch(closes)
        state.rsi.update_batch(closes)
        state.macd.update_batch(closes)
        state.atr.update_batch(highs, lows, closes)
        
        if klines:
            state.last_price = klines[-1].close
        
        logger.debug(f"Batch updated {symbol} with {len(klines)} candles")
    
    def evaluate(self, symbol: str) -> Signal:
        """
        Evaluate all indicators and generate a trading signal.
        
        Returns:
            Signal with confluence score and trade parameters
        """
        if symbol not in self._symbols:
            return self._neutral_signal(symbol)
        
        state = self._symbols[symbol]
        
        # Check cooldown
        if not self._check_cooldown(state):
            return self._neutral_signal(symbol, reason="Cooldown active")
        
        # Check if indicators are ready
        if not self._indicators_ready(state):
            return self._neutral_signal(symbol, reason="Indicators warming up")
        
        # Evaluate each indicator
        indicator_status = self._evaluate_indicators(state)
        
        # Calculate confluence scores for long and short
        long_score, long_aligned = self._calculate_long_score(indicator_status)
        short_score, short_aligned = self._calculate_short_score(indicator_status)
        
        # Determine signal type
        min_score = self.config.strategy.min_confluence_score
        min_aligned = self.config.strategy.min_indicators_aligned
        
        if long_score >= min_score and long_aligned >= min_aligned:
            return self._create_signal(
                symbol, SignalType.LONG, long_score, long_aligned,
                state, indicator_status
            )
        elif short_score >= min_score and short_aligned >= min_aligned:
            return self._create_signal(
                symbol, SignalType.SHORT, short_score, short_aligned,
                state, indicator_status
            )
        else:
            return self._neutral_signal(
                symbol,
                reason=f"Confluence too low (L:{long_score}% S:{short_score}%)"
            )
    
    def _evaluate_indicators(self, state: SymbolState) -> IndicatorStatus:
        """Evaluate all indicators and return status."""
        # OI signal
        oi_signal = state.oi.get_signal()
        
        # Funding signal
        funding_signal = state.funding.get_signal()
        
        return IndicatorStatus(
            ema_bullish=state.ema.is_bullish(),
            ema_crossover=state.ema.is_bullish_crossover(),
            rsi_oversold=state.rsi.is_oversold(),
            rsi_overbought=state.rsi.is_overbought(),
            rsi_recovering=state.rsi.is_recovering_from_oversold(),
            rsi_falling=state.rsi.is_falling_from_overbought(),
            macd_bullish=state.macd.is_bullish(),
            macd_crossover=state.macd.is_bullish_crossover(),
            macd_histogram_rising=state.macd.is_histogram_rising(),
            oi_rising=oi_signal.is_rising,
            oi_confirmation=oi_signal.confirmation,
            funding_sentiment=funding_signal.sentiment,
            funding_squeeze_risk=funding_signal.squeeze_risk,
        )
    
    def _calculate_long_score(self, status: IndicatorStatus) -> tuple[int, int]:
        """Calculate confluence score for LONG signal."""
        score = 0
        aligned = 0
        
        # EMA: Bullish trend (crossover gets extra weight)
        if status.ema_bullish:
            score += self.WEIGHT_EMA
            aligned += 1
        elif status.ema_crossover:
            score += self.WEIGHT_EMA
            aligned += 1
        
        # RSI: Oversold or recovering
        if status.rsi_recovering or status.rsi_oversold:
            score += self.WEIGHT_RSI
            aligned += 1
        elif status.rsi_overbought:
            score -= 10  # Penalty for overbought on long
        
        # MACD: Bullish or bullish crossover
        if status.macd_bullish or status.macd_crossover:
            score += self.WEIGHT_MACD
            aligned += 1
        
        # OI: Rising with bullish confirmation
        if status.oi_rising and status.oi_confirmation == "BULLISH":
            score += self.WEIGHT_OI
            aligned += 1
        elif status.oi_rising:
            score += self.WEIGHT_OI // 2  # Partial credit
        
        # Funding: Short squeeze potential or neutral/short heavy
        if status.funding_squeeze_risk == "SHORT_SQUEEZE":
            score += self.WEIGHT_FUNDING
            aligned += 1
        elif status.funding_sentiment == "SHORT_HEAVY":
            score += self.WEIGHT_FUNDING // 2
        elif status.funding_sentiment == "LONG_HEAVY":
            score -= 10  # Penalty for crowded longs
        
        return max(0, min(100, score)), aligned
    
    def _calculate_short_score(self, status: IndicatorStatus) -> tuple[int, int]:
        """Calculate confluence score for SHORT signal."""
        score = 0
        aligned = 0
        
        # EMA: Bearish trend
        if not status.ema_bullish and not status.ema_crossover:
            score += self.WEIGHT_EMA
            aligned += 1
        
        # RSI: Overbought or falling
        if status.rsi_falling or status.rsi_overbought:
            score += self.WEIGHT_RSI
            aligned += 1
        elif status.rsi_oversold:
            score -= 10  # Penalty for oversold on short
        
        # MACD: Bearish
        if not status.macd_bullish:
            score += self.WEIGHT_MACD
            aligned += 1
        
        # OI: Rising with bearish confirmation
        if status.oi_rising and status.oi_confirmation == "BEARISH":
            score += self.WEIGHT_OI
            aligned += 1
        elif status.oi_rising:
            score += self.WEIGHT_OI // 2
        
        # Funding: Long squeeze potential or long heavy
        if status.funding_squeeze_risk == "LONG_SQUEEZE":
            score += self.WEIGHT_FUNDING
            aligned += 1
        elif status.funding_sentiment == "LONG_HEAVY":
            score += self.WEIGHT_FUNDING // 2
        elif status.funding_sentiment == "SHORT_HEAVY":
            score -= 10  # Penalty for crowded shorts
        
        return max(0, min(100, score)), aligned
    
    def _create_signal(
        self,
        symbol: str,
        signal_type: SignalType,
        score: int,
        aligned: int,
        state: SymbolState,
        status: IndicatorStatus
    ) -> Signal:
        """Create a trading signal with price levels."""
        entry_price = state.last_price
        
        # Calculate SL/TP using ATR
        risk_cfg = self.config.risk
        
        stoploss_price = state.atr.calculate_stoploss(
            entry_price,
            signal_type.value,
            risk_cfg.stoploss_atr_multiplier
        )
        
        takeprofit_price = state.atr.calculate_takeprofit(
            entry_price,
            signal_type.value,
            risk_cfg.takeprofit_ratio,
            risk_cfg.stoploss_atr_multiplier
        )
        
        # Build reason string
        reasons = []
        if signal_type == SignalType.LONG:
            if status.ema_bullish:
                reasons.append("EMA↑")
            if status.rsi_recovering or status.rsi_oversold:
                reasons.append("RSI oversold")
            if status.macd_bullish:
                reasons.append("MACD↑")
            if status.oi_rising:
                reasons.append("OI↑")
            if status.funding_squeeze_risk == "SHORT_SQUEEZE":
                reasons.append("Short squeeze risk")
        else:
            if not status.ema_bullish:
                reasons.append("EMA↓")
            if status.rsi_falling or status.rsi_overbought:
                reasons.append("RSI overbought")
            if not status.macd_bullish:
                reasons.append("MACD↓")
            if status.oi_rising:
                reasons.append("OI↑")
            if status.funding_squeeze_risk == "LONG_SQUEEZE":
                reasons.append("Long squeeze risk")
        
        # Update state
        state.last_signal_time = time.time()
        state.last_signal_type = signal_type
        
        return Signal(
            symbol=symbol,
            signal_type=signal_type,
            confluence_score=score,
            indicators_aligned=aligned,
            entry_price=entry_price,
            stoploss_price=stoploss_price,
            takeprofit_price=takeprofit_price,
            leverage=risk_cfg.default_leverage,
            position_size_pct=risk_cfg.max_capital_per_trade,
            indicator_status=status,
            reason=", ".join(reasons),
        )
    
    def _neutral_signal(self, symbol: str, reason: str = "") -> Signal:
        """Create a neutral (no action) signal."""
        return Signal(
            symbol=symbol,
            signal_type=SignalType.NEUTRAL,
            confluence_score=0,
            indicators_aligned=0,
            reason=reason,
        )
    
    def _check_cooldown(self, state: SymbolState) -> bool:
        """Check if cooldown period has passed."""
        if state.last_signal_time == 0:
            return True
        
        elapsed = time.time() - state.last_signal_time
        return elapsed >= self.config.strategy.trade_cooldown
    
    def _indicators_ready(self, state: SymbolState) -> bool:
        """Check if all indicators have sufficient data."""
        return (
            state.ema.is_ready() and
            state.rsi.is_ready() and
            state.macd.is_ready() and
            state.atr.is_ready()
        )
    
    def get_indicator_values(self, symbol: str) -> dict:
        """Get current indicator values for debugging."""
        if symbol not in self._symbols:
            return {}
        
        state = self._symbols[symbol]
        
        return {
            "price": state.last_price,
            "ema_fast": state.ema.fast_value,
            "ema_slow": state.ema.slow_value,
            "ema_bullish": state.ema.is_bullish(),
            "rsi": state.rsi.value,
            "macd": state.macd.macd,
            "macd_signal": state.macd.signal,
            "macd_histogram": state.macd.histogram,
            "atr": state.atr.value,
            "oi_signal": state.oi.get_signal().__dict__,
            "funding_signal": state.funding.get_signal().__dict__,
        }
