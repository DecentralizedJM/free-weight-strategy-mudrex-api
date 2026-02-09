"""
Symbol Fetcher
==============

Fetches all available perpetual futures symbols from Bybit.
"""

import logging
from typing import List, Optional
import aiohttp

logger = logging.getLogger(__name__)

# Bybit V5 API endpoint for instruments info
BYBIT_INSTRUMENTS_URL = "https://api.bybit.com/v5/market/instruments-info"


async def fetch_all_symbols(category: str = "linear") -> List[str]:
    """
    Fetch all available perpetual futures symbols from Bybit.
    
    Args:
        category: "linear" for USDT perpetuals, "inverse" for inverse contracts
        
    Returns:
        List of symbol names (e.g., ["BTCUSDT", "ETHUSDT", ...])
    """
    symbols = []
    
    try:
        async with aiohttp.ClientSession() as session:
            params = {
                "category": category,
                "limit": 1000,  # Max per request
            }
            
            cursor = None
            while True:
                if cursor:
                    params["cursor"] = cursor
                
                async with session.get(BYBIT_INSTRUMENTS_URL, params=params) as resp:
                    if resp.status != 200:
                        logger.error(f"Failed to fetch symbols: HTTP {resp.status}")
                        break
                    
                    data = await resp.json()
                    
                    if data.get("retCode") != 0:
                        logger.error(f"Bybit API error: {data.get('retMsg')}")
                        break
                    
                    result = data.get("result", {})
                    instruments = result.get("list", [])
                    
                    for inst in instruments:
                        # Only include trading instruments (status = "Trading")
                        if inst.get("status") == "Trading":
                            symbols.append(inst.get("symbol"))
                    
                    # Check for pagination
                    cursor = result.get("nextPageCursor")
                    if not cursor:
                        break
        
        logger.info(f"Fetched {len(symbols)} {category} perpetual symbols from Bybit")
        
    except Exception as e:
        logger.error(f"Error fetching symbols: {e}")
    
    return symbols


def fetch_all_symbols_sync() -> List[str]:
    """
    Synchronous wrapper to fetch all symbols.
    Used during config loading.
    """
    import asyncio
    
    try:
        # Check if we're already in an event loop
        loop = asyncio.get_running_loop()
        # If we are, we need to use a different approach
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(asyncio.run, fetch_all_symbols())
            return future.result(timeout=30)
    except RuntimeError:
        # No running loop, safe to use asyncio.run
        return asyncio.run(fetch_all_symbols())


# Fallback list of major symbols if API fetch fails
FALLBACK_SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT",
    "ADAUSDT", "AVAXUSDT", "LINKUSDT", "DOTUSDT", "MATICUSDT",
    "LTCUSDT", "UNIUSDT", "ATOMUSDT", "XLMUSDT", "ETCUSDT",
    "FILUSDT", "APTUSDT", "NEARUSDT", "ARBUSDT", "OPUSDT",
    "BNBUSDT", "TRXUSDT", "SHIBUSDT", "PEPEUSDT", "SUIUSDT",
]


def get_all_symbols() -> List[str]:
    """
    Get all available trading symbols.
    Falls back to a hardcoded list if API fetch fails.
    """
    try:
        symbols = fetch_all_symbols_sync()
        if symbols:
            return symbols
    except Exception as e:
        logger.warning(f"Could not fetch symbols from API: {e}")
    
    logger.warning(f"Using fallback list of {len(FALLBACK_SYMBOLS)} symbols")
    return FALLBACK_SYMBOLS
