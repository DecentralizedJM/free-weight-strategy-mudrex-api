"""
Configuration Module
====================

Loads and validates configuration from YAML files and environment variables.
Optimized for Railway deployment with full environment variable support.
"""

import os
import logging
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass, field
import yaml
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


@dataclass
class EMAConfig:
    fast_period: int = 9
    slow_period: int = 21


@dataclass
class RSIConfig:
    period: int = 14
    oversold: int = 30
    overbought: int = 70


@dataclass
class MACDConfig:
    fast_period: int = 12
    slow_period: int = 26
    signal_period: int = 9


@dataclass
class ATRConfig:
    period: int = 14


@dataclass
class IndicatorsConfig:
    ema: EMAConfig = field(default_factory=EMAConfig)
    rsi: RSIConfig = field(default_factory=RSIConfig)
    macd: MACDConfig = field(default_factory=MACDConfig)
    atr: ATRConfig = field(default_factory=ATRConfig)


@dataclass
class StrategyConfig:
    min_confluence_score: int = 60
    min_indicators_aligned: int = 3
    trade_cooldown: int = 300
    max_positions_per_symbol: int = 1


@dataclass
class RiskConfig:
    # Margin percentage - how much of your balance to use per trade
    margin_percent: float = 5.0  # 5% of balance as margin
    
    # Min/Max leverage for auto-scaling
    min_leverage: int = 1
    max_leverage: int = 20
    default_leverage: int = 5
    
    # Minimum order value to meet (will scale leverage to achieve this)
    min_order_value: float = 8.0
    
    # Stop-loss / Take-profit
    stoploss_atr_multiplier: float = 1.5
    takeprofit_ratio: float = 2.0
    
    # Legacy field (kept for compatibility, now uses margin_percent)
    max_capital_per_trade: float = 2.0


@dataclass
class BybitConfig:
    ws_url: str = "wss://stream.bybit.com/v5/public/linear"
    rest_url: str = "https://api.bybit.com"
    ping_interval: int = 20
    reconnect_delay: int = 5


@dataclass
class LoggingConfig:
    level: str = "INFO"
    file: Optional[str] = None
    max_size: int = 10
    backup_count: int = 5


@dataclass
class TelegramConfig:
    """Telegram alert configuration."""
    bot_token: str = ""
    chat_id: str = ""
    enabled: bool = False
    
    def is_valid(self) -> bool:
        return bool(self.bot_token and self.chat_id and self.enabled)


