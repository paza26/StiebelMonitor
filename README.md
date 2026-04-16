# StiebelMonitor

Monitor per pompa di calore **Stiebel Eltron HPA-O 6 CS Plus**.

Raccoglie tutti i parametri Modbus della macchina ogni 60 secondi, li salva in PostgreSQL e li visualizza tramite un'interfaccia web con:

- **Valori in tempo reale** — ultimo valore campionato per ogni tag, con indicazione dello stato macchina (Riscaldamento / Raffrescamento / ACS / Standby)
- **Grafico storico** — seleziona tag e range temporale; lo sfondo del grafico mostra bande colorate per la modalità operativa:
  - 🔴 **Rosso** → Riscaldamento
  - 🔵 **Blu** → Raffrescamento
  - 🟡 **Giallo** → ACS
  - Nessuno sfondo → Standby

## Architettura

```
[Stiebel Eltron HPA-O 6 CS Plus]
        │ Modbus TCP
        ▼
[Python App (FastAPI)]
   ├── Modbus Poller (APScheduler, ogni 60s)
   ├── REST API
   └── Web UI (Chart.js)
        │
        ▼
[PostgreSQL 16]
```

## Quick Start

### 1. Configura

Modifica `config.yaml` con l'IP della tua pompa di calore / ISG e verifica gli indirizzi dei registri Modbus:

```yaml
modbus:
  host: "192.168.1.100"   # IP del tuo ISG
  port: 502
  unit_id: 1
```

### 2. Avvia con Docker Compose

```bash
docker compose up -d --build
```

### 3. Accedi all'interfaccia

Apri il browser su [http://localhost:8080](http://localhost:8080)

## Struttura Progetto

```
├── config.yaml            # Configurazione Modbus, DB, registri, stati
├── docker-compose.yml     # App + PostgreSQL
├── Dockerfile
├── requirements.txt
└── app/
    ├── main.py            # FastAPI + endpoints REST
    ├── config.py          # Loader configurazione YAML
    ├── models.py          # Modelli SQLAlchemy (Reading, MachineStatus)
    ├── database.py        # Engine DB + query CRUD
    ├── modbus_reader.py   # Client Modbus TCP (pymodbus)
    ├── scheduler.py       # Polling periodico con APScheduler
    └── static/
        └── index.html     # Interfaccia web (SPA)
```

## API Endpoints

| Metodo | Endpoint | Descrizione |
|--------|----------|-------------|
| GET | `/api/tags` | Lista tag configurati con descrizione e unità |
| GET | `/api/readings?tag=...&start=...&end=...` | Letture storiche filtrate per tag e intervallo |
| GET | `/api/readings/latest` | Ultimo valore per ogni tag + stato macchina |
| GET | `/api/status?start=...&end=...` | Storico stati macchina (per sfondi grafico) |
| GET | `/api/config/modes` | Modalità operative configurate con colori |

## Note

- Gli **indirizzi dei registri Modbus** nel `config.yaml` sono basati su valori comuni per sistemi ISG Stiebel. **Verificarli** con la documentazione Modbus del proprio ISG/pompa di calore.
- Il `config.yaml` è montato come volume Docker: le modifiche non richiedono rebuild dell'immagine (solo restart del container).
- Nessuna autenticazione: pensato per uso su rete locale.
