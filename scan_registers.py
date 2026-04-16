#!/usr/bin/env python3
"""
Stiebel Monitor — Modbus Register Scanner
==========================================
Scans a range of holding registers on the target device and reports
which addresses return valid data. Use the output to update config.yaml
with the correct register addresses for your specific device.

Usage:
    python scan_registers.py [host] [port] [unit_id] [start] [end] [batch]

Examples:
    # Scan the default range with IP from config.yaml
    python scan_registers.py

    # Scan a specific IP and range
    python scan_registers.py 192.168.0.4 502 1 0 2000

Dependencies: pymodbus (already in requirements.txt)
"""

import sys
import time
from pathlib import Path

try:
    from pymodbus.client import ModbusTcpClient
except ImportError:
    print("ERROR: pymodbus not installed. Run: pip install pymodbus")
    sys.exit(1)

try:
    import yaml
    _cfg = yaml.safe_load(open("config.yaml"))
    DEFAULT_HOST    = _cfg["modbus"]["host"]
    DEFAULT_PORT    = _cfg["modbus"]["port"]
    DEFAULT_UNIT_ID = _cfg["modbus"]["unit_id"]
except Exception:
    DEFAULT_HOST    = "192.168.0.4"
    DEFAULT_PORT    = 502
    DEFAULT_UNIT_ID = 1

# ---------------------------------------------------------------------------
# CLI args
# ---------------------------------------------------------------------------
HOST     = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_HOST
PORT     = int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_PORT
UNIT_ID  = int(sys.argv[3]) if len(sys.argv) > 3 else DEFAULT_UNIT_ID
SCAN_START = int(sys.argv[4]) if len(sys.argv) > 4 else 0
SCAN_END   = int(sys.argv[5]) if len(sys.argv) > 5 else 3000
BATCH_SIZE = int(sys.argv[6]) if len(sys.argv) > 6 else 10   # registers per request

# ---------------------------------------------------------------------------
# Stiebel Eltron ISG known register descriptions
# (from official ISG Modbus documentation, addresses are 0-based)
# ---------------------------------------------------------------------------
KNOWN_REGISTERS = {
    # ── System / Operating values ─────────────────────────────────────
    0:  "Betriebsart / Operating mode",
    1:  "HK1 Betriebsart",
    2:  "HK2 Betriebsart",
    3:  "WW Betriebsart / DHW mode",
    5:  "WP Stufe / Heat pump stage",
    6:  "NHZ Stufen / Aux heating stages",
    7:  "WP Status / Heat pump status",
    8:  "FB Status",
    9:  "Störung / Fault",
    11: "Anlagenstatus / System status",
    12: "Außentemperatur / Outside temp [°C × 0.1]",
    13: "Außentemperatur gemittelt [°C × 0.1]",
    14: "Vorlauftemperatur HK1 [°C × 0.1]",
    15: "Vorlauftemperatur HK1 Soll [°C × 0.1]",
    16: "Rücklauftemperatur / Return temp [°C × 0.1]",
    17: "Speichertemperatur / Storage temp [°C × 0.1]",
    18: "WW Temperatur Soll / DHW set temp",
    19: "Sauggastemp / Suction gas temp [°C × 0.1]",
    20: "Vorlauftemperatur HK2 [°C × 0.1]",
    21: "Vorlauftemperatur HK2 Soll [°C × 0.1]",
    22: "Raumtemperatur HK1 [°C × 0.1]",
    23: "Raumtemperatur HK2 [°C × 0.1]",
    24: "Raumtemperatur HK1 Soll [°C × 0.1]",
    25: "Raumtemperatur HK2 Soll [°C × 0.1]",
    26: "Kältemitteldruck Heizen HP [bar × 0.01]",
    27: "Kältemitteldruck Kühlen LP [bar × 0.01]",
    28: "WW Temperatur Ist [°C × 0.1]",
    29: "Verdichtertemperatur [°C × 0.1]",
    30: "Puffertemperatur oben [°C × 0.1]",
    31: "Puffertemperatur unten [°C × 0.1]",
    32: "Heizkreispumpe HK1",
    33: "Heizkreispumpe HK2",
    34: "Systemdruck [bar × 0.1]",
    35: "Volumenstrom [l/min × 0.1]",
    # ── Energy counters ────────────────────────────────────────────────
    40: "El. Energie WP Heizen [Wh high word]",
    41: "El. Energie WP Heizen [Wh low word]",
    42: "El. Energie WP Kühlen [Wh]",
    43: "El. Energie WW [Wh high]",
    44: "El. Energie WW [Wh low]",
    45: "El. Energie NHZ [Wh]",
    46: "Wärmemenge Heizen [Wh high]",
    47: "Wärmemenge Heizen [Wh low]",
    48: "Wärmemenge Kühlen [Wh]",
    49: "Wärmemenge WW [Wh high]",
    50: "Wärmemenge WW [Wh low]",
    # ── Setpoints (read/write) ─────────────────────────────────────────
    1000: "Komfortsolltemperatur HK1 [°C × 0.1]",
    1001: "Eco Solltemperatur HK1 [°C × 0.1]",
    1002: "Heizkurvensteigung HK1",
    1003: "Komfortsolltemperatur HK2 [°C × 0.1]",
    1004: "Eco Solltemperatur HK2 [°C × 0.1]",
    1005: "Heizkurvensteigung HK2",
    1006: "WW Komfortsolltemperatur [°C × 0.1]",
    1007: "WW Eco Solltemperatur [°C × 0.1]",
}

