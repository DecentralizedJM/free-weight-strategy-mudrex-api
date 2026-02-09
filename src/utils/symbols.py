"""
Symbol Fetcher
==============

Fetches all available perpetual futures symbols from Mudrex.
"""

import logging
from typing import List, Optional

logger = logging.getLogger(__name__)


def fetch_mudrex_symbols(api_secret: str) -> List[str]:
    """
    Fetch all available perpetual futures symbols from Mudrex.
    
    Args:
        api_secret: Mudrex API secret for authentication
        
    Returns:
        List of symbol names (e.g., ["BTCUSDT", "ETHUSDT", ...])
    """
    symbols = []
    
    try:
        from mudrex import MudrexClient
        client = MudrexClient(api_secret=api_secret)
        
        # Get all available assets from Mudrex
        assets = client.assets.list()
        
        if assets and hasattr(assets, '__iter__'):
            for asset in assets:
                # Get symbol name - handle both dict and object
                if isinstance(asset, dict):
                    symbol = asset.get('symbol') or asset.get('name')
                else:
                    symbol = getattr(asset, 'symbol', None) or getattr(asset, 'name', None)
                
                if symbol:
                    # Ensure symbol ends with USDT for perpetuals
                    if not symbol.endswith('USDT'):
                        symbol = f"{symbol}USDT"
                    symbols.append(symbol)
        
        # Deduplicate and sort
        symbols = sorted(list(set(symbols)))
        logger.info(f"Fetched {len(symbols)} symbols from Mudrex")
        
    except ImportError:
        logger.error("Mudrex SDK not installed")
    except Exception as e:
        logger.error(f"Error fetching Mudrex symbols: {e}")
    
    return symbols


async def fetch_all_symbols(api_secret: Optional[str] = None) -> List[str]:
    """
    Fetch all available symbols.
    Uses Mudrex if api_secret provided, otherwise falls back to defaults.
    
    Args:
        api_secret: Mudrex API secret (optional)
        
    Returns:
        List of symbol names
    """
    if api_secret:
        symbols = fetch_mudrex_symbols(api_secret)
        if symbols:
            return symbols
    
    logger.warning("Using fallback symbol list")
    return FALLBACK_SYMBOLS


def fetch_all_symbols_sync(api_secret: Optional[str] = None) -> List[str]:
    """
    Synchronous wrapper to fetch all symbols.
    Used during config loading.
    """
    if api_secret:
        symbols = fetch_mudrex_symbols(api_secret)
        if symbols:
            return symbols
    
    logger.warning("Using fallback symbol list")
    return FALLBACK_SYMBOLS


# Fallback list of major symbols if API fetch fails
FALLBACK_SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT",
    "ADAUSDT", "AVAXUSDT", "LINKUSDT", "DOTUSDT", "MATICUSDT",
    "LTCUSDT", "UNIUSDT", "ATOMUSDT", "XLMUSDT", "ETCUSDT",
    "FILUSDT", "APTUSDT", "NEARUSDT", "ARBUSDT", "OPUSDT",
    "BNBUSDT", "TRXUSDT", "SHIBUSDT", "PEPEUSDT", "SUIUSDT",
]


def get_all_symbols(api_secret: Optional[str] = None) -> List[str]:
    """
    Get all available trading symbols.
    Falls back to a hardcoded list if API fetch fails.
    """
    try:
        symbols = fetch_all_symbols_sync(api_secret)
        if symbols:
            return symbols
    except Exception as e:
        logger.warning(f"Could not fetch symbols from API: {e}")
    
    logger.warning(f"Using fallback list of {len(FALLBACK_SYMBOLS)} symbols")
    return FALLBACK_SYMBOLS

