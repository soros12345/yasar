from fastapi import FastAPI
from .agents import EnsembleEngine
from .broker import DemoBroker
from .models import AccountState, MarketSnapshot
from .risk import RiskEngine

app = FastAPI(title="Forex Agent OS", version="0.1.0")
ensemble = EnsembleEngine()
risk_engine = RiskEngine()
broker = DemoBroker()


@app.get("/health")
def health():
    return {"status": "ok", "mode": "DEMO", "live_trading": False}


@app.post("/analyze")
def analyze(market: MarketSnapshot, account: AccountState):
    signals, intent = ensemble.decide(market)
    if intent is None:
        return {"signals": [s.model_dump() for s in signals], "intent": None, "risk": None, "execution": None}

    risk = risk_engine.evaluate(intent, market, account)
    execution = broker.execute(intent, risk)
    return {
        "signals": [s.model_dump() for s in signals],
        "intent": intent.model_dump(),
        "risk": risk.model_dump(),
        "execution": execution.__dict__,
    }


@app.post("/kill-switch/{enabled}")
def kill_switch(enabled: bool):
    risk_engine.kill_switch = enabled
    return {"kill_switch": risk_engine.kill_switch}
