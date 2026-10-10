from enum import Enum
from pydantic import BaseModel, Field


class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class MarketSnapshot(BaseModel):
    symbol: str
    bid: float
    ask: float
    atr: float = Field(gt=0)
    ema_fast: float
    ema_slow: float
    rsi: float = Field(ge=0, le=100)
    volatility_pct: float = Field(ge=0)

    @property
    def spread(self) -> float:
        return self.ask - self.bid


class AgentSignal(BaseModel):
    agent: str
    side: Side
    confidence: float = Field(ge=0, le=1)
    reason: str


class TradeIntent(BaseModel):
    symbol: str
    side: Side
    confidence: float = Field(ge=0, le=1)
    entry: float
    stop_loss: float
    take_profit: float


class AccountState(BaseModel):
    balance: float = Field(gt=0)
    equity: float = Field(gt=0)
    daily_pnl: float = 0.0
    peak_equity: float = Field(gt=0)
    open_positions: int = Field(ge=0)


class RiskDecision(BaseModel):
    approved: bool
    reason: str
    risk_amount: float = 0.0
    lot_size: float = 0.0
