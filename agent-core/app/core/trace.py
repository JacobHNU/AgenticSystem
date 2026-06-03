from contextvars import ContextVar
import uuid

_trace_id: ContextVar[str] = ContextVar('trace_id', default='')


class TraceContext:
    """trace_id full-chain injection via ContextVar"""

    @staticmethod
    def get_trace_id() -> str:
        return _trace_id.get() or ''

    @staticmethod
    def set_trace_id(trace_id: str):
        _trace_id.set(trace_id)

    @staticmethod
    def generate_trace_id() -> str:
        return uuid.uuid4().hex[:16]

    @staticmethod
    def get_or_create() -> str:
        tid = _trace_id.get()
        if not tid:
            tid = TraceContext.generate_trace_id()
            _trace_id.set(tid)
        return tid
