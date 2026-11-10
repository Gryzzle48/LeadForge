import logging
import time
from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text
from .config import CORS_ORIGINS, MAX_BODY_SIZE
from .database import init_db, async_session
from .routers import search, leads, export
from .auth import verify_api_key, client_ip_key

logger = logging.getLogger(__name__)

limiter = Limiter(key_func=client_ip_key)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    try:
        async with async_session() as db:
            await db.execute(text(
                "UPDATE campaigns SET status = 'failed', "
                "status_detail = 'Search was interrupted when the server restarted. Run it again.' "
                "WHERE status IN ('pending', 'running')"
            ))
            await db.commit()
    except Exception as exc:
        logger.warning(f"Could not mark interrupted searches: {exc}")
    yield

app = FastAPI(title="LeadForge", lifespan=lifespan)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

origins = [o.strip() for o in CORS_ORIGINS.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if origins != ["*"] else ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def limit_body_size(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > MAX_BODY_SIZE:
        return JSONResponse(status_code=413, content={"detail": "Request body too large"})
    return await call_next(request)

@app.middleware("http")
async def audit_logging(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    elapsed = time.time() - start
    if request.url.path.startswith("/api/") and request.url.path != "/api/health":
        try:
            async with async_session() as db:
                from .models.audit_log import AuditLog
                log = AuditLog(
                    method=request.method,
                    path=request.url.path,
                    status_code=response.status_code,
                    client_ip=request.client.host if request.client else None,
                    user_agent=request.headers.get("user-agent"),
                    detail=f"{elapsed:.3f}s",
                )
                db.add(log)
                await db.commit()
        except Exception as e:
            logger.warning(f"Audit log write failed: {e}")
    return response

app.include_router(search.router, prefix="/api", tags=["search"], dependencies=[Depends(verify_api_key)])
app.include_router(leads.router, prefix="/api", tags=["leads"], dependencies=[Depends(verify_api_key)])
app.include_router(export.router, prefix="/api", tags=["export"], dependencies=[Depends(verify_api_key)])

@app.get("/api/health")
async def health():
    db_ok = False
    try:
        async with async_session() as session:
            await session.execute(text("SELECT 1"))
        db_ok = True
    except Exception as e:
        logger.warning(f"Health check DB failure: {e}")
    return {"status": "ok" if db_ok else "degraded", "database": "connected" if db_ok else "disconnected"}
