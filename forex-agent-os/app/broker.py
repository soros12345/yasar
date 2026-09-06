from dataclasses import dataclass
from .models import RiskDecision, TradeIntent


@dataclass
class ExecutionResult:
    accepted: bool
    mode: str
    order_id: str | None
    message: str


class DemoBroker:
    """Paper-trading executor. It never sends real-money orders."""

    def execute(self, intent: TradeIntent, risk: RiskDecision) -> ExecutionResult:
        if not risk.approved:
            return ExecutionResult(False, "DEMO", None, f"Rejected: {risk.reason}")
        order_id = f"DEMO-{intent.symbol}-{intent.side.value}"
        return ExecutionResult(True, "DEMO", order_id, f"Paper order accepted, lot={risk.lot_size}")


class MT5Broker:
    """Live/demo MT5 adapter placeholder. Disabled until explicit broker credentials/config are provided."""

    def __init__(self, enabled: bool = False):
        self.enabled = enabled

    def execute(self, intent: TradeIntent, risk: RiskDecision) -> ExecutionResult:
        if not self.enabled:
            return ExecutionResult(False, "MT5_DISABLED", None, "MT5 execution is disabled by default")
        raise NotImplementedError("Wire MetaTrader5 package, symbol metadata, credentials and order_send before enabling.")
