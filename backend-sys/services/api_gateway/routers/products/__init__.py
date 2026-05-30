from fastapi import APIRouter
from services.api_gateway.routers.products.create import router as create_router
from services.api_gateway.routers.products.read import router as read_router
from services.api_gateway.routers.products.update import router as update_router
from services.api_gateway.routers.products.delete import router as delete_router

router = APIRouter(tags=["Product Management"])

# Include CRUD sub-routers
router.include_router(create_router)
router.include_router(read_router)
router.include_router(update_router)
router.include_router(delete_router)
