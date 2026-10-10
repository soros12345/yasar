"""Decision model adapter stubs (V1A-3).

The decision model drives ExecutionController decisions. It is not implemented
in V1A-3; this package reserves the interface and returns UNVERIFIED for all
queries.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class DecisionStub:
    decision_type: str
    state: str = "UNVERIFIED"
    recommendation: str | None = None


def decide_stub(decision_type: str, context: dict) -> DecisionStub:
    """Stub decision. Real decision evaluation is deferred."""
    return DecisionStub(decision_type=decision_type, state="UNVERIFIED", recommendation=None)
