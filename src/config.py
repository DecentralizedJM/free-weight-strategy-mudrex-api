"""
Configuration Module
====================

Loads and validates configuration from YAML files and environment variables.
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
    max_capital_per_trade: float = 2.0
    stoploss_atr_multiplier: float = 1.5
    takeprofit_ratio: float = 2.0
    default_leverage: int = 5
    max_leverage: int = 10


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
class Config:
    """Main configuration container."""
    
    # API credentials
    mudrex_api_secret: str = ""
    
    # Trading settings
    symbols: List[str] = field(default_factory=lambda: ["BTCUSDT"])
    timeframe: int = 5
    
    # Sub-configs
    indicators: IndicatorsConfig = field(default_factory=IndicatorsConfig)
    strategy: StrategyConfig = field(default_factory=StrategyConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    bybit: BybitConfig = field(default_factory=BybitConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    
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
            logger.warning(f"Config file {config_path} not found, using defaults")
        
        # Override with environment variables
        config.mudrex_api_secret = os.getenv("MUDREX_API_SECRET", "")
        config.dry_run = os.getenv("DRY_RUN", "false").lower() == "true"
        
        if log_level := os.getenv("LOG_LEVEL"):
            config.logging.level = log_level
        
        return config
    
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
        
        if self.risk.max_capital_per_trade > 10:
            logger.warning("Risk per trade >10% is very aggressive!")
        
        return True
