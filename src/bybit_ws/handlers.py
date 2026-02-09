"""
WebSocket Message Handlers
==========================

Additional handlers for processing WebSocket messages.
"""

import logging
from typing import Callable, Dict, List, Optional
from dataclasses import dataclass

from src.bybit_ws.client import OHLCV, Ticker

logger = logging.getLogger(__name__)


class KlineHandler:
    """
    Handler for processing kline data with technical indicator integration.
    """
    
    def __init__(self, max_candles: int = 500):
        self.max_candles = max_candles
        self._klines: Dict[str, List[OHLCV]] = {}
        self._callbacks: List[Callable[[str, OHLCV], None]] = []
    
    def add_callback(self, callback: Callable[[str, OHLCV], None]) -> None:
        """Add a callback to be called on each new kline."""
        self._callbacks.append(callback)
    
    def handle(self, symbol: str, kline: OHLCV) -> None:
        """Process incoming kline data."""
        if symbol not in self._klines:
            self._klines[symbol] = []
        
        klines = self._klines[symbol]
        
        # Update or append
        if klines and klines[-1].timestamp == kline.timestamp:
            klines[-1] = kline
        else:
            klines.append(kline)
            if len(klines) > self.max_candles:
                klines.pop(0)
        
        # Fire callbacks
        for callback in self._callbacks:
            try:
                callback(symbol, kline)
            except Exception as e:
                logger.error(f"Kline callback error: {e}")
    
    def get_closes(self, symbol: str, count: int = 100) -> List[float]:
        """Get last N close prices."""
        klines = self._klines.get(symbol, [])
        return [k.close for k in klines[-count:]]
    
    def get_ohlcv(self, symbol: str, count: int = 100) -> List[OHLCV]:
        """Get last N candles."""
        return self._klines.get(symbol, [])[-count:]


class TickerHandler:
    """
    Handler for processing ticker data with OI and funding rate tracking.
    """
    
    def __init__(self, history_size: int = 100):
        self.history_size = history_size
        self._tickers: Dict[str, Ticker] = {}
        self._oi_history: Dict[str, List[float]] = {}
        self._funding_history: Dict[str, List[float]] = {}
        self._callbacks: List[Callable[[Ticker], None]] = []
    
    def add_callback(self, callback: Callable[[Ticker], None]) -> None:
        """Add a callback to be called on each ticker update."""
        self._callbacks.append(callback)
    
    def handle(self, ticker: Ticker) -> None:
        """Process incoming ticker data."""
        symbol = ticker.symbol
        self._tickers[symbol] = ticker
        
        # Track OI history
        if symbol not in self._oi_history:
            self._oi_history[symbol] = []
        oi_hist = self._oi_history[symbol]
        oi_hist.append(ticker.open_interest)
        if len(oi_hist) > self.history_size:
            oi_hist.pop(0)
        
        # Track funding rate history
        if symbol not in self._funding_history:
            self._funding_history[symbol] = []
        fr_hist = self._funding_history[symbol]
        fr_hist.append(ticker.funding_rate)
        if len(fr_hist) > self.history_size:
            fr_hist.pop(0)
        
        # Fire callbacks
        for callback in self._callbacks:
            try:
                callback(ticker)
            except Exception as e:
                logger.error(f"Ticker callback error: {e}")
    
    def get_ticker(self, symbol: str) -> Optional[Ticker]:
        """Get latest ticker for symbol."""
        return self._tickers.get(symbol)
    
    def get_oi_history(self, symbol: str) -> List[float]:
        """Get OI history for symbol."""
        return self._oi_history.get(symbol, [])
    
    def get_funding_history(self, symbol: str) -> List[float]:
        """Get funding rate history for symbol."""
        return self._funding_history.get(symbol, [])
    
    def get_oi_change(self, symbol: str, periods: int = 10) -> float:
        """Calculate OI change over last N periods."""
        oi_hist = self._oi_history.get(symbol, [])
        if len(oi_hist) < periods + 1:
            return 0.0
        
        old_oi = oi_hist[-(periods + 1)]
        new_oi = oi_hist[-1]
        
        if old_oi == 0:
            return 0.0
        
        return ((new_oi - old_oi) / old_oi) * 100
