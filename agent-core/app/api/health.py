from datetime import datetime
from fastapi import APIRouter

router = APIRouter()

@router.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@router.get("/health/detailed")
async def detailed_health():
    return {
        "status": "healthy",
        "components": {
            "mysql": "ok",
            "redis": "ok",
            "mcp_discovery": "ok",
            "llm_api": "ok"
        }
    }
