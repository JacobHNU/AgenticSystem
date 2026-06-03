import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.trace import TraceContext
from app.core.exceptions import AgentCoreError
from app.api.health import router as health_router
from app.api.agent import router as agent_router
from app.api.admin import router as admin_router
from app.api.ws import router as ws_router


class TraceMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        trace_id = request.headers.get("X-Trace-Id") or TraceContext.generate_trace_id()
        TraceContext.set_trace_id(trace_id)
        response = await call_next(request)
        response.headers["X-Trace-Id"] = trace_id
        return response


def create_app() -> FastAPI:
    app = FastAPI(title="Agent Core", version="1.0.0")

    # Middleware
    app.add_middleware(TraceMiddleware)

    # Exception handler
    @app.exception_handler(AgentCoreError)
    async def handle_agent_error(request: Request, exc: AgentCoreError):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.error_type,
                "message": exc.message,
                "details": exc.details,
                "trace_id": TraceContext.get_trace_id()
            }
        )

    # Routers
    app.include_router(health_router)
    app.include_router(agent_router)
    app.include_router(admin_router)
    app.include_router(ws_router)

    return app


app = create_app()
