#!/usr/bin/env python3
"""
Scansione completa dei registri Stiebel:
- FC04 (Input Registers) range 0-600, 1000-1100
- FC03 (Holding Registers) range 1000-2000
Valori 0x8000 (32768) = "non disponibile" vengono ignorati.
"""
from pymodbus.client import ModbusTcpClient

HOST = "192.168.0.4"
PORT = 502
UNIT_ID = 1
NA_VALUE = 32768  # 0x8000 = not available in Stiebel protocol

# Known descriptions from Stiebel ISG Modbus documentation
FC04_LABELS = {
    # Status
    500: "Betriebsstatus / Operating mode",
    501: "Betriebsstatus 2",
    502: "Störungsstatus / Fault",
    503: "Störungsstatus 2",
    # Temperatures
    504: "Außentemperatur / Outside temp [°C×0.1]",
    505: "Außentemperatur gemittelt [°C×0.1]",
    506: "Rücklauftemperatur HK1 / Return temp [°C×0.1]",
    507: "Vorlauftemperatur HK1 / Flow temp [°C×0.1]",
    508: "Vorlauftemperatur HK1 Soll / Flow setpoint [°C×0.1]",
    509: "Speichertemperatur / Storage temp [°C×0.1]",
    510: "WW Temperatur / DHW temp [°C×0.1]",
    511: "WW Temperatur Soll / DHW setpoint [°C×0.1]",
    512: "Vorlauftemperatur HK2 [°C×0.1]",
    513: "Vorlauftemperatur HK2 Soll [°C×0.1]",
    514: "Raumtemperatur HK1 / Room temp HK1 [°C×0.1]",
    515: "Raumtemperatur HK1 Soll / Room setpoint HK1 [°C×0.1]",
    516: "Raumtemperatur HK2 [°C×0.1]",
    517: "Raumtemperatur HK2 Soll [°C×0.1]",
    518: "Sauggastemperatur / Suction gas [°C×0.1]",
    519: "Kondensationstemperatur / Condensation [°C×0.1]",
    520: "Kältemitteldruck Hochdruck / HP pressure [bar×0.01]",
    521: "Kältemitteldruck Niederdruck / LP pressure [bar×0.01]",
    522: "Puffertemperatur oben / Buffer top [°C×0.1]",
    523: "Puffertemperatur unten / Buffer bottom [°C×0.1]",
    524: "Systemdruck / System pressure [bar×0.1]",
    525: "Volumenstrom / Flow rate [l/min×0.1]",
    # Energy counters
    526: "El. Energie Heizen HW [Wh]",
    527: "El. Energie Heizen LW [Wh]",
    528: "El. Energie Kühlen [Wh]",
    529: "El. Energie WW HW [Wh]",
    530: "El. Energie WW LW [Wh]",
    531: "Wärmemenge Heizen HW [Wh]",
    532: "Wärmemenge Heizen LW [Wh]",
    533: "Wärmemenge Kühlen [Wh]",
    534: "Wärmemenge WW HW [Wh]",
    535: "Wärmemenge WW LW [Wh]",
    # Power
    536: "Elektrische Leistung / El. power [W]",
    537: "Wärmeleistung / Thermal power [W]",
    538: "COP Aktuell / Actual COP [×0.1]",
    # Additional status
    540: "WP Stufe / HP stage",
    541: "NHZ Stufen / Aux stage",
    542: "Heizkreispumpe HK1",
    543: "Heizkreispumpe HK2",
}

FC03_LABELS = {
    # Setpoints (read/write)
    1500: "Komfortsolltemp HK1 [°C×0.1]",
    1501: "Eco-Solltemp HK1 [°C×0.1]",
    1502: "Heizkurvensteigung HK1 [×0.1]",
    1503: "Komfortsolltemp HK2 [°C×0.1]",
    1504: "Eco-Solltemp HK2 [°C×0.1]",
    1505: "Heizkurvensteigung HK2 [×0.1]",
    1506: "WW Komfortsolltemp [°C×0.1]",
    1507: "WW Eco-Solltemp [°C×0.1]",
    1508: "Anti-Legionellen Temp [°C×0.1]",
    1509: "Kesselvorlauftemperatur [°C×0.1]",
    1510: "Mischervorlauftemperatur HK1 [°C×0.1]",
    1511: "Mischervorlauftemperatur HK2 [°C×0.1]",
}

client = ModbusTcpClient(host=HOST, port=PORT, timeout=5)
if not client.connect():
    print("ERRORE: connessione fallita")
    exit(1)

print(f"Connesso a {HOST}:{PORT}  unit_id={UNIT_ID}\n")

# ── FC04 scan ──────────────────────────────────────────────────────
print("=" * 70)
print("INPUT REGISTERS (FC04) — Valori misurati")
print("=" * 70)
print(f"{'ADDR':>6}  {'RAW':>7}  {'INT16':>7}  {'INT16/10':>9}  Descrizione")
print("-" * 70)

for start in range(490, 560, 10):
    r = client.read_input_registers(address=start, count=10, slave=UNIT_ID)
    if r.isError():
        continue
    for i, raw in enumerate(r.registers):
        addr = start + i
        if raw == NA_VALUE:
            continue
        signed = raw if raw < 32768 else raw - 65536
        label = FC04_LABELS.get(addr, "")
        print(f"{addr:>6}  {raw:>7}  {signed:>7}  {signed/10:>9.1f}  {label}")

# also try broader range
for start in range(0, 500, 20):
    r = client.read_input_registers(address=start, count=20, slave=UNIT_ID)
    if r.isError():
        continue
    for i, raw in enumerate(r.registers):
        addr = start + i
        if raw == NA_VALUE:
            continue
        signed = raw if raw < 32768 else raw - 65536
        label = FC04_LABELS.get(addr, "range 0-499")
        print(f"{addr:>6}  {raw:>7}  {signed:>7}  {signed/10:>9.1f}  {label}")

# ── FC03 scan ──────────────────────────────────────────────────────
print()
print("=" * 70)
print("HOLDING REGISTERS (FC03) — Setpoint / Config")
print("=" * 70)
print(f"{'ADDR':>6}  {'RAW':>7}  {'INT16':>7}  {'INT16/10':>9}  Descrizione")
print("-" * 70)

for start in range(1490, 1560, 10):
    r = client.read_holding_registers(address=start, count=10, slave=UNIT_ID)
    if r.isError():
        continue
    for i, raw in enumerate(r.registers):
        addr = start + i
        if raw == NA_VALUE:
            continue
        signed = raw if raw < 32768 else raw - 65536
        label = FC03_LABELS.get(addr, "")
        print(f"{addr:>6}  {raw:>7}  {signed:>7}  {signed/10:>9.1f}  {label}")

client.close()
print("\nScansione completata.")
