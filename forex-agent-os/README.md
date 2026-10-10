# Forex Agent OS V1

A safety-first multi-agent Forex trading backend. V1 is DEMO/PAPER only by default.

## What works now
- FastAPI backend
- Trend Agent
- Mean Reversion Agent
- Ensemble decision engine
- ATR-based stop-loss and take-profit intent
- Deterministic Risk Engine
- Kill switch
- Demo/paper execution
- MT5 adapter boundary (disabled until configured)
- Risk tests

## Hard risk limits (defaults)
- Risk per trade: 0.5% equity
- Max daily loss: 2%
- Max drawdown: 10%
- Max open positions: 3
- Max EURUSD-like spread: 0.00030
- Minimum confidence: 0.65
- Max lot cap: 1.0

AI/agents cannot bypass these limits.

## Run
```bash
cd forex-agent-os
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/docs` for the interactive API.

## Test
```bash
pytest -q
```

## Next milestones
1. Real MT5 demo-account connection and symbol metadata/tick-value lot sizing
2. Live candle/tick ingestion
3. Indicator pipeline (EMA/RSI/MACD/ADX/ATR/Bollinger)
4. Market Regime Agent
5. Liquidity / breakout agent
6. News & economic-calendar risk agent
7. Correlation / exposure guardian
8. Trailing-stop manager
9. Backtest + walk-forward engine
10. PostgreSQL trade/audit ledger
11. Web dashboard
12. LLM Critic/Supervisor with deterministic execution guardrails

## Safety
Live trading is intentionally disabled. Do not enable live execution before backtest, paper trading, forward testing, broker-specific sizing validation, slippage/spread checks and manual review.
