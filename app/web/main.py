import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.config import ROOT, load_config
from app.execution.broker import OfflinePaperBroker
from app.market.data import CsvProvider
from app.storage.db import Store

PAGES = {
    "overview": "Overview",
    "market-regime": "Market Regime",
    "heatmap": "Sector / Industry Heatmap",
    "scanner": "Stock Scanner",
    "watchlist": "Watchlist",
    "signals": "Signals",
    "positions": "Active Positions",
    "strategies": "Intraday / Swing Strategies",
    "backtest": "Backtest Lab",
    "journal": "Order Journal",
    "health": "Risk & Health",
    "settings": "Settings",
    "logs": "Logs",
}


def create_app(runtime: Path | None = None) -> FastAPI:
    config = load_config()
    directory = runtime or ROOT / "runtime"
    templates = Jinja2Templates(directory=str(ROOT / "app/web/templates"))

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        directory.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(directory / "app.log", maxBytes=1_000_000, backupCount=3)
        logger = logging.getLogger(f"autotrade.{id(app)}")
        logger.setLevel(logging.INFO)
        logger.addHandler(handler)
        app.state.store = Store(directory / "autotrade.db")
        app.state.broker = OfflinePaperBroker(app.state.store)
        app.state.broker.connect()
        app.state.provider = CsvProvider(ROOT / "samples/daily.csv")
        app.state.session_enabled = False
        logger.info(json.dumps({"event": "startup", "paper_only": True, "enabled": False}))
        try:
            yield
        finally:
            logger.info(json.dumps({"event": "shutdown"}))
            handler.close()
            logger.removeHandler(handler)

    app = FastAPI(title="AutoTrade V1.0 — PAPER ONLY", lifespan=lifespan)
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "testserver"]
    )

    @app.get("/api/health")
    def health(request: Request) -> dict[str, object]:
        return {
            "paper_only": True,
            "session_enabled": False,
            "broker": request.app.state.broker.health(),
            "data": request.app.state.provider.quality(),
        }

    @app.post("/api/session/enable")
    def enable() -> None:
        raise HTTPException(
            409, "Blocked: risk engine, current data and protection not implemented"
        )

    @app.get("/", response_class=HTMLResponse)
    @app.get("/page/{page}", response_class=HTMLResponse)
    def page_view(request: Request, page: str = "overview") -> HTMLResponse:
        if page not in PAGES:
            raise HTTPException(404, "Unknown page")
        now = datetime.now(UTC)
        store = request.app.state.store
        data: object = {"status": "Not implemented in milestone 1; entries blocked"}
        if page == "overview":
            data = request.app.state.broker.get_account()
        elif page == "health":
            data = health(request)
        elif page == "settings":
            data = config
        elif page in {"journal", "positions", "logs"}:
            data = store.rows(
                {"journal": "orders", "positions": "positions", "logs": "audit"}[page]
            )
        elif page == "strategies":
            data = {"intraday": "OFF — not implemented", "swing": "OFF — not implemented"}
        return templates.TemplateResponse(
            request=request,
            name="dashboard.html",
            context={
                "pages": PAGES,
                "page": page,
                "title": PAGES[page],
                "data": json.dumps(data, indent=2),
                "et": now.astimezone(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M:%S %Z"),
                "sgt": now.astimezone(ZoneInfo(config["ui_timezone"])).strftime(
                    "%Y-%m-%d %H:%M:%S %Z"
                ),
                "quality": request.app.state.provider.quality(),
            },
        )

    return app


app = create_app()