@dataclass
class Config:
    """Main configuration container."""
    
    # API credentials
    mudrex_api_secret: str = ""
    
    # Trading settings
    # Empty list = fetch ALL available symbols from Bybit at startup
    symbols: List[str] = field(default_factory=list)
    timeframe: int = 5
    
    # Sub-configs
    indicators: IndicatorsConfig = field(default_factory=IndicatorsConfig)
    strategy: StrategyConfig = field(default_factory=StrategyConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    bybit: BybitConfig = field(default_factory=BybitConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    telegram: TelegramConfig = field(default_factory=TelegramConfig)
    
    # Runtime flags
    dry_run: bool = False
    
    @classmethod
    def load(cls, config_path: str = "config.yaml") -> "Config":
        """Load configuration from YAML file and environment variables."""
        config = cls()
        
        # Load from YAML if exists
        if Path(config_path).exists():
            with open(config_path, "r") as f:
                yaml_config = yaml.safe_load(f) or {}
            config = cls._from_dict(yaml_config)
            logger.info(f"Loaded configuration from {config_path}")
        else:
            logger.warning(f"Config file {config_path} not found, using defaults/env vars")
        
        # Override with environment variables (Railway-friendly)
        config._load_from_env()
        
        return config
    
    def _load_from_env(self) -> None:
        """Load/override configuration from environment variables."""
        # Core settings
        self.mudrex_api_secret = os.getenv("MUDREX_API_SECRET", self.mudrex_api_secret)
        self.dry_run = os.getenv("DRY_RUN", "false").lower() == "true"
        
        # Symbols (comma-separated)
        if symbols := os.getenv("SYMBOLS"):
            self.symbols = [s.strip().upper() for s in symbols.split(",")]
        
        # Timeframe
        if timeframe := os.getenv("TIMEFRAME"):
            self.timeframe = int(timeframe)
        
        # Risk settings
        if margin_pct := os.getenv("MARGIN_PERCENT"):
            self.risk.margin_percent = float(margin_pct)
        
        if min_leverage := os.getenv("MIN_LEVERAGE"):
            self.risk.min_leverage = int(min_leverage)
        
        if max_leverage := os.getenv("MAX_LEVERAGE"):
            self.risk.max_leverage = int(max_leverage)
        
        if default_leverage := os.getenv("DEFAULT_LEVERAGE"):
            self.risk.default_leverage = int(default_leverage)
        
        if min_order := os.getenv("MIN_ORDER_VALUE"):
            self.risk.min_order_value = float(min_order)
        
        if sl_mult := os.getenv("STOPLOSS_ATR_MULTIPLIER"):
            self.risk.stoploss_atr_multiplier = float(sl_mult)
        
        if tp_ratio := os.getenv("TAKEPROFIT_RATIO"):
            self.risk.takeprofit_ratio = float(tp_ratio)
        
        # Strategy settings
        if confluence := os.getenv("MIN_CONFLUENCE_SCORE"):
            self.strategy.min_confluence_score = int(confluence)
        
        if indicators := os.getenv("MIN_INDICATORS_ALIGNED"):
            self.strategy.min_indicators_aligned = int(indicators)
        
        if cooldown := os.getenv("TRADE_COOLDOWN"):
            self.strategy.trade_cooldown = int(cooldown)
        
        if max_pos := os.getenv("MAX_POSITIONS_PER_SYMBOL"):
            self.strategy.max_positions_per_symbol = int(max_pos)
        
        # Logging
        if log_level := os.getenv("LOG_LEVEL"):
            self.logging.level = log_level
        
        if log_file := os.getenv("LOG_FILE"):
            self.logging.file = log_file
        
        # Telegram
        if bot_token := os.getenv("TELEGRAM_BOT_TOKEN"):
            self.telegram.bot_token = bot_token
        
        if chat_id := os.getenv("TELEGRAM_CHAT_ID"):
            self.telegram.chat_id = chat_id
        
        # Enable telegram if both are set
        if self.telegram.bot_token and self.telegram.chat_id:
            self.telegram.enabled = os.getenv("TELEGRAM_ENABLED", "true").lower() == "true"
    
    @classmethod
    def _from_dict(cls, data: dict) -> "Config":
        """Create Config from dictionary."""
        config = cls()
        
        # Simple fields
        config.symbols = data.get("symbols", config.symbols)
        config.timeframe = data.get("timeframe", config.timeframe)
        
        # Indicators
        if ind := data.get("indicators"):
            if ema := ind.get("ema"):
                config.indicators.ema = EMAConfig(**ema)
            if rsi := ind.get("rsi"):
                config.indicators.rsi = RSIConfig(**rsi)
            if macd := ind.get("macd"):
                config.indicators.macd = MACDConfig(**macd)
            if atr := ind.get("atr"):
                config.indicators.atr = ATRConfig(**atr)
        
        # Strategy
        if strat := data.get("strategy"):
            config.strategy = StrategyConfig(**strat)
        
        # Risk
        if risk := data.get("risk"):
            config.risk = RiskConfig(**risk)
        
        # Bybit
        if bybit := data.get("bybit"):
            config.bybit = BybitConfig(**bybit)
        
        # Logging
        if log := data.get("logging"):
            config.logging = LoggingConfig(**log)
        
        return config
    
    def validate(self) -> bool:
        """Validate configuration."""
        if not self.mudrex_api_secret and not self.dry_run:
            logger.error("MUDREX_API_SECRET is required for live trading")
            return False
        
        if not self.symbols:
            logger.error("At least one trading symbol is required")
            return False
        
        if self.risk.margin_percent > 20:
            logger.warning("Margin percent > 20% is very aggressive!")
        
        if self.risk.min_leverage > self.risk.max_leverage:
            logger.error("MIN_LEVERAGE cannot be greater than MAX_LEVERAGE")
            return False
        
        return True
    
    def print_config(self) -> None:
        """Print current configuration (for debugging)."""
        logger.info("=" * 50)
        logger.info("CONFIGURATION")
        logger.info("=" * 50)
        logger.info(f"Mode: {'DRY-RUN' if self.dry_run else 'LIVE'}")
        logger.info(f"Symbols: {', '.join(self.symbols)}")
        logger.info(f"Timeframe: {self.timeframe}m")
        logger.info(f"Margin %: {self.risk.margin_percent}%")
        logger.info(f"Leverage: {self.risk.min_leverage}-{self.risk.max_leverage}x (default: {self.risk.default_leverage}x)")
        logger.info(f"Min Order Value: ${self.risk.min_order_value}")
        logger.info(f"Confluence: {self.strategy.min_confluence_score}% / {self.strategy.min_indicators_aligned} indicators")
        logger.info("=" * 50)
