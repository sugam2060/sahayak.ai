from fastapi import APIRouter
from services.api_gateway.routers.ai_config.handlers import router as config_router

router = APIRouter(tags=["AI Configuration"])
router.include_router(config_router)
