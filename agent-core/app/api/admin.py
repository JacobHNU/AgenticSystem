from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import APIKeyHeader

router = APIRouter(prefix="/api/v1/admin")

api_key_header = APIKeyHeader(name="X-Admin-Key")

async def verify_admin_key(key: str = Depends(api_key_header)):
    from app.core.config import load_config
    config = load_config("config/settings.yaml")
    if key != config.get("app", {}).get("admin_api_key", ""):
        raise HTTPException(status_code=403, detail="Invalid admin API key")

@router.post("/reload/skills", dependencies=[Depends(verify_admin_key)])
async def reload_skills():
    return {"success": True, "count": 0}

@router.post("/reload/workflows", dependencies=[Depends(verify_admin_key)])
async def reload_workflows():
    return {"success": True, "count": 0}

@router.post("/reload/all", dependencies=[Depends(verify_admin_key)])
async def reload_all():
    return {"skills": {"success": True, "count": 0}, "workflows": {"success": True, "count": 0}}
