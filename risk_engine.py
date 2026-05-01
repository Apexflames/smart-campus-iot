from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from typing import List, Dict
import models


SEVERITY_SCORE = {"critical": 28, "high": 16, "medium": 8, "low": 3}


def assess_risk(
    device: models.Device,
    data_type: str,
    value: float,
    raw_data: dict,
    db: Session
) -> List[Dict]:
    alerts = []
    now = datetime.utcnow()
    hour = now.hour

    # ── Rule 1: Temperature thresholds ─────────────────────────────────────────
    if data_type == "temperature":
        if value >= 80:
            alerts.append({
                "alert_type": "TEMPERATURE_CRITICAL",
                "severity": "critical",
                "description": (
                    f"Critical temperature of {value:.1f}°C recorded at {device.location}. "
                    "Exceeds maximum safe threshold of 80°C. Immediate response required."
                )
            })
        elif value >= 50:
            alerts.append({
                "alert_type": "TEMPERATURE_HIGH",
                "severity": "high",
                "description": (
                    f"Elevated temperature of {value:.1f}°C recorded at {device.location}. "
                    "Exceeds high-alert threshold of 50°C."
                )
            })

    # ── Rule 2: Motion in restricted zone after hours ───────────────────────────
    if data_type == "motion" and value == 1.0:
        zone = raw_data.get("zone", "open")
        if zone == "restricted" and (hour >= 22 or hour < 6):
            alerts.append({
                "alert_type": "MOTION_AFTER_HOURS",
                "severity": "medium",
                "description": (
                    f"Motion detected in restricted zone at {device.location} at {now.strftime('%H:%M')} UTC. "
                    "Access to this area is not authorised during off-hours."
                )
            })
        elif zone == "restricted":
            alerts.append({
                "alert_type": "MOTION_RESTRICTED_ZONE",
                "severity": "low",
                "description": (
                    f"Motion detected in restricted zone at {device.location}. Verify authorisation."
                )
            })

    # ── Rule 3: Multiple failed door access attempts ────────────────────────────
    if data_type == "access_attempt" and value == 0.0:
        window = now - timedelta(seconds=60)
        failures = db.query(models.SensorData).filter(
            models.SensorData.device_id == device.device_id,
            models.SensorData.data_type == "access_attempt",
            models.SensorData.value == 0.0,
            models.SensorData.timestamp >= window
        ).count()
        if failures >= 5:
            alerts.append({
                "alert_type": "BRUTE_FORCE_DOOR",
                "severity": "critical",
                "description": (
                    f"{failures} failed access attempts detected at {device.location} within 60 seconds. "
                    "Possible brute-force attack or tailgating attempt."
                )
            })
        elif failures >= 3:
            alerts.append({
                "alert_type": "REPEATED_ACCESS_FAILURE",
                "severity": "high",
                "description": (
                    f"{failures} failed access attempts at {device.location} in the last 60 seconds."
                )
            })

    # ── Rule 4: Rapid data submission anomaly ───────────────────────────────────
    window = now - timedelta(seconds=30)
    burst_count = db.query(models.SensorData).filter(
        models.SensorData.device_id == device.device_id,
        models.SensorData.timestamp >= window
    ).count()
    if burst_count >= 15:
        alerts.append({
            "alert_type": "DATA_BURST_ANOMALY",
            "severity": "medium",
            "description": (
                f"Device '{device.name}' submitted {burst_count} readings in 30 seconds. "
                "Possible device malfunction, firmware exploit, or replay attack."
            )
        })

    # ── Rule 5: Perimeter breach ────────────────────────────────────────────────
    if data_type == "perimeter_breach" and value >= 0.8:
        alerts.append({
            "alert_type": "PERIMETER_BREACH",
            "severity": "high",
            "description": (
                f"Perimeter breach detected at {device.location} with {value * 100:.0f}% confidence. "
                "Physical security team should respond immediately."
            )
        })
    elif data_type == "perimeter_breach" and value >= 0.5:
        alerts.append({
            "alert_type": "PERIMETER_ANOMALY",
            "severity": "medium",
            "description": (
                f"Potential perimeter anomaly at {device.location} — confidence: {value * 100:.0f}%."
            )
        })

    # ── Rule 6: Camera offline ──────────────────────────────────────────────────
    if data_type == "camera_status" and value == 0.0:
        alerts.append({
            "alert_type": "CAMERA_OFFLINE",
            "severity": "medium",
            "description": (
                f"Security camera at {device.location} has gone offline. "
                "Visual coverage gap created — verify connectivity and physical integrity."
            )
        })

    # ── Rule 7: Unknown card ID ─────────────────────────────────────────────────
    if data_type == "card_access" and value == -1.0:
        card_id = raw_data.get("card_id", "UNKNOWN")
        alerts.append({
            "alert_type": "UNKNOWN_CARD_ACCESS",
            "severity": "high",
            "description": (
                f"Unregistered access card (ID: {card_id}) used at {device.location}. "
                "Card is not in the authorised personnel database."
            )
        })

    # ── Rule 8: Low battery / power anomaly ────────────────────────────────────
    if data_type == "battery" and value <= 5.0:
        alerts.append({
            "alert_type": "CRITICAL_BATTERY",
            "severity": "low",
            "description": (
                f"Device '{device.name}' at {device.location} battery at {value:.0f}%. "
                "Device may go offline soon."
            )
        })

    return alerts


def update_risk_score(current: float, alerts: List[Dict]) -> float:
    score = current
    for alert in alerts:
        score += SEVERITY_SCORE.get(alert["severity"], 0)
    return round(min(100.0, score), 1)


def decay_risk_score(current: float, hours_since_last_alert: float) -> float:
    """Score decays by 5 points per hour of no alerts"""
    decay = 5.0 * hours_since_last_alert
    return round(max(0.0, current - decay), 1)


def get_system_threat_level(devices: list) -> Dict:
    """Calculate overall campus threat level from device scores"""
    if not devices:
        return {"level": "NOMINAL", "color": "safe", "score": 0}

    scores = [d.risk_score for d in devices if d.is_active]
    if not scores:
        return {"level": "NOMINAL", "color": "safe", "score": 0}

    avg = sum(scores) / len(scores)
    max_score = max(scores)

    if max_score >= 80 or avg >= 60:
        return {"level": "CRITICAL", "color": "critical", "score": round(avg, 1)}
    elif max_score >= 60 or avg >= 40:
        return {"level": "HIGH", "color": "high", "score": round(avg, 1)}
    elif max_score >= 40 or avg >= 20:
        return {"level": "ELEVATED", "color": "medium", "score": round(avg, 1)}
    elif max_score >= 20 or avg >= 10:
        return {"level": "GUARDED", "color": "low", "score": round(avg, 1)}
    else:
        return {"level": "NOMINAL", "color": "safe", "score": round(avg, 1)}
