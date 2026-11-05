import asyncio
from typing import Any
from app.database import AsyncSessionLocal
from app.models import AuditLog
from app.logger import logger

async def _persist_audit_log(
    action: str,
    status: str,
    client_id: int | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    try:
        async with AsyncSessionLocal() as session:
            entry = AuditLog(
                client_id=client_id,
                action=action,
                status=status,
                ip_address=ip_address,
                user_agent=user_agent,
                details=details or {},
            )
            session.add(entry)
            await session.commit()
    except Exception as exc:
        logger.error(f"Audit log write failed: {exc}", exc_info=True)

def dispatch_audit(action: str, status: str, **kwargs: Any) -> None:
    """Non-blocking fire-and-forget audit entry."""
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_persist_audit_log(action, status, **kwargs))
    except RuntimeError:
        pass