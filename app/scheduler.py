"""Background scheduler that polls Modbus registers and stores readings."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler

from app.config import AppConfig
from app.database import insert_readings, insert_status
from app.modbus_reader import ModbusReader

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None
_reader: ModbusReader | None = None
_config: AppConfig | None = None


def trigger_poll() -> None:
    """Run the polling cycle immediately (called from the API endpoint)."""
    global _reader, _config
    if _reader is not None and _config is not None:
        _poll_job(_reader, _config)
    else:
        logger.warning("trigger_poll called before scheduler was started")


def _poll_job(reader: ModbusReader, config: AppConfig) -> None:
    """Single polling cycle: read all registers + status, write to DB."""
    now = datetime.now(timezone.utc)
    try:
        values = reader.read_registers()
        mode = reader.read_status()
    except Exception:
        logger.exception("Modbus poll failed")
        return

    # Build reading records
    tag_to_reg = {r.tag: r for r in config.registers}
    readings = []
    for tag, value in values.items():
        if value is not None:
            readings.append(
                {
                    "tag": tag,
                    "register_address": tag_to_reg[tag].address,
                    "value": value,
                    "timestamp": now,
                }
            )

    try:
        if readings:
            insert_readings(readings)
        insert_status(mode, timestamp=now)
        logger.info(
            "Poll OK — %d readings stored, mode=%s", len(readings), mode
        )
    except Exception:
        logger.exception("Failed to write poll results to database")


def start_scheduler(reader: ModbusReader, config: AppConfig) -> None:
    """Start the background polling scheduler."""
    global _scheduler, _reader, _config
    _reader = reader
    _config = config
    _scheduler = BackgroundScheduler(daemon=True)
    _scheduler.add_job(
        _poll_job,
        "interval",
        seconds=config.polling.interval_seconds,
        args=[reader, config],
        id="modbus_poll",
        max_instances=1,
        next_run_time=datetime.now(timezone.utc),  # run immediately on start
    )
    _scheduler.start()
    logger.info(
        "Scheduler started — polling every %ds", config.polling.interval_seconds
    )


def stop_scheduler() -> None:
    """Gracefully stop the scheduler."""
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
        _scheduler = None
