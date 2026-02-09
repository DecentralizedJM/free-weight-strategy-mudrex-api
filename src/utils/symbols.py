"""
Symbol Fetcher
==============

Fetches all available perpetual futures symbols from Bybit.
Note: Bybit has more symbols than Mudrex supports, but Mudrex will fail
gracefully if a symbol is not supported.
"""

import logging
from typing import List, Optional
import aiohttp

logger = logging.getLogger(__name__)

# Bybit V5 API endpoint for instruments info
BYBIT_INSTRUMENTS_URL = "https://api.bybit.com/v5/market/instruments-info"


async def fetch_all_symbols(api_secret: Optional[str] = None) -> List[str]:
    """
    Fetch all available perpetual futures symbols from Bybit.
        
    Returns:
        List of symbol names (e.g., ["BTCUSDT", "ETHUSDT", ...])
    """
    symbols = []
    
    try:
        async with aiohttp.ClientSession() as session:
            params = {
                "category": "linear",
                "limit": 1000,
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
                        # and standard USDT perpetuals (not dated futures)
                        symbol = inst.get("symbol", "")
                        if inst.get("status") == "Trading" and symbol.endswith("USDT") and "-" not in symbol:
                            symbols.append(symbol)
                    
                    # Check for pagination
                    cursor = result.get("nextPageCursor")
                    if not cursor:
                        break
        
        logger.info(f"Fetched {len(symbols)} linear perpetual symbols from Bybit")
        
    except Exception as e:
        logger.error(f"Error fetching symbols: {e}")
    
    return symbols if symbols else FALLBACK_SYMBOLS


def fetch_all_symbols_sync(api_secret: Optional[str] = None) -> List[str]:
    """
    Synchronous wrapper to fetch all symbols.
    Used during config loading.
    """
    import asyncio
    
    try:
        loop = asyncio.get_running_loop()
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(asyncio.run, fetch_all_symbols(api_secret))
            return future.result(timeout=30)
    except RuntimeError:
        return asyncio.run(fetch_all_symbols(api_secret))


# Expanded fallback list of major symbols (verified on both Bybit and Mudrex)
FALLBACK_SYMBOLS = [
    # Major coins
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT",
    "ADAUSDT", "AVAXUSDT", "LINKUSDT", "DOTUSDT", "LTCUSDT",
    "UNIUSDT", "ATOMUSDT", "XLMUSDT", "ETCUSDT", "FILUSDT",
    "APTUSDT", "NEARUSDT", "ARBUSDT", "OPUSDT", "BNBUSDT",
    "TRXUSDT", "SUIUSDT", "MATICUSDT",
    # Layer 1s
    "INJUSDT", "SEIUSDT", "TIAUSDT", "TAOUSDT", "KASUSDT",
    # DeFi
    "AAVEUSDT", "MKRUSDT", "CRVUSDT", "LDOUSDT", "COMPUSDT",
    # Meme coins (correct Bybit symbols)
    "1000PEPEUSDT", "1000SHIBUSDT", "1000FLOKIUSDT", "WIFUSDT", "BONKUSDT",
    # AI coins
    "RENDERUSDT", "FETUSDT", "AGIXUSDT", "OCEANUSDT",
    # Gaming
    "IMXUSDT", "GALAUSDT", "SANDUSDT", "AXSUSDT", "MANAUSDT",
    # Others
    "HBARUSDT", "ALGOUSDT", "ICPUSDT", "VETUSDT", "RUNEUSDT",
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
