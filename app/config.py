"""Configuration loader and Pydantic models for StiebelMonitor."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, field_validator


class ModbusConfig(BaseModel):
    host: str
    port: int = 502
    unit_id: int = 1
    timeout: int = 5


class DatabaseConfig(BaseModel):
    host: str = "db"
    port: int = 5432
    name: str = "stiebel_monitor"
    user: str = "stiebel"
    password: str = "stiebel"

    @property
    def url(self) -> str:
        return (
            f"postgresql://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.name}"
        )


class PollingConfig(BaseModel):
    interval_seconds: int = 60


class RegisterConfig(BaseModel):
    address: int
    tag: str
    description: str
    unit: str = ""
    scale: float = 1.0
    data_type: str = "int16"
    function_code: int = 4  # 3 = holding registers (FC03), 4 = input registers (FC04)
    category: str = "Generale"  # display grouping label

    @field_validator("data_type")
    @classmethod
    def validate_data_type(cls, v: str) -> str:
        allowed = {"int16", "uint16"}
        if v not in allowed:
            raise ValueError(f"data_type must be one of {allowed}")
        return v

    @field_validator("function_code")
    @classmethod
    def validate_function_code(cls, v: int) -> int:
        if v not in (3, 4):
            raise ValueError("function_code must be 3 (holding) or 4 (input)")
        return v


class StatusMode(BaseModel):
    values: list[int]
    label: str
    color: str = "transparent"


class StatusConfig(BaseModel):
    register: int
    function_code: int = 3  # 3 = FC03 (holding), 4 = FC04 (input)
    data_type: str = "uint16"
    modes: dict[str, StatusMode]

    def resolve_mode(self, raw_value: int) -> tuple[str, StatusMode]:
        """Return (mode_key, StatusMode) for a given raw register value."""
        for key, mode in self.modes.items():
            if raw_value in mode.values:
                return key, mode
        # Default to standby if value is unknown
        return "standby", self.modes.get(
            "standby", StatusMode(values=[], label="Standby")
        )


class AppConfig(BaseModel):
    modbus: ModbusConfig
    database: DatabaseConfig
    polling: PollingConfig = PollingConfig()
    registers: list[RegisterConfig]
    status: StatusConfig


def load_config(path: str | Path = "config.yaml") -> AppConfig:
    """Load and validate configuration from a YAML file."""
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        raw: dict[str, Any] = yaml.safe_load(f)

    return AppConfig(**raw)
