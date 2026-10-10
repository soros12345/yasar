"""Execution authority contract schemas (V1A-3).

Deny-by-default: every execution intent must carry a correlation_id and
pass Casbin + SpendGuard stub + approval stub. UNVERIFIED states are
explicit in the response so consumers know what is still pending.
"""
from datetime import datetime

from pydantic import BaseModel, Field


class ExecutionPlanRequest(BaseModel):
    intent: str = Field(min_length=1, max_length=64)
    correlation_id: str = Field(min_length=1, max_length=36)
    payload: dict = Field(default_factory=dict)


class ExecutionRunOut(BaseModel):
    id: str
    tenant_id: str
    correlation_id: str
    intent: str
    status: str
    decision_json: dict | None = None
    capability_state: str
    spend_guard_state: str
    policy_state: str
    lock_state: str
    risk_state: str
    approval_state: str
    error_detail: str | None = None
    created_at: datetime
    updated_at: datetime


class ExecutionEventOut(BaseModel):
    id: str
    tenant_id: str
    correlation_id: str
    causation_id: str | None = None
    event_type: str
    payload_json: dict | None = None
    occurred_at: datetime


class OutboxEventOut(BaseModel):
    id: str
    tenant_id: str
    correlation_id: str
    destination: str
    payload_json: dict | None = None
    state: str
    attempts: int
    created_at: datetime
    dispatched_at: datetime | None = None


class ApprovalRequestOut(BaseModel):
    id: str
    tenant_id: str
    correlation_id: str
    request_type: str
    subject_json: dict | None = None
    status: str
    requested_by: str
    expires_at: datetime | None = None
    created_at: datetime


class WorkflowInstanceOut(BaseModel):
    id: str
    tenant_id: str
    correlation_id: str
    workflow_type: str
    status: str
    current_state: str
    verification_outcome: str
    attempt_count: int
    last_verify_at: datetime | None = None
    error_detail: str | None = None
    created_at: datetime
    updated_at: datetime


class VerifyRequest(BaseModel):
    outcome: str = Field(min_length=1, max_length=32)
    detail: str | None = None


# --------------------------------------------------------------------------
# V1A-4 execution adapters (enforced guards)
# --------------------------------------------------------------------------
class CapabilityOut(BaseModel):
    id: str
    provider_id: str
    capability_id: str
    verification_state: str
    enabled: bool
    scope_json: dict | None = None
    notes: str | None = None


class CapabilityCreateRequest(BaseModel):
    provider_id: str = Field(min_length=1, max_length=64)
    capability_id: str = Field(min_length=1, max_length=128)
    verification_state: str = Field(default="UNVERIFIED", max_length=32)
    enabled: bool = False
    scope: dict | None = None
    notes: str | None = None


class SpendBudgetOut(BaseModel):
    id: str
    tenant_id: str
    provider_id: str | None = None
    currency: str
    period: str
    limit_amount: str
    enabled: bool
    note: str | None = None


class SpendBudgetCreateRequest(BaseModel):
    currency: str = Field(min_length=3, max_length=3)
    limit_amount: str = Field(min_length=1, max_length=32)
    provider_id: str | None = Field(default=None, max_length=64)
    period: str = Field(default="MONTHLY", max_length=16)
    note: str | None = None


class ExecutionPolicyOut(BaseModel):
    id: str
    tenant_id: str
    intent: str
    effect: str
    requires_approval: bool
    enabled: bool
    note: str | None = None


class ExecutionPolicyCreateRequest(BaseModel):
    intent: str = Field(min_length=1, max_length=64)
    effect: str = Field(default="DENY", max_length=16)
    requires_approval: bool = False
    note: str | None = None


class AdapterOut(BaseModel):
    adapter_id: str
    capability_id: str
    enabled: bool
    registered: bool = True


class ApprovalDecisionRequest(BaseModel):
    note: str | None = Field(default=None, max_length=512)
