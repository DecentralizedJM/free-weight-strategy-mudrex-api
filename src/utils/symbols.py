"""
Symbol Fetcher
==============

Fetches all available perpetual futures symbols from Mudrex API directly.
Falls back to Bybit if Mudrex fails.
"""

import logging
from typing import List, Optional
import aiohttp

logger = logging.getLogger(__name__)

# Mudrex direct API endpoint for asset listing
MUDREX_ASSETS_URL = "https://trade.mudrex.com/fapi/v1/futures"

# Bybit V5 API endpoint for instruments info (fallback)
BYBIT_INSTRUMENTS_URL = "https://api.bybit.com/v5/market/instruments-info"


async def fetch_mudrex_symbols(api_secret: str) -> List[str]:
    """
    Fetch all available futures symbols directly from Mudrex API.
    
    Args:
        api_secret: Mudrex API secret for authentication
        
    Returns:
        List of symbol names (e.g., ["BTCUSDT", "ETHUSDT", ...])
    """
    symbols = []
    
    try:
        async with aiohttp.ClientSession() as session:
            headers = {
                "X-Authentication": api_secret,
            }
            
            offset = 0
            limit = 100  # Fetch 100 at a time
            
            while True:
                params = {
                    "sort": "popularity",
                    "order": "asc",
                    "offset": offset,
                    "limit": limit,
                }
                
                async with session.get(MUDREX_ASSETS_URL, headers=headers, params=params) as resp:
                    if resp.status != 200:
                        logger.error(f"Mudrex API error: HTTP {resp.status}")
                        break
                    
                    data = await resp.json()
                    
                    if not data.get("success"):
                        logger.error(f"Mudrex API error: {data}")
                        break
                    
                    assets = data.get("data", [])
                    
                    if not assets:
                        break  # No more assets
                    
                    for asset in assets:
                        symbol = asset.get("symbol")
                        if symbol:
                            symbols.append(symbol)
                    
                    # Check if we got less than limit (last page)
                    if len(assets) < limit:
                        break
                    
                    offset += limit
        
        if symbols:
            logger.info(f"Fetched {len(symbols)} symbols from Mudrex")
        
    except Exception as e:
        logger.error(f"Error fetching Mudrex symbols: {e}")
    
    return symbols


async def fetch_bybit_symbols() -> List[str]:
    """Fallback: Fetch symbols from Bybit."""
    symbols = []
    
    try:
        async with aiohttp.ClientSession() as session:
            params = {"category": "linear", "limit": 1000}
            cursor = None
            
            while True:
                if cursor:
                    params["cursor"] = cursor
                
                async with session.get(BYBIT_INSTRUMENTS_URL, params=params) as resp:
                    if resp.status != 200:
                        break
                    
                    data = await resp.json()
                    if data.get("retCode") != 0:
                        break
                    
                    result = data.get("result", {})
                    instruments = result.get("list", [])
                    
                    for inst in instruments:
                        symbol = inst.get("symbol", "")
                        if inst.get("status") == "Trading" and symbol.endswith("USDT") and "-" not in symbol:
                            symbols.append(symbol)
                    
                    cursor = result.get("nextPageCursor")
                    if not cursor:
                        break
        
        if symbols:
            logger.info(f"Fetched {len(symbols)} symbols from Bybit (fallback)")
            
    except Exception as e:
        logger.error(f"Error fetching Bybit symbols: {e}")
    
    return symbols


async def fetch_all_symbols(api_secret: Optional[str] = None) -> List[str]:
    """
    Fetch all available symbols.
    Priority: Mudrex → Bybit → Fallback list
    """
    # Try Mudrex first
    if api_secret:
        symbols = await fetch_mudrex_symbols(api_secret)
        if symbols:
            return symbols
    
    # Fall back to Bybit
    symbols = await fetch_bybit_symbols()
    if symbols:
        return symbols
    
    # Last resort: hardcoded fallback
    logger.warning("Using fallback symbol list")
    return FALLBACK_SYMBOLS


def fetch_all_symbols_sync(api_secret: Optional[str] = None) -> List[str]:
    """Synchronous wrapper for fetch_all_symbols."""
    import asyncio
    
    try:
        loop = asyncio.get_running_loop()
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(asyncio.run, fetch_all_symbols(api_secret))
            return future.result(timeout=30)
    except RuntimeError:
        return asyncio.run(fetch_all_symbols(api_secret))


# Fallback list of major symbols
FALLBACK_SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT",
    "ADAUSDT", "AVAXUSDT", "LINKUSDT", "DOTUSDT", "LTCUSDT",
    "UNIUSDT", "ATOMUSDT", "XLMUSDT", "ETCUSDT", "FILUSDT",
    "APTUSDT", "NEARUSDT", "ARBUSDT", "OPUSDT", "BNBUSDT",
    "TRXUSDT", "SUIUSDT", "MATICUSDT", "INJUSDT", "SEIUSDT",
    "TIAUSDT", "TAOUSDT", "AAVEUSDT", "CRVUSDT", "LDOUSDT",
    "1000PEPEUSDT", "1000SHIBUSDT", "WIFUSDT", "BONKUSDT",
    "RENDERUSDT", "IMXUSDT", "GALAUSDT", "SANDUSDT", "MANAUSDT",
    "HBARUSDT", "ALGOUSDT", "ICPUSDT", "VETUSDT", "RUNEUSDT",
]


def get_all_symbols(api_secret: Optional[str] = None) -> List[str]:
    """Get all available trading symbols."""
    try:
        symbols = fetch_all_symbols_sync(api_secret)
        if symbols:
            return symbols
    except Exception as e:
        logger.warning(f"Could not fetch symbols from API: {e}")
    
    logger.warning(f"Using fallback list of {len(FALLBACK_SYMBOLS)} symbols")
    return FALLBACK_SYMBOLS

