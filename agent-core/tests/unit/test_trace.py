from app.core.trace import TraceContext

def test_set_and_get_trace_id():
    TraceContext.set_trace_id("abc123")
    assert TraceContext.get_trace_id() == "abc123"

def test_generate_trace_id():
    tid = TraceContext.generate_trace_id()
    assert len(tid) == 16
    assert tid.isalnum()

def test_get_or_create_generates_when_empty():
    TraceContext.set_trace_id("")
    tid = TraceContext.get_or_create()
    assert len(tid) == 16

def test_get_or_create_returns_existing():
    TraceContext.set_trace_id("existing")
    assert TraceContext.get_or_create() == "existing"
