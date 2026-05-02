from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect, Header, status, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
from pydantic import BaseModel
from typing import Optional, List
import uuid, json, asyncio, os, statistics

from database import engine, get_db, SessionLocal
import models, auth, risk_engine
from dotenv import load_dotenv

load_dotenv()
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Smart Campus Security System", version="2.0.0", docs_url="/docs")

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")


# ── RBAC ───────────────────────────────────────────────────────────────────────
ROLE_RANK = {"viewer": 1, "officer": 2, "admin": 3, "superadmin": 4}

def require_role(min_role: str):
    def checker(current_user: models.User = Depends(auth.get_current_user)):
        if ROLE_RANK.get(current_user.role, 0) < ROLE_RANK.get(min_role, 99):
            raise HTTPException(status_code=403, detail=f"Requires role: {min_role} or higher")
        return current_user
    return checker


# ── AUDIT HELPER ───────────────────────────────────────────────────────────────
def audit(db, username, action, target, detail, ip=None):
    db.add(models.AuditLog(username=username, action=action,
           target=target, detail=detail, ip_address=ip))


# ── WEBSOCKET MANAGER ──────────────────────────────────────────────────────────
class ConnectionManager:
    def __init__(self):
        self.connections: List[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.connections.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.connections:
            self.connections.remove(ws)

    async def broadcast(self, data: dict):
        dead = []
        for ws in self.connections:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

manager = ConnectionManager()


# ── STARTUP ────────────────────────────────────────────────────────────────────
@app.on_event("startup")
def seed_admin():
    db = SessionLocal()
    try:
        if not db.query(models.User).filter(models.User.username == "admin").first():
            db.add(models.User(
                username="admin", email="admin@smartcampus.edu",
                hashed_password=auth.hash_password("admin123"),
                role="superadmin"
            ))
            db.commit()
            print("✓ Default superadmin: admin / admin123")
    finally:
        db.close()


@app.on_event("startup")
async def start_background():
    asyncio.create_task(device_heartbeat())


async def device_heartbeat():
    while True:
        await asyncio.sleep(30)
        db = SessionLocal()
        try:
            cutoff = datetime.utcnow() - timedelta(minutes=5)
            stale = db.query(models.Device).filter(
                models.Device.is_online == True,
                models.Device.last_seen < cutoff
            ).all()
            for d in stale:
                d.is_online = False
            if stale:
                db.commit()
                await manager.broadcast({
                    "type": "device_status_update",
                    "updates": [{"device_id": d.device_id, "is_online": False} for d in stale]
                })
        finally:
            db.close()


# ── SCHEMAS ────────────────────────────────────────────────────────────────────
class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str
    role: Optional[str] = "viewer"

class LoginRequest(BaseModel):
    username: str
    password: str

class DeviceRegisterRequest(BaseModel):
    name: str
    location: str
    device_type: str

class SensorDataRequest(BaseModel):
    data_type: str
    value: float
    metadata: Optional[dict] = {}

class AttackScenarioRequest(BaseModel):
    scenario: str


# ── AUTH ───────────────────────────────────────────────────────────────────────
@app.post("/api/auth/register")
def register(req: RegisterRequest, request: Request, db: Session = Depends(get_db)):
    if db.query(models.User).filter(models.User.username == req.username).first():
        raise HTTPException(400, "Username already exists")
    if db.query(models.User).filter(models.User.email == req.email).first():
        raise HTTPException(400, "Email already registered")
    role = req.role if req.role in ROLE_RANK else "viewer"
    user = models.User(username=req.username, email=req.email,
                       hashed_password=auth.hash_password(req.password), role=role)
    db.add(user)
    audit(db, req.username, "REGISTER", req.username, f"New account, role={role}", request.client.host)
    db.commit()
    return {"message": "Account created", "username": req.username, "role": role}


@app.post("/api/auth/login")
def login(req: LoginRequest, request: Request, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == req.username).first()
    if not user or not auth.verify_password(req.password, user.hashed_password):
        raise HTTPException(401, "Invalid credentials")
    token = auth.create_access_token({"sub": user.username, "role": user.role})
    audit(db, user.username, "LOGIN", user.username, f"Login from {request.client.host}", request.client.host)
    db.commit()
    return {"access_token": token, "token_type": "bearer", "username": user.username, "role": user.role}


@app.get("/api/auth/me")
def me(current_user: models.User = Depends(auth.get_current_user)):
    return {"username": current_user.username, "email": current_user.email, "role": current_user.role}


# ── USER MANAGEMENT ────────────────────────────────────────────────────────────
@app.get("/api/users")
def list_users(db: Session = Depends(get_db), current_user: models.User = Depends(require_role("superadmin"))):
    users = db.query(models.User).filter(models.User.is_active == True).all()
    return [{"id": u.id, "username": u.username, "email": u.email,
             "role": u.role, "created_at": u.created_at.isoformat()} for u in users]


@app.patch("/api/users/{username}/role")
def update_role(username: str, body: dict, request: Request,
                db: Session = Depends(get_db), current_user: models.User = Depends(require_role("superadmin"))):
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user:
        raise HTTPException(404, "User not found")
    new_role = body.get("role")
    if new_role not in ROLE_RANK:
        raise HTTPException(400, "Invalid role")
    old_role = user.role
    user.role = new_role
    audit(db, current_user.username, "CHANGE_ROLE", username, f"{old_role} → {new_role}", request.client.host)
    db.commit()
    return {"message": f"{username} role updated to {new_role}"}


# ── DEVICES ────────────────────────────────────────────────────────────────────
@app.post("/api/devices/register")
def register_device(req: DeviceRegisterRequest, request: Request,
                    db: Session = Depends(get_db), current_user: models.User = Depends(require_role("admin"))):
    device_id = f"DEV-{str(uuid.uuid4())[:8].upper()}"
    api_key = str(uuid.uuid4())
    device = models.Device(device_id=device_id, name=req.name, location=req.location,
                           device_type=req.device_type, api_key=api_key, is_online=False, risk_score=0.0)
    db.add(device)
    audit(db, current_user.username, "REGISTER_DEVICE", device_id,
          f"Registered '{req.name}' ({req.device_type}) at {req.location}", request.client.host)
    db.commit()
    db.refresh(device)
    return {"device_id": device_id, "name": req.name, "location": req.location,
            "device_type": req.device_type, "api_key": api_key,
            "message": "Device registered. Store the API key securely."}


@app.get("/api/devices")
def list_devices(db: Session = Depends(get_db), current_user: models.User = Depends(require_role("viewer"))):
    return [{"device_id": d.device_id, "name": d.name, "location": d.location,
             "device_type": d.device_type, "is_online": d.is_online, "risk_score": d.risk_score,
             "last_seen": d.last_seen.isoformat() if d.last_seen else None,
             "registered_at": d.registered_at.isoformat()}
            for d in db.query(models.Device).filter(models.Device.is_active == True).all()]


@app.delete("/api/devices/{device_id}")
def delete_device(device_id: str, request: Request, db: Session = Depends(get_db),
                  current_user: models.User = Depends(require_role("admin"))):
    device = db.query(models.Device).filter(models.Device.device_id == device_id).first()
    if not device:
        raise HTTPException(404, "Device not found")
    device.is_active = False
    audit(db, current_user.username, "REMOVE_DEVICE", device_id,
          f"Deactivated '{device.name}'", request.client.host)
    db.commit()
    return {"message": f"Device {device_id} deactivated"}


# ── SENSOR DATA ────────────────────────────────────────────────────────────────
@app.post("/api/data")
async def ingest_data(req: SensorDataRequest, x_api_key: str = Header(..., alias="X-API-Key"),
                      db: Session = Depends(get_db)):
    device = auth.authenticate_device(x_api_key, db)
    if not device:
        raise HTTPException(403, "Invalid or inactive device API key")

    device.is_online = True
    device.last_seen = datetime.utcnow()

    reading = models.SensorData(device_id=device.device_id, data_type=req.data_type,
                                value=req.value, raw_data=json.dumps(req.metadata or {}))
    db.add(reading)
    db.flush()

    new_alerts = (risk_engine.assess_risk(device, req.data_type, req.value, req.metadata or {}, db)
                  + detect_anomaly(device.device_id, req.data_type, req.value, db))

    saved_alerts = []
    for ad in new_alerts:
        alert = models.ThreatAlert(device_id=device.device_id, alert_type=ad["alert_type"],
                                   severity=ad["severity"], description=ad["description"])
        db.add(alert)
        db.flush()
        saved_alerts.append({"id": alert.id, "device_id": device.device_id,
                              "device_name": device.name, "alert_type": alert.alert_type,
                              "severity": alert.severity, "description": alert.description,
                              "timestamp": alert.timestamp.isoformat()})

    device.risk_score = risk_engine.update_risk_score(device.risk_score, new_alerts)
    db.commit()

    await manager.broadcast({"type": "sensor_data", "device_id": device.device_id,
                              "device_name": device.name, "device_type": device.device_type,
                              "location": device.location, "data_type": req.data_type,
                              "value": req.value, "risk_score": device.risk_score,
                              "timestamp": datetime.utcnow().isoformat(), "alerts": saved_alerts})

    return {"status": "accepted", "alerts_generated": len(saved_alerts), "risk_score": device.risk_score}


@app.get("/api/data/{device_id}")
def get_device_data(device_id: str, limit: int = 50, db: Session = Depends(get_db),
                    current_user: models.User = Depends(require_role("viewer"))):
    readings = (db.query(models.SensorData).filter(models.SensorData.device_id == device_id)
                .order_by(models.SensorData.timestamp.desc()).limit(limit).all())
    return [{"id": r.id, "data_type": r.data_type, "value": r.value,
             "timestamp": r.timestamp.isoformat()} for r in reversed(readings)]


# ── ANOMALY DETECTION ──────────────────────────────────────────────────────────
def detect_anomaly(device_id, data_type, value, db):
    if data_type not in ["temperature", "perimeter_breach", "battery"]:
        return []
    history = (db.query(models.SensorData.value)
               .filter(models.SensorData.device_id == device_id,
                       models.SensorData.data_type == data_type)
               .order_by(models.SensorData.timestamp.desc()).limit(100).all())
    values = [r.value for r in history]
    if len(values) < 20:
        return []
    mean = statistics.mean(values)
    stdev = statistics.stdev(values)
    if stdev < 0.01:
        return []
    z = abs(value - mean) / stdev
    if z >= 4.0:
        return [{"alert_type": "STATISTICAL_ANOMALY", "severity": "high",
                 "description": f"Reading {value:.2f} for '{data_type}' is {z:.1f} std deviations from baseline mean {mean:.2f}. Statistically abnormal based on last {len(values)} readings."}]
    elif z >= 3.0:
        return [{"alert_type": "STATISTICAL_ANOMALY", "severity": "medium",
                 "description": f"Reading {value:.2f} for '{data_type}' is {z:.1f} std deviations from baseline mean {mean:.2f}. Possible sensor fault or anomalous condition."}]
    return []


# ── THREATS ────────────────────────────────────────────────────────────────────
@app.get("/api/threats")
def get_threats(severity: Optional[str] = None, resolved: Optional[bool] = None,
                limit: int = 100, db: Session = Depends(get_db),
                current_user: models.User = Depends(require_role("viewer"))):
    q = db.query(models.ThreatAlert).join(models.Device, models.ThreatAlert.device_id == models.Device.device_id)
    if severity:
        q = q.filter(models.ThreatAlert.severity == severity)
    if resolved is not None:
        q = q.filter(models.ThreatAlert.resolved == resolved)
    alerts = q.order_by(models.ThreatAlert.timestamp.desc()).limit(limit).all()
    return [{"id": a.id, "device_id": a.device_id,
             "device_name": a.device.name if a.device else "Unknown",
             "device_location": a.device.location if a.device else "Unknown",
             "alert_type": a.alert_type, "severity": a.severity, "description": a.description,
             "timestamp": a.timestamp.isoformat(), "resolved": a.resolved,
             "resolved_at": a.resolved_at.isoformat() if a.resolved_at else None} for a in alerts]


@app.patch("/api/threats/{alert_id}/resolve")
async def resolve_threat(alert_id: int, request: Request, db: Session = Depends(get_db),
                         current_user: models.User = Depends(require_role("officer"))):
    alert = db.query(models.ThreatAlert).filter(models.ThreatAlert.id == alert_id).first()
    if not alert:
        raise HTTPException(404, "Alert not found")
    alert.resolved = True
    alert.resolved_at = datetime.utcnow()
    audit(db, current_user.username, "RESOLVE_ALERT", str(alert_id),
          f"Resolved {alert.alert_type} on {alert.device_id}", request.client.host)
    db.commit()
    await manager.broadcast({"type": "alert_resolved", "alert_id": alert_id})
    return {"message": "Alert resolved", "alert_id": alert_id}


# ── DASHBOARD STATS ────────────────────────────────────────────────────────────
@app.get("/api/dashboard/stats")
def dashboard_stats(db: Session = Depends(get_db),
                    current_user: models.User = Depends(require_role("viewer"))):
    all_devices = db.query(models.Device).filter(models.Device.is_active == True).all()
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    return {
        "total_devices": len(all_devices),
        "online_devices": sum(1 for d in all_devices if d.is_online),
        "offline_devices": sum(1 for d in all_devices if not d.is_online),
        "alerts_today": db.query(models.ThreatAlert).filter(
            models.ThreatAlert.timestamp >= today, models.ThreatAlert.resolved == False).count(),
        "critical_alerts": db.query(models.ThreatAlert).filter(
            models.ThreatAlert.severity == "critical", models.ThreatAlert.resolved == False).count(),
        "unresolved_alerts": db.query(models.ThreatAlert).filter(models.ThreatAlert.resolved == False).count(),
        "threat_level": risk_engine.get_system_threat_level(all_devices)
    }


# ── ANALYTICS ─────────────────────────────────────────────────────────────────
@app.get("/api/analytics/alerts-per-day")
def alerts_per_day(days: int = 7, db: Session = Depends(get_db),
                   current_user: models.User = Depends(require_role("viewer"))):
    since = datetime.utcnow() - timedelta(days=days)
    # Use strftime for SQLite compatibility; PostgreSQL also supports it via func
    rows = (db.query(
                func.strftime('%Y-%m-%d', models.ThreatAlert.timestamp).label("day"),
                models.ThreatAlert.severity,
                func.count().label("count"))
            .filter(models.ThreatAlert.timestamp >= since)
            .group_by(
                func.strftime('%Y-%m-%d', models.ThreatAlert.timestamp),
                models.ThreatAlert.severity)
            .order_by(func.strftime('%Y-%m-%d', models.ThreatAlert.timestamp))
            .all())
    result = {}
    for row in rows:
        d = str(row.day)
        if d not in result:
            result[d] = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        if row.severity in result[d]:
            result[d][row.severity] = row.count
    return result


@app.get("/api/analytics/top-devices")
def top_devices(db: Session = Depends(get_db), current_user: models.User = Depends(require_role("viewer"))):
    rows = (db.query(models.ThreatAlert.device_id, func.count().label("alert_count"))
            .filter(models.ThreatAlert.resolved == False)
            .group_by(models.ThreatAlert.device_id)
            .order_by(func.count().desc()).limit(5).all())
    result = []
    for row in rows:
        device = db.query(models.Device).filter(models.Device.device_id == row.device_id).first()
        result.append({"device_id": row.device_id,
                       "name": device.name if device else row.device_id,
                       "location": device.location if device else "Unknown",
                       "alert_count": row.alert_count,
                       "risk_score": device.risk_score if device else 0})
    return result


@app.get("/api/analytics/severity-breakdown")
def severity_breakdown(db: Session = Depends(get_db), current_user: models.User = Depends(require_role("viewer"))):
    rows = db.query(models.ThreatAlert.severity, func.count().label("count")).group_by(models.ThreatAlert.severity).all()
    return {row.severity: row.count for row in rows}


@app.get("/api/analytics/alert-types")
def alert_types(db: Session = Depends(get_db), current_user: models.User = Depends(require_role("viewer"))):
    rows = (db.query(models.ThreatAlert.alert_type, func.count().label("count"))
            .group_by(models.ThreatAlert.alert_type).order_by(func.count().desc()).limit(8).all())
    return [{"type": r.alert_type, "count": r.count} for r in rows]


# ── AUDIT LOG ──────────────────────────────────────────────────────────────────
@app.get("/api/audit")
def get_audit_log(limit: int = 100, db: Session = Depends(get_db),
                  current_user: models.User = Depends(require_role("admin"))):
    logs = db.query(models.AuditLog).order_by(models.AuditLog.timestamp.desc()).limit(limit).all()
    return [{"id": l.id, "username": l.username, "action": l.action, "target": l.target,
             "detail": l.detail, "ip_address": l.ip_address,
             "timestamp": l.timestamp.isoformat()} for l in logs]


# ── DEMO ATTACK TRIGGER ────────────────────────────────────────────────────────
@app.post("/api/demo/trigger-attack")
async def trigger_attack(req: AttackScenarioRequest, request: Request,
                         db: Session = Depends(get_db),
                         current_user: models.User = Depends(require_role("admin"))):
    devices = db.query(models.Device).filter(models.Device.is_active == True).all()
    if not devices:
        raise HTTPException(400, "No devices registered. Run the simulator first.")

    def find(dtype):
        return next((d for d in devices if d.device_type == dtype), devices[0])

    SCENARIOS = {
        "brute_force":          {"device": find("door"),        "label": "Brute Force Door Attack",
                                 "readings": [{"data_type": "access_attempt", "value": 0.0, "metadata": {"method": "badge"}}] * 7},
        "temperature_critical": {"device": find("temperature"),  "label": "Critical Temperature Spike",
                                 "readings": [{"data_type": "temperature", "value": 87.5, "metadata": {}}]},
        "perimeter_breach":     {"device": find("perimeter"),    "label": "Perimeter Breach Detected",
                                 "readings": [{"data_type": "perimeter_breach", "value": 0.94, "metadata": {}}]},
        "unknown_card":         {"device": find("card_reader"),  "label": "Unknown Card Access Attempt",
                                 "readings": [{"data_type": "card_access", "value": -1.0, "metadata": {"card_id": "CLONED-001"}}]},
        "camera_offline":       {"device": find("camera"),       "label": "Security Camera Offline",
                                 "readings": [{"data_type": "camera_status", "value": 0.0, "metadata": {}}]},
    }

    sc = SCENARIOS.get(req.scenario)
    if not sc:
        raise HTTPException(400, f"Unknown scenario. Options: {list(SCENARIOS.keys())}")

    device = sc["device"]
    device.is_online = True
    device.last_seen = datetime.utcnow()
    total_alerts = []

    for reading in sc["readings"]:
        r = models.SensorData(device_id=device.device_id, data_type=reading["data_type"],
                              value=reading["value"], raw_data=json.dumps(reading.get("metadata", {})))
        db.add(r)
        db.flush()
        new_alerts = risk_engine.assess_risk(device, reading["data_type"], reading["value"],
                                             reading.get("metadata", {}), db)
        for ad in new_alerts:
            alert = models.ThreatAlert(device_id=device.device_id, alert_type=ad["alert_type"],
                                       severity=ad["severity"], description=ad["description"])
            db.add(alert)
            db.flush()
            entry = {"id": alert.id, "device_id": device.device_id, "device_name": device.name,
                     "alert_type": alert.alert_type, "severity": alert.severity,
                     "description": alert.description, "timestamp": alert.timestamp.isoformat()}
            total_alerts.append(entry)
            await manager.broadcast({"type": "sensor_data", "device_id": device.device_id,
                                     "device_name": device.name, "device_type": device.device_type,
                                     "location": device.location, "data_type": reading["data_type"],
                                     "value": reading["value"], "risk_score": device.risk_score,
                                     "timestamp": datetime.utcnow().isoformat(), "alerts": [entry]})
        device.risk_score = risk_engine.update_risk_score(device.risk_score, new_alerts)

    audit(db, current_user.username, "DEMO_ATTACK", req.scenario,
          f"Triggered '{sc['label']}' demo", request.client.host)
    db.commit()
    return {"scenario": req.scenario, "label": sc["label"], "device": device.name,
            "alerts_generated": len(total_alerts), "alerts": total_alerts}


# ── WEBSOCKET ──────────────────────────────────────────────────────────────────
@app.websocket("/ws/live")
async def websocket_endpoint(ws: WebSocket, token: Optional[str] = None):
    db = SessionLocal()
    try:
        user = auth.get_current_user_ws(token or "", db)
        if not user:
            await ws.close(code=4001)
            return
        await manager.connect(ws)
        await ws.send_json({"type": "connected", "message": f"Welcome {user.username}", "role": user.role})
        try:
            while True:
                await ws.receive_text()
        except WebSocketDisconnect:
            manager.disconnect(ws)
    finally:
        db.close()


# ── FRONTEND ───────────────────────────────────────────────────────────────────
@app.get("/")
def serve_frontend():
    return FileResponse("static/index.html")
