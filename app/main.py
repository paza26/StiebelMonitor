"""FastAPI application — REST API + static file serving for StiebelMonitor."""

from __future__ import annotations

import logging
import os
import threading
from collections import deque
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import AppConfig, load_config
from app.database import (
    get_latest_readings,
    get_latest_status,
    get_readings,
    get_status_history,
    init_db,
)
from app.modbus_reader import ModbusReader
from app.scheduler import start_scheduler, stop_scheduler, trigger_poll

logger = logging.getLogger(__name__)

# ── In-memory log buffer for the web console ───────────────────────────────
_log_buffer: deque = deque(maxlen=500)
_log_lock = threading.Lock()
_log_counter: int = 0


class _WebLogHandler(logging.Handler):
    """Captures app log records into the in-memory buffer for the web console."""

    _INCLUDE_PREFIXES = ("app.", "apscheduler.")

    def emit(self, record: logging.LogRecord) -> None:
        global _log_counter
        if not any(record.name.startswith(p) for p in self._INCLUDE_PREFIXES):
            return
        try:
            with _log_lock:
                _log_counter += 1
                _log_buffer.append(
                    {
                        "id": _log_counter,
                        "ts": datetime.fromtimestamp(
                            record.created, tz=timezone.utc
                        ).isoformat(),
                        "level": record.levelname,
                        "logger": (
                            record.name
                            .replace("app.", "")
                            .replace("apscheduler.executors.", "aps.")
                            .replace("apscheduler.", "aps.")
                        ),
                        "msg": record.getMessage(),
                    }
                )
        except Exception:
            pass


# ── Globals set during startup ──────────────────────────────────────────────
_config: AppConfig | None = None
_reader: ModbusReader | None = None

CONFIG_PATH = os.environ.get("STIEBEL_CONFIG", "config.yaml")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    global _config, _reader

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    # Attach web-console log handler
    logging.getLogger().addHandler(_WebLogHandler())

    # Load configuration
    _config = load_config(CONFIG_PATH)
    logger.info("Configuration loaded from %s", CONFIG_PATH)

    # Initialise database (creates tables)
    init_db(_config)

    # Connect Modbus reader
    _reader = ModbusReader(_config)
    connected = _reader.connect()
    if not connected:
        logger.warning(
            "Modbus not reachable — polling will retry on each cycle"
        )

    # Start background polling
    start_scheduler(_reader, _config)

    yield

    # Shutdown
    stop_scheduler()
    if _reader is not None:
        _reader.disconnect()


app = FastAPI(
    title="Stiebel Monitor",
    description="Monitor per pompa di calore Stiebel Eltron HPA-O 6 CS Plus",
    version="1.0.0",
    lifespan=lifespan,
)


# ── API routes ──────────────────────────────────────────────────────────────


@app.get("/api/tags")
def api_tags():
    """Return the list of all configured register tags with metadata."""
    if _config is None:
        return []
    return [
        {
            "tag": r.tag,
            "description": r.description,
            "unit": r.unit,
            "address": r.address,
            "category": r.category,
        }
        for r in _config.registers
    ]


@app.get("/api/readings")
def api_readings(
    tag: str | None = Query(None, description="Comma-separated tag names"),
    start: datetime | None = Query(None, description="Start datetime ISO-8601"),
    end: datetime | None = Query(None, description="End datetime ISO-8601"),
):
    """Return readings filtered by tag(s) and time range."""
    tags = [t.strip() for t in tag.split(",")] if tag else None
    return get_readings(tags, start, end)


@app.get("/api/readings/latest")
def api_latest_readings():
    """Return the most recent reading for every tag plus current machine status."""
    readings = get_latest_readings()
    status = get_latest_status()

    # Enrich status with label and color from config
    status_info = {"mode": "standby", "label": "Standby", "color": "transparent"}
    if _config and status:
        mode_key = status["mode"]
        mode_cfg = _config.status.modes.get(mode_key)
        if mode_cfg:
            status_info = {
                "mode": mode_key,
                "label": mode_cfg.label,
                "color": mode_cfg.color,
                "timestamp": status["timestamp"],
            }

    return {"readings": readings, "status": status_info}


@app.get("/api/logs")
def api_logs(after: int = Query(0, description="Return entries with id > after")):
    """Return buffered log entries. Never persisted — in-memory buffer only."""
    with _log_lock:
        return [e for e in _log_buffer if e["id"] > after]


@app.post("/api/poll")
def api_poll():
    """Trigger an immediate Modbus poll cycle in a background thread."""
    import threading
    threading.Thread(target=trigger_poll, daemon=True, name="manual-poll").start()
    return {"status": "triggered"}


@app.get("/api/status")
def api_status_history(
    start: datetime | None = Query(None),
    end: datetime | None = Query(None),
):
    """Return machine status history for the given time range, enriched with colors."""
    history = get_status_history(start, end)
    if _config is None:
        return history
    enriched = []
    for entry in history:
        mode_key = entry["mode"]
        mode_cfg = _config.status.modes.get(mode_key)
        enriched.append(
            {
                **entry,
                "label": mode_cfg.label if mode_cfg else mode_key,
                "color": mode_cfg.color if mode_cfg else "transparent",
            }
        )
    return enriched


@app.get("/api/config/modes")
def api_config_modes():
    """Return all available operating modes with labels and colors."""
    if _config is None:
        return {}
    return {
        key: {"label": m.label, "color": m.color}
        for key, m in _config.status.modes.items()
    }


# ── Static files (SPA) ─────────────────────────────────────────────────────

STATIC_DIR = Path(__file__).parent / "static"


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
