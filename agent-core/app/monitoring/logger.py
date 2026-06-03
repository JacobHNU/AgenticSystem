import logging
import json
from app.core.trace import TraceContext


class TraceFilter(logging.Filter):
    def filter(self, record):
        record.trace_id = TraceContext.get_trace_id()
        return True


def setup_logging(level: str = "INFO", format_type: str = "json"):
    handler = logging.StreamHandler()
    handler.addFilter(TraceFilter())

    if format_type == "json":
        formatter = logging.Formatter(
            '{"time":"%(asctime)s","level":"%(levelname)s",'
            '"trace_id":"%(trace_id)s","module":"%(module)s","message":"%(message)s"}'
        )
    else:
        formatter = logging.Formatter(
            '%(asctime)s [%(trace_id)s] %(levelname)s %(module)s: %(message)s'
        )

    handler.setFormatter(formatter)
    logger = logging.getLogger()
    logger.addHandler(handler)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
