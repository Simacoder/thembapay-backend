import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import audit, payments, ocr, qr, bank_integration
from app.engines.ocr_extract import PaddleOCRBackend


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Force the PaddleOCR model to download/load now, at startup, instead of
    # on the first request. Loading is blocking and can take a couple of
    # minutes on a cold cache (model weights download from paddleocr's CDN),
    # so run it in a thread to avoid blocking the event loop during startup.
    await asyncio.to_thread(PaddleOCRBackend._get_engine)
    yield
    # (nothing to clean up on shutdown)


app = FastAPI(
    title="ThembaPay API",
    description="Pre-authorization trust-scoring and route recommendation for cross-border payments. "
                 "MVP built for EDHE Studentpreneurs Indaba FinTech Hackathon, empowered by Absa.",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS: allows the frontend to call this API even if it's ever hosted on a
# different origin than the backend. allow_origins=["*"] is fine for a
# hackathon demo with no real user data.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include all routers
app.include_router(payments.router)
app.include_router(audit.router)
app.include_router(ocr.router)
app.include_router(qr.router)
app.include_router(bank_integration.router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "thembapay-api"}


# Serve the demo frontend (static/index.html, style.css, app.js) at the
# root path. Mounted AFTER the API routes above, so /payments/... and
# /audit/... are matched first - only paths that don't match an API route
# fall through to serving static files.
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="frontend")