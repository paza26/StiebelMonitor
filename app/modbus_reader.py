"""Modbus TCP client wrapper for Stiebel Eltron heat pump."""

from __future__ import annotations

import ctypes
import logging
from typing import Any

from pymodbus.client import ModbusTcpClient

from app.config import AppConfig, RegisterConfig, StatusConfig

logger = logging.getLogger(__name__)


class ModbusReader:
    """Reads holding registers from a Stiebel Eltron heat pump via Modbus TCP."""

    def __init__(self, config: AppConfig) -> None:
        self._cfg = config.modbus
        self._registers = config.registers
        self._status_cfg = config.status
        self._client: ModbusTcpClient | None = None

    # ── Connection ──────────────────────────────────────────────────────

    def connect(self) -> bool:
        self._client = ModbusTcpClient(
            host=self._cfg.host,
            port=self._cfg.port,
            timeout=self._cfg.timeout,
        )
        ok = self._client.connect()
        if ok:
            logger.info("Modbus connected to %s:%s", self._cfg.host, self._cfg.port)
        else:
            logger.error("Modbus connection FAILED to %s:%s", self._cfg.host, self._cfg.port)
        return ok

    def disconnect(self) -> None:
        if self._client is not None:
            self._client.close()
            logger.info("Modbus disconnected")

    # ── Reading helpers ─────────────────────────────────────────────────

    # Stiebel Eltron "not available" sentinel value (0x8000)
    _NA_VALUE = 0x8000

    @staticmethod
    def _convert_value(raw: int, reg: RegisterConfig) -> float:
        """Apply data-type conversion and scale factor."""
        if reg.data_type == "int16":
            raw = ctypes.c_int16(raw).value  # unsigned → signed
        return round(raw * reg.scale, 4)

    def _read_single(
        self, address: int, unit: int, function_code: int = 4
    ) -> int | None:
        """Read a single register using the specified function code.

        Returns the raw value, or None if the read failed or the Stiebel
        'not available' sentinel (0x8000) was returned.
        """
        if self._client is None:
            return None

        if function_code == 4:
            result = self._client.read_input_registers(
                address=address, count=1, slave=unit
            )
        else:
            result = self._client.read_holding_registers(
                address=address, count=1, slave=unit
            )

        if result.isError():
            logger.warning(
                "Modbus FC%02d read error at address %d: %s",
                function_code,
                address,
                result,
            )
            return None

        raw = result.registers[0]
        if raw == self._NA_VALUE:
            logger.debug("Address %d returned NA sentinel (0x8000)", address)
            return None
        return raw

    # ── Public API ──────────────────────────────────────────────────────

    def read_registers(self) -> dict[str, Any]:
        """Read all configured registers. Returns {tag: scaled_value, …}."""
        values: dict[str, Any] = {}
        for reg in self._registers:
            raw = self._read_single(reg.address, self._cfg.unit_id, reg.function_code)
            if raw is not None:
                values[reg.tag] = self._convert_value(raw, reg)
            else:
                values[reg.tag] = None
        return values

    def read_status(self) -> str:
        """Read the status register and return the mode key string."""
        raw = self._read_single(
            self._status_cfg.register,
            self._cfg.unit_id,
            self._status_cfg.function_code,
        )
        if raw is None:
            return "standby"
        mode_key, _ = self._status_cfg.resolve_mode(raw)
        return mode_key
