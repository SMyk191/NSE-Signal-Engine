from __future__ import annotations

"""
NSE Signal Engine - FastAPI Application Entry Point

Run with: uvicorn main:app --reload --port 8000
"""

import logging
import sys
from contextlib import asynccontextmanager
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import init_db
from routes.stocks import router as stocks_router
from routes.portfolio import router as portfolio_router
from routes.screener import router as screener_router
from routes.auth import router as auth_router
from services.auth import init_auth_db

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("nse_signal_engine")


# ---------------------------------------------------------------------------
# Lifespan: startup & shutdown hooks
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Runs on startup before serving requests, and on shutdown after."""
    # --- Startup ---
    logger.info("Initializing NSE Signal Engine...")

    # Initialize SQLite database tables
    await init_db()
    logger.info("Database initialized.")

    # Initialize auth database
    init_auth_db()
    logger.info("Auth database initialized.")

    # Optional: start APScheduler for daily pre-market data refresh
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from services.data_fetcher import fetch_bulk_nifty50

        scheduler = AsyncIOScheduler()

        async def premarket_refresh():
            logger.info("Running pre-market data refresh...")
            try:
                await fetch_bulk_nifty50()
                logger.info("Pre-market refresh complete.")
            except Exception as e:
                logger.error("Pre-market refresh failed: %s", e)

        # Schedule at 8:45 AM IST (3:15 AM UTC) on weekdays
        scheduler.add_job(
            premarket_refresh,
            "cron",
            day_of_week="mon-fri",
            hour=3,
            minute=15,
            timezone="UTC",
        )
        scheduler.start()
        logger.info("APScheduler started: pre-market refresh scheduled at 8:45 AM IST on weekdays.")
    except ImportError:
        logger.info("APScheduler not installed. Skipping scheduled data refresh. "
                     "Install with: pip install apscheduler")

    yield

    # --- Shutdown ---
    logger.info("Shutting down NSE Signal Engine.")


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(
    title="NSE Signal Engine API",
    description=(
        "Comprehensive stock analysis engine for NIFTY 50 stocks. "
        "Provides technical indicators, composite signals, sentiment analysis, "
        "portfolio risk management, screening, and backtesting."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS middleware (allow all origins for development)
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Include routers
# ---------------------------------------------------------------------------
app.include_router(auth_router)
app.include_router(stocks_router)
app.include_router(portfolio_router)
app.include_router(screener_router)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/api/health", tags=["health"])
async def health_check():
    """
    GET /api/health
    Health check endpoint.
    """
    return {
        "status": "healthy",
        "service": "NSE Signal Engine API",
        "version": "1.0.0",
    }


# ---------------------------------------------------------------------------
# Run with: uvicorn main:app --reload --port 8000
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
