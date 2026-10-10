from dataclasses import dataclass
from .models import AccountState, MarketSnapshot, RiskDecision, TradeIntent


@dataclass(frozen=True)
class RiskLimits:
    risk_per_trade_pct: float = 0.005
    max_daily_loss_pct: float = 0.02
    max_drawdown_pct: float = 0.10
    max_open_positions: int = 3
    max_spread: float = 0.00030
    min_confidence: float = 0.65
    max_lot: float = 1.0


class RiskEngine:
    def __init__(self, limits: RiskLimits | None = None):
        self.limits = limits or RiskLimits()
        self.kill_switch = False

    def evaluate(self, intent: TradeIntent, market: MarketSnapshot, account: AccountState) -> RiskDecision:
        l = self.limits
        if self.kill_switch:
            return RiskDecision(approved=False, reason="kill_switch")
        if intent.confidence < l.min_confidence:
            return RiskDecision(approved=False, reason="low_confidence")
        if account.open_positions >= l.max_open_positions:
            return RiskDecision(approved=False, reason="max_open_positions")
        if market.spread > l.max_spread:
            return RiskDecision(approved=False, reason="spread_too_wide")
        if account.daily_pnl <= -(account.balance * l.max_daily_loss_pct):
            return RiskDecision(approved=False, reason="daily_loss_limit")
        drawdown = max(0.0, (account.peak_equity - account.equity) / account.peak_equity)
        if drawdown >= l.max_drawdown_pct:
            return RiskDecision(approved=False, reason="max_drawdown")

        stop_distance = abs(intent.entry - intent.stop_loss)
        if stop_distance <= 0:
            return RiskDecision(approved=False, reason="invalid_stop")

        risk_amount = account.equity * l.risk_per_trade_pct
        # Generic sizing placeholder. Broker symbol metadata will replace this with tick-value sizing.
        raw_lot = risk_amount / max(stop_distance * 100000.0, 1.0)
        lot = min(max(round(raw_lot, 2), 0.01), l.max_lot)
        return RiskDecision(approved=True, reason="approved", risk_amount=round(risk_amount, 2), lot_size=lot)
