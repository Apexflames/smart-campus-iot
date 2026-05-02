from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    # Roles: superadmin | admin | officer | viewer
    role = Column(String, default="admin")
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    audit_logs = relationship("AuditLog", back_populates="user")


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, ForeignKey("users.username"))
    action = Column(String)       # e.g. REGISTER_DEVICE, RESOLVE_ALERT, LOGIN
    target = Column(String)       # e.g. device_id or alert_id
    detail = Column(Text)         # human-readable description
    ip_address = Column(String, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    user = relationship("User", back_populates="audit_logs")


class Device(Base):
    __tablename__ = "devices"
    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String, unique=True, index=True)
    name = Column(String)
    location = Column(String)
    device_type = Column(String)  # motion, door, temperature, camera, perimeter, card_reader
    api_key = Column(String, unique=True, index=True)
    is_active = Column(Boolean, default=True)
    is_online = Column(Boolean, default=False)
    last_seen = Column(DateTime, nullable=True)
    registered_at = Column(DateTime, default=datetime.utcnow)
    risk_score = Column(Float, default=0.0)
    sensor_data = relationship("SensorData", back_populates="device", cascade="all, delete-orphan")
    alerts = relationship("ThreatAlert", back_populates="device", cascade="all, delete-orphan")


class SensorData(Base):
    __tablename__ = "sensor_data"
    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String, ForeignKey("devices.device_id"))
    data_type = Column(String)
    value = Column(Float)
    raw_data = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)
    device = relationship("Device", back_populates="sensor_data")


class ThreatAlert(Base):
    __tablename__ = "threat_alerts"
    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String, ForeignKey("devices.device_id"))
    alert_type = Column(String)
    severity = Column(String)  # low, medium, high, critical
    description = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)
    resolved = Column(Boolean, default=False)
    resolved_at = Column(DateTime, nullable=True)
    device = relationship("Device", back_populates="alerts")
