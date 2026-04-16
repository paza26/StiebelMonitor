#!/usr/bin/env python3
"""
Diagnostica rapida: prova FC03 e FC04, unit_id 0/1/2/100, range di indirizzi vari.
"""
import time
from pymodbus.client import ModbusTcpClient

HOST = "192.168.0.4"
PORT = 502

client = ModbusTcpClient(host=HOST, port=PORT, timeout=5)
if not client.connect():
    print("ERRORE: connessione fallita")
    exit(1)

print(f"Connesso a {HOST}:{PORT}\n")

ranges_to_try = [
    (0, 50),
    (100, 150),
    (500, 560),
    (1000, 1050),
    (1500, 1520),
    (2000, 2050),
    (3000, 3020),
]

print("=== Batch reads FC03 + FC04 per unit_id 0,1,2,100 ===")
for uid in [0, 1, 2, 100]:
    for start, end in ranges_to_try:
        r = client.read_holding_registers(address=start, count=end-start, slave=uid)
        if not r.isError():
            print(f"FC03 unit_id={uid} addr={start}-{end}: {r.registers[:10]}")
        r4 = client.read_input_registers(address=start, count=end-start, slave=uid)
        if not r4.isError():
            print(f"FC04 unit_id={uid} addr={start}-{end}: {r4.registers[:10]}")

print("\n=== Scan singolo FC03 uid=1 addr 0-50 ===")
for addr in range(0, 51):
    r = client.read_holding_registers(address=addr, count=1, slave=1)
    if not r.isError():
        print(f"  FC03 uid=1 addr={addr}: {r.registers[0]}")

print("\n=== Scan singolo FC04 uid=1 addr 0-50 ===")
for addr in range(0, 51):
    r = client.read_input_registers(address=addr, count=1, slave=1)
    if not r.isError():
        print(f"  FC04 uid=1 addr={addr}: {r.registers[0]}")

print("\n=== Scan singolo FC03 uid=1 addr 100-200 ===")
for addr in range(100, 201):
    r = client.read_holding_registers(address=addr, count=1, slave=1)
    if not r.isError():
        print(f"  FC03 uid=1 addr={addr}: {r.registers[0]}")

client.close()
print("\nDiagnostica completata.")