# ---------------------------------------------------------------------------
# Scan
# ---------------------------------------------------------------------------
def scan(host: str, port: int, unit_id: int, start: int, end: int, batch: int):
    print(f"\n{'='*65}")
    print(f"  Stiebel Modbus Register Scanner")
    print(f"  Host: {host}:{port}  Unit ID: {unit_id}")
    print(f"  Scanning addresses {start} – {end}  (batch size: {batch})")
    print(f"{'='*65}\n")

    client = ModbusTcpClient(host=host, port=port, timeout=5)
    if not client.connect():
        print(f"ERROR: Cannot connect to {host}:{port}")
        return

    print(f"Connected to {host}:{port}\n")
    print(f"{'ADDR':>6}  {'RAW':>8}  {'HEX':>8}  {'INT16':>8}  Description")
    print("-" * 65)

    valid_addresses = []
    current = start

    try:
        while current <= end:
            # Read a batch (reduce individual TCP round-trips)
            count = min(batch, end - current + 1)
            result = client.read_holding_registers(
                address=current, count=count, slave=unit_id
            )

            if result.isError():
                # If the whole batch fails, try individual registers
                for addr in range(current, current + count):
                    r = client.read_holding_registers(address=addr, count=1, slave=unit_id)
                    if not r.isError():
                        raw = r.registers[0]
                        signed = raw if raw < 32768 else raw - 65536
                        label = KNOWN_REGISTERS.get(addr, "")
                        print(
                            f"{addr:>6}  {raw:>8}  {raw:#010x}  {signed:>8}  {label}"
                        )
                        valid_addresses.append((addr, raw, signed))
                    time.sleep(0.02)
            else:
                for i, raw in enumerate(result.registers):
                    addr = current + i
                    signed = raw if raw < 32768 else raw - 65536
                    label = KNOWN_REGISTERS.get(addr, "")
                    print(
                        f"{addr:>6}  {raw:>8}  {raw:#010x}  {signed:>8}  {label}"
                    )
                    valid_addresses.append((addr, raw, signed))

            current += count
            time.sleep(0.05)  # small delay between batches

    except KeyboardInterrupt:
        print("\n[interrupted]")
    finally:
        client.close()

    # ── Summary ─────────────────────────────────────────────────────────
    print(f"\n{'='*65}")
    print(f"  Scan complete — {len(valid_addresses)} valid registers found")
    print(f"={'='*65}\n")

    if valid_addresses:
        print("Valid addresses (copy into config.yaml):")
        print()
        for addr, raw, signed in valid_addresses:
            label = KNOWN_REGISTERS.get(addr, "unknown")
            print(
                f"  - address: {addr}\n"
                f"    tag: \"tag_{addr}\"\n"
                f"    description: \"{label}\"\n"
                f"    unit: \"\"\n"
                f"    scale: 1.0\n"
                f"    data_type: \"uint16\"\n"
            )


if __name__ == "__main__":
    scan(HOST, PORT, UNIT_ID, SCAN_START, SCAN_END, BATCH_SIZE)
