"""RevenueOS event backbone (V1A-3).

Append-only event log with correlation/causation IDs, plus an outbox pattern
that flushes deterministic events into Valkey/PostgreSQL. Replay is by
correlation id; never blind retry.
"""
__version__ = "0.1.0"
