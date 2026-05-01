from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect, Header, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from pydantic import BaseModel
from typing import Optional, List
import uuid, json, asyncio, os

from database import engine, get_db, SessionLocal
import models, auth, risk_engine
from dotenv import load_dotenv

load_dotenv()
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Smart Campus Security System", version="1.0.0", docs_url="/docs")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")


# ─── WebSocket Connection Manager ─────────────────────────────────────────────
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


# ─── Startup: seed default admin ──────────────────────────────────────────────
@app.on_event("startup")
def seed_admin():
    db = SessionLocal()
    try:
        existing = db.query(models.User).filter(models.User.username == "admin").first()
        if not existing:
            admin = models.User(
                username="admin",
                email="admin@smartcampus.edu",
                hashed_password=auth.hash_password("admin123"),
                role="admin"
            )
            db.add(admin)
            db.commit()
            print("✓ Default admin created: admin / admin123")
    finally:
        db.close()


# ─── Background: mark offline devices ─────────────────────────────────────────
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

@app.on_event("startup")
async def start_heartbeat():
    asyncio.create_task(device_heartbeat())


# ─── Schemas ───────────────────────────────────────────────────────────────────
class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str

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


# ─── Auth Routes ───────────────────────────────────────────────────────────────
@app.post("/api/auth/register")
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(models.User).filter(models.User.username == req.username).first():
        raise HTTPException(400, "Username already exists")
    if db.query(models.User).filter(models.User.email == req.email).first():
        raise HTTPException(400, "Email already registered")
    user = models.User(
        username=req.username,
        email=req.email,
        hashed_password=auth.hash_password(req.password)
    )
    db.add(user)
    db.commit()
    return {"message": "Account created", "username": req.username}

