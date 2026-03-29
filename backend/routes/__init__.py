from __future__ import annotations

from routes.stocks import router as stocks_router
from routes.portfolio import router as portfolio_router
from routes.screener import router as screener_router

__all__ = ["stocks_router", "portfolio_router", "screener_router"]
