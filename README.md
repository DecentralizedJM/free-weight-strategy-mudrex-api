# Free Weight Strategy

An advanced multi-indicator confluence trading strategy for crypto perpetual futures using Mudrex API.

## Features

- **Multi-Indicator Confluence**: Combines EMA, RSI, MACD, Open Interest, and Funding Rate
- **Real-Time Data**: Bybit WebSocket for live market data
- **Smart Risk Management**: ATR-based dynamic stop-loss and position sizing
- **Mudrex Integration**: Seamless order execution via Mudrex API

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure

```bash
cp .env.example .env
cp config.example.yaml config.yaml
```

Edit `.env` with your Mudrex API secret:
```
MUDREX_API_SECRET=your_api_secret_here
```

Edit `config.yaml` to customize strategy parameters.

### 3. Run (Dry-Run Mode)

```bash
python -m src.main --dry-run
```

### 4. Run (Live Trading)

```bash
python -m src.main
```

## Strategy Logic

| Indicator | Purpose | Signal |
|-----------|---------|--------|
| EMA (9/21) | Trend | EMA9 > EMA21 = Uptrend |
| RSI (14) | Momentum | <30 oversold, >70 overbought |
| MACD | Confirmation | Bullish/Bearish crossover |
| Open Interest | Participation | Rising OI = Strong move |
| Funding Rate | Sentiment | Extreme negative = Short squeeze |

**Entry**: Minimum 3/5 indicators aligned + confluence score ≥ 60%

## Risk Management

- Max 2% capital per trade
- Dynamic SL based on 1.5x ATR
- TP at 2:1 or 3:1 risk-reward ratio
- No overlapping positions on same symbol

## Configuration

See `config.example.yaml` for all available options:
- Trading symbols and timeframes
- Indicator periods
- Risk parameters
- Leverage settings

## License

MIT License
