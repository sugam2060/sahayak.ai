from fastapi import APIRouter
from services.api_gateway.routers.ticket.create import router as create_router
from services.api_gateway.routers.ticket.read import router as read_router
from services.api_gateway.routers.ticket.update import router as update_router

router = APIRouter()
router.include_router(create_router)
router.include_router(read_router)
router.include_router(update_router)

__all__ = ["router"]
