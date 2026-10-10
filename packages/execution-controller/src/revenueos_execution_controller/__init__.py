"""RevenueOS execution controller (V1A-3).

ExecutionController is the SOLE external side-effect authority.
Every external effect (task dispatch, outbox flush, adapter call) passes
through it. Direct writes to external systems from elsewhere in the codebase
are not permitted by package convention — enforced by review, not runtime.
"""
__version__ = "0.1.0"