@app.post("/api/auth/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == req.username).first()
    if not user or not auth.verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = auth.create_access_token({"sub": user.username, "role": user.role})
    return {"access_token": token, "token_type": "bearer", "username": user.username, "role": user.role}

@app.get("/api/auth/me")
def me(current_user: models.User = Depends(auth.get_current_user)):
    return {"username": current_user.username, "email": current_user.email, "role": current_user.role}


# ─── Device Routes ─────────────────────────────────────────────────────────────
@app.post("/api/devices/register")
def register_device(
    req: DeviceRegisterRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    device_id = f"DEV-{str(uuid.uuid4())[:8].upper()}"
    api_key = str(uuid.uuid4())
    device = models.Device(
        device_id=device_id,
        name=req.name,
        location=req.location,
        device_type=req.device_type,
        api_key=api_key,
        is_online=False,
        risk_score=0.0
    )
    db.add(device)
    db.commit()
    db.refresh(device)
    return {
        "device_id": device_id,
        "name": req.name,
        "location": req.location,
        "device_type": req.device_type,
        "api_key": api_key,
        "message": "Device registered. Store the API key securely — it will not be shown again."
    }

@app.get("/api/devices")
def list_devices(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    devices = db.query(models.Device).filter(models.Device.is_active == True).all()
    return [
        {
            "device_id": d.device_id,
            "name": d.name,
            "location": d.location,
            "device_type": d.device_type,
            "is_online": d.is_online,
            "risk_score": d.risk_score,
            "last_seen": d.last_seen.isoformat() if d.last_seen else None,
            "registered_at": d.registered_at.isoformat()
        }
        for d in devices
    ]

@app.delete("/api/devices/{device_id}")
def delete_device(
    device_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    device = db.query(models.Device).filter(models.Device.device_id == device_id).first()
    if not device:
        raise HTTPException(404, "Device not found")
    device.is_active = False
    db.commit()
    return {"message": f"Device {device_id} deactivated"}


# ─── Sensor Data Route ─────────────────────────────────────────────────────────
@app.post("/api/data")
async def ingest_data(
    req: SensorDataRequest,
    x_api_key: str = Header(..., alias="X-API-Key"),
    db: Session = Depends(get_db)
):
    device = auth.authenticate_device(x_api_key, db)
    if not device:
        raise HTTPException(status_code=403, detail="Invalid or inactive device API key")

    # Mark online
    device.is_online = True
    device.last_seen = datetime.utcnow()

    # Store reading
    reading = models.SensorData(
        device_id=device.device_id,
        data_type=req.data_type,
        value=req.value,
        raw_data=json.dumps(req.metadata or {})
    )
    db.add(reading)
    db.flush()

    # Run risk engine
    raw = req.metadata or {}
    new_alerts = risk_engine.assess_risk(device, req.data_type, req.value, raw, db)

    # Save alerts and update risk score
    saved_alerts = []
    for alert_data in new_alerts:
        alert = models.ThreatAlert(
            device_id=device.device_id,
            alert_type=alert_data["alert_type"],
            severity=alert_data["severity"],
            description=alert_data["description"]
        )
        db.add(alert)
        db.flush()
        saved_alerts.append({
            "id": alert.id,
            "device_id": device.device_id,
            "device_name": device.name,
            "alert_type": alert.alert_type,
            "severity": alert.severity,
            "description": alert.description,
            "timestamp": alert.timestamp.isoformat()
        })

    device.risk_score = risk_engine.update_risk_score(device.risk_score, new_alerts)
    db.commit()

    # Broadcast over WebSocket
    ws_payload = {
        "type": "sensor_data",
        "device_id": device.device_id,
        "device_name": device.name,
        "device_type": device.device_type,
        "location": device.location,
        "data_type": req.data_type,
        "value": req.value,
        "risk_score": device.risk_score,
        "timestamp": datetime.utcnow().isoformat(),
        "alerts": saved_alerts
    }
    await manager.broadcast(ws_payload)

    return {"status": "accepted", "alerts_generated": len(saved_alerts), "risk_score": device.risk_score}

@app.get("/api/data/{device_id}")
def get_device_data(
    device_id: str,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    readings = (
        db.query(models.SensorData)
        .filter(models.SensorData.device_id == device_id)
        .order_by(models.SensorData.timestamp.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": r.id,
            "data_type": r.data_type,
            "value": r.value,
            "timestamp": r.timestamp.isoformat()
        }
        for r in reversed(readings)
    ]


# ─── Threat Alert Routes ───────────────────────────────────────────────────────
@app.get("/api/threats")
def get_threats(
    severity: Optional[str] = None,
    resolved: Optional[bool] = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    q = db.query(models.ThreatAlert).join(
        models.Device, models.ThreatAlert.device_id == models.Device.device_id
    )
    if severity:
        q = q.filter(models.ThreatAlert.severity == severity)
    if resolved is not None:
        q = q.filter(models.ThreatAlert.resolved == resolved)
    alerts = q.order_by(models.ThreatAlert.timestamp.desc()).limit(limit).all()
    return [
        {
            "id": a.id,
            "device_id": a.device_id,
            "device_name": a.device.name if a.device else "Unknown",
            "device_location": a.device.location if a.device else "Unknown",
            "alert_type": a.alert_type,
            "severity": a.severity,
            "description": a.description,
            "timestamp": a.timestamp.isoformat(),
            "resolved": a.resolved,
            "resolved_at": a.resolved_at.isoformat() if a.resolved_at else None
        }
        for a in alerts
    ]

@app.patch("/api/threats/{alert_id}/resolve")
async def resolve_threat(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    alert = db.query(models.ThreatAlert).filter(models.ThreatAlert.id == alert_id).first()
    if not alert:
        raise HTTPException(404, "Alert not found")
    alert.resolved = True
    alert.resolved_at = datetime.utcnow()
    db.commit()
    await manager.broadcast({"type": "alert_resolved", "alert_id": alert_id})
    return {"message": "Alert resolved", "alert_id": alert_id}


# ─── Dashboard Stats ───────────────────────────────────────────────────────────
@app.get("/api/dashboard/stats")
def dashboard_stats(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    all_devices = db.query(models.Device).filter(models.Device.is_active == True).all()
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0)

    total_devices = len(all_devices)
    online_devices = sum(1 for d in all_devices if d.is_online)
    alerts_today = db.query(models.ThreatAlert).filter(
        models.ThreatAlert.timestamp >= today_start,
        models.ThreatAlert.resolved == False
    ).count()
    critical_alerts = db.query(models.ThreatAlert).filter(
        models.ThreatAlert.severity == "critical",
        models.ThreatAlert.resolved == False
    ).count()
    unresolved_total = db.query(models.ThreatAlert).filter(
        models.ThreatAlert.resolved == False
    ).count()

    threat_level = risk_engine.get_system_threat_level(all_devices)

    return {
        "total_devices": total_devices,
        "online_devices": online_devices,
        "offline_devices": total_devices - online_devices,
        "alerts_today": alerts_today,
        "critical_alerts": critical_alerts,
        "unresolved_alerts": unresolved_total,
        "threat_level": threat_level
    }


# ─── WebSocket Live Feed ───────────────────────────────────────────────────────
@app.websocket("/ws/live")
async def websocket_endpoint(ws: WebSocket, token: Optional[str] = None):
    db = SessionLocal()
    try:
        user = auth.get_current_user_ws(token or "", db)
        if not user:
            await ws.close(code=4001)
            return
        await manager.connect(ws)
        await ws.send_json({"type": "connected", "message": f"Welcome {user.username}"})
        try:
            while True:
                await ws.receive_text()
        except WebSocketDisconnect:
            manager.disconnect(ws)
    finally:
        db.close()


# ─── Serve Frontend ────────────────────────────────────────────────────────────
@app.get("/")
def serve_frontend():
    return FileResponse("static/index.html")