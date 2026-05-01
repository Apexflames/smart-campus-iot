# Smart Campus Security System (SCSS)
### IoT Security Prototype — Final Year Project

A full-stack web application simulating a smart campus IoT security system with real-time threat detection, device authentication, and a live monitoring dashboard.

---

## Features

- **JWT Authentication** — Secure admin login with 24-hour token expiry
- **Device Registry** — Register IoT devices with unique API keys
- **Sensor Data Ingestion** — Secure REST endpoint for device data submission
- **Risk Assessment Engine** — 8-rule threat classifier with severity levels
- **Real-Time Dashboard** — WebSocket-powered live monitoring
- **Threat Log** — Full alert history with resolve functionality
- **Device Simulator** — 12 simulated campus IoT devices

---

## Quick Start

### 1. Clone / extract the project

```bash
cd smart-campus-iot
```

### 2. Create a virtual environment and install dependencies

```bash
python -m venv venv

# macOS/Linux
source venv/bin/activate

# Windows
venv\Scripts\activate

pip install -r requirements.txt
```

### 3. Configure environment variables

```bash
cp .env.example .env
# Edit .env and set a strong SECRET_KEY
```

### 4. Start the server

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 5. Open the dashboard

Visit: [http://localhost:8000](http://localhost:8000)

**Default credentials:** `admin` / `admin123`

### 6. Start the device simulator

In a second terminal (with venv active):

```bash
# Normal simulation
python simulator.py

# With attack scenarios injected (good for demo)
python simulator.py --attack
```

---

## API Documentation

Interactive API docs available at: [http://localhost:8000/docs](http://localhost:8000/docs)

### Key Endpoints

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/auth/register` | None | Create admin account |
| POST | `/api/auth/login` | None | Login, receive JWT |
| POST | `/api/devices/register` | JWT | Register IoT device |
| GET | `/api/devices` | JWT | List all devices |
| POST | `/api/data` | API Key | Submit sensor reading |
| GET | `/api/threats` | JWT | List all threat alerts |
| PATCH | `/api/threats/{id}/resolve` | JWT | Resolve an alert |
| GET | `/api/dashboard/stats` | JWT | Dashboard statistics |
| WS | `/ws/live?token=...` | JWT | Real-time data stream |

---

## Deployment (Render.com — Free)

1. Push the project to a GitHub repository
2. Go to [render.com](https://render.com) → New → Web Service
3. Connect your repository
4. Set the following:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Add environment variables: `SECRET_KEY`, `TOKEN_EXPIRE_MINUTES`
6. Deploy

---

## Risk Assessment Rules

| Rule | Trigger | Severity |
|------|---------|----------|
| Temperature Critical | > 80°C | Critical |
| Temperature High | > 50°C | High |
| Motion After Hours | Restricted zone, 10pm–6am | Medium |
| Brute Force Door | ≥ 5 failed attempts / 60s | Critical |
| Repeated Access Failure | ≥ 3 failed attempts / 60s | High |
| Data Burst Anomaly | ≥ 15 readings / 30s | Medium |
| Perimeter Breach | Confidence ≥ 80% | High |
| Camera Offline | Status = offline | Medium |
| Unknown Card Access | Unregistered card ID | High |
| Critical Battery | Battery ≤ 5% | Low |

---

## Project Structure

```
smart-campus-iot/
├── main.py           # FastAPI app, routes, WebSocket
├── models.py         # SQLAlchemy database models
├── database.py       # DB engine and session setup
├── auth.py           # JWT authentication module
├── risk_engine.py    # Threat detection rule engine
├── simulator.py      # IoT device simulator (12 devices)
├── requirements.txt
├── .env.example
└── static/
    └── index.html    # Full dashboard frontend
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.10+ / FastAPI |
| Database | SQLite + SQLAlchemy ORM |
| Authentication | JWT (python-jose) + bcrypt |
| Real-time | WebSockets |
| Frontend | HTML5 + CSS3 + Vanilla JS |
| Charts | Chart.js 4.x |

---

*Developed as a Final Year Computer Science Project — 2026*
