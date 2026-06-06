from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from pydantic import BaseModel, Field
from typing import Optional

from shared.database.schema.organization_config_ai import OrganizationConfigAI
from services.api_gateway.routers.auth_routers.me import get_current_user
from shared.utils import get_db

router = APIRouter(prefix="/api/ai-config")

class AIConfigUpdate(BaseModel):
    ai_enabled: bool
    auto_order_enabled: bool
    system_prompt: Optional[str] = Field("", max_length=500)
    knowledge_base: Optional[str] = ""

@router.get("")
async def get_ai_config(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    try:
        org_id = UUID(current_user["organization_id"])
        
        # Query existing config
        stmt = select(OrganizationConfigAI).where(OrganizationConfigAI.organization_id == org_id)
        res = await db.execute(stmt)
        config_rec = res.scalar_one_or_none()
        
        if not config_rec:
            # Create a default one if not exists
            config_rec = OrganizationConfigAI(
                organization_id=org_id,
                ai_enabled=True,
                auto_order_enabled=False,
                system_prompt="You are a helpful assistant.",
                knowledge_base=""
            )
            db.add(config_rec)
            await db.commit()
            await db.refresh(config_rec)
            
        return {
            "success": True,
            "config": {
                "id": str(config_rec.id),
                "organization_id": str(config_rec.organization_id),
                "ai_enabled": config_rec.ai_enabled,
                "auto_order_enabled": config_rec.auto_order_enabled,
                "system_prompt": config_rec.system_prompt or "",
                "knowledge_base": config_rec.knowledge_base or "",
                "created_at": config_rec.created_at.isoformat() if config_rec.created_at else None,
                "updated_at": config_rec.updated_at.isoformat() if config_rec.updated_at else None,
            }
        }
    except Exception as e:
        print(f"Error fetching AI configuration: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch AI configuration."
        )

@router.put("")
async def update_ai_config(
    req: AIConfigUpdate,
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    try:
        org_id = UUID(current_user["organization_id"])
        
        # Query existing config
        stmt = select(OrganizationConfigAI).where(OrganizationConfigAI.organization_id == org_id)
        res = await db.execute(stmt)
        config_rec = res.scalar_one_or_none()
        
        if not config_rec:
            config_rec = OrganizationConfigAI(
                organization_id=org_id,
                ai_enabled=req.ai_enabled,
                auto_order_enabled=req.auto_order_enabled,
                system_prompt=req.system_prompt,
                knowledge_base=req.knowledge_base
            )
            db.add(config_rec)
        else:
            config_rec.ai_enabled = req.ai_enabled
            config_rec.auto_order_enabled = req.auto_order_enabled
            config_rec.system_prompt = req.system_prompt
            config_rec.knowledge_base = req.knowledge_base
            
        await db.commit()
        await db.refresh(config_rec)
        
        # Trigger RAG knowledge base re-indexing if knowledge_base was provided
        if req.knowledge_base:
            import asyncio
            import importlib
            try:
                rag_indexer = importlib.import_module("services.chatai-service.ai.tools.rag.rag_indexer")
                asyncio.create_task(rag_indexer.upsert_knowledge_base(
                    organization_id=str(org_id),
                    organization_name=current_user.get("organization_name", ""),
                    knowledge_text=req.knowledge_base
                ))
            except Exception as rag_err:
                print(f"RAG indexing task creation failed (non-critical): {rag_err}")

        return {
            "success": True,
            "config": {
                "id": str(config_rec.id),
                "organization_id": str(config_rec.organization_id),
                "ai_enabled": config_rec.ai_enabled,
                "auto_order_enabled": config_rec.auto_order_enabled,
                "system_prompt": config_rec.system_prompt or "",
                "knowledge_base": config_rec.knowledge_base or "",
                "created_at": config_rec.created_at.isoformat() if config_rec.created_at else None,
                "updated_at": config_rec.updated_at.isoformat() if config_rec.updated_at else None,
            }
        }
    except Exception as e:
        await db.rollback()
        print(f"Error updating AI configuration: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update AI configuration."
        )
