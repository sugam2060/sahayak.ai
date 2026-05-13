from uuid import UUID
from typing import Optional, Any, Dict
from shared.database.engine import SessionLocal
from shared.database.schema import AuditLog, AuditEventType

async def log_audit_event(
    event_type: AuditEventType,
    user_id: Optional[UUID] = None,
    organization_id: Optional[UUID] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None
):
    """
    Utility to log security events to the audit_logs table.
    """
    try:
        async with SessionLocal() as session:
            audit_entry = AuditLog(
                user_id=user_id,
                organization_id=organization_id,
                event_type=event_type,
                ip_address=ip_address,
                user_agent=user_agent,
                details=details
            )
            session.add(audit_entry)
            await session.commit()
    except Exception as e:
        # We don't want audit logging failures to crash the main auth flow,
        # but we definitely want to see them in the logs.
        print(f"FAILED TO WRITE AUDIT LOG: {str(e)}")
