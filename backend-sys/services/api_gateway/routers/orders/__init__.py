from fastapi import APIRouter
from services.api_gateway.routers.orders.create import router as create_router
from services.api_gateway.routers.orders.read import router as read_router
from services.api_gateway.routers.orders.update import router as update_router
from services.api_gateway.routers.orders.track import router as track_router

router = APIRouter()
router.include_router(create_router)
router.include_router(read_router)
router.include_router(update_router)
router.include_router(track_router)

