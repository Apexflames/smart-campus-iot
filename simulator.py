"""
Smart Campus IoT Device Simulator
──────────────────────────────────
Simulates 12 IoT devices across campus sending real sensor data to the SCSS server.
Run this alongside the main server to generate live data.

Usage:
    python simulator.py
    python simulator.py --url http://localhost:8000
    python simulator.py --attack  (inject threat scenarios)
"""
import asyncio
import httpx
import random
import json
import argparse
import sys
from datetime import datetime

BASE_URL = "http://localhost:8000"
ADMIN_USER = "admin"
ADMIN_PASS = "admin123"

# ── Device definitions ─────────────────────────────────────────────────────────
DEVICES = [
    {"name": "Motion Sensor — Main Gate",      "location": "Main Entrance",     "device_type": "motion",       "interval": 5},
    {"name": "Motion Sensor — Server Room",    "location": "Server Room A",     "device_type": "motion",       "interval": 8},
    {"name": "Door Lock — Admin Block",        "location": "Admin Block",       "device_type": "door",         "interval": 0},
    {"name": "Door Lock — Research Lab",       "location": "Research Lab B",    "device_type": "door",         "interval": 0},
    {"name": "Temp Monitor — Server Room A",   "location": "Server Room A",     "device_type": "temperature",  "interval": 30},
    {"name": "Temp Monitor — Electrical Room", "location": "Electrical Room",   "device_type": "temperature",  "interval": 30},
    {"name": "IP Camera — Car Park",           "location": "Car Park East",     "device_type": "camera",       "interval": 10},
    {"name": "IP Camera — Library",            "location": "Library Entrance",  "device_type": "camera",       "interval": 10},
    {"name": "Perimeter Sensor — North Fence", "location": "North Perimeter",   "device_type": "perimeter",    "interval": 15},
    {"name": "Perimeter Sensor — South Fence", "location": "South Perimeter",   "device_type": "perimeter",    "interval": 15},
    {"name": "Card Reader — Lab Block",        "location": "Lab Block Entry",   "device_type": "card_reader",  "interval": 0},
    {"name": "Card Reader — Staff Parking",    "location": "Staff Parking",     "device_type": "card_reader",  "interval": 0},
]


async def get_token(client: httpx.AsyncClient) -> str:
    r = await client.post(f"{BASE_URL}/api/auth/login", json={"username": ADMIN_USER, "password": ADMIN_PASS})
    if r.status_code != 200:
        print(f"✗ Login failed: {r.text}")
        sys.exit(1)
    token = r.json()["access_token"]
    print(f"✓ Authenticated as {ADMIN_USER}")
    return token


async def register_devices(client: httpx.AsyncClient, token: str) -> dict:
    """Register all devices and return a dict of name -> api_key"""
    headers = {"Authorization": f"Bearer {token}"}

    # Get existing devices
    r = await client.get(f"{BASE_URL}/api/devices", headers=headers)
    existing = {d["name"]: d for d in r.json()}

    device_keys = {}
    for device in DEVICES:
        if device["name"] in existing:
            # Already registered — we need to re-register to get key (or store it)
            # For simulator, we'll re-register if not in our local cache
            pass
        # Register (server will create new if needed)
        r = await client.post(f"{BASE_URL}/api/devices/register", headers=headers, json={
            "name": device["name"],
            "location": device["location"],
            "device_type": device["device_type"]
        })
        if r.status_code == 200:
            data = r.json()
            device_keys[device["name"]] = data["api_key"]
            print(f"  ✓ Registered: {device['name']}")
        else:
            print(f"  ⚠ Could not register {device['name']}: {r.text}")

    return device_keys


def generate_reading(device: dict) -> dict:
    """Generate a realistic sensor reading for the given device type"""
    dtype = device["device_type"]
    hour = datetime.utcnow().hour

    if dtype == "motion":
        location = device["location"]
        is_restricted = "Server" in location or "Lab" in location
        # Higher motion probability during work hours
        motion = random.random() < (0.3 if 8 <= hour <= 18 else 0.05)
        return {
            "data_type": "motion",
            "value": 1.0 if motion else 0.0,
            "metadata": {"zone": "restricted" if is_restricted else "open"}
        }

    elif dtype == "temperature":
        # Normal range 18–35°C with occasional spikes
        spike = random.random() < 0.02  # 2% chance of anomaly
        if spike:
            temp = random.uniform(55, 90)
        else:
            temp = random.gauss(28, 4)
            temp = max(15, min(45, temp))
        return {
            "data_type": "temperature",
            "value": round(temp, 1),
            "metadata": {"unit": "celsius"}
        }

    elif dtype == "door":
        # Random access event
        success = random.random() < 0.85
        return {
            "data_type": "access_attempt",
            "value": 1.0 if success else 0.0,
            "metadata": {"method": "badge"}
        }

    elif dtype == "camera":
        # Occasionally goes offline
        online = random.random() < 0.97
        motion = random.random() < 0.2
        return {
            "data_type": "camera_status",
            "value": 1.0 if online else 0.0,
            "metadata": {"motion_detected": motion}
        }

    elif dtype == "perimeter":
        breach_confidence = random.gauss(0.05, 0.1)
        breach_confidence = max(0.0, min(1.0, breach_confidence))
        return {
            "data_type": "perimeter_breach",
            "value": round(breach_confidence, 3),
            "metadata": {}
        }

    elif dtype == "card_reader":
        r = random.random()
        if r < 0.80:
            return {"data_type": "card_access", "value": 1.0, "metadata": {"card_id": f"CARD-{random.randint(1000,9999)}"}}
        elif r < 0.95:
            return {"data_type": "card_access", "value": 0.0, "metadata": {"card_id": f"CARD-{random.randint(1000,9999)}"}}
        else:
            return {"data_type": "card_access", "value": -1.0, "metadata": {"card_id": f"FAKE-{random.randint(100,999)}"}}

    return {"data_type": "heartbeat", "value": 1.0, "metadata": {}}


async def simulate_device(client: httpx.AsyncClient, device: dict, api_key: str):
    """Run a continuous simulation loop for one device"""
    headers = {"X-API-Key": api_key}
    name = device["name"]
    base_interval = device["interval"] if device["interval"] > 0 else random.randint(8, 20)

    print(f"  ▶ Starting: {name}")
    while True:
        try:
            reading = generate_reading(device)
            r = await client.post(f"{BASE_URL}/api/data", headers=headers, json=reading, timeout=5)
            status = "✓" if r.status_code == 200 else "✗"
            data = r.json() if r.status_code == 200 else {}
            alerts = data.get("alerts_generated", 0)
            alert_str = f" [{alerts} alert{'s' if alerts != 1 else ''}]" if alerts > 0 else ""
            ts = datetime.utcnow().strftime("%H:%M:%S")
            print(f"  {status} [{ts}] {name[:35]:<35} {reading['data_type']:20} = {reading['value']}{alert_str}")
        except Exception as e:
            print(f"  ✗ {name}: {e}")

        # Randomise interval slightly to avoid lockstep
        jitter = random.uniform(0.8, 1.5)
        await asyncio.sleep(base_interval * jitter)


async def inject_attack_scenarios(client: httpx.AsyncClient, device_keys: dict):
    """Inject specific threat scenarios for demo purposes"""
    print("\n[ATTACK SCENARIOS] Starting threat injection in 5 seconds...\n")
    await asyncio.sleep(5)

    scenarios = [
        {
            "name": "Brute Force Door Attack",
            "device": "Door Lock — Admin Block",
            "readings": [{"data_type": "access_attempt", "value": 0.0, "metadata": {"method": "badge"}}] * 7,
            "delay": 0.5
        },
        {
            "name": "Server Room Temperature Critical",
            "device": "Temp Monitor — Server Room A",
            "readings": [{"data_type": "temperature", "value": 87.5, "metadata": {"unit": "celsius"}}],
            "delay": 1
        },
        {
            "name": "Perimeter Breach",
            "device": "Perimeter Sensor — North Fence",
            "readings": [{"data_type": "perimeter_breach", "value": 0.92, "metadata": {}}],
            "delay": 1
        },
        {
            "name": "Unknown Card Access",
            "device": "Card Reader — Lab Block",
            "readings": [{"data_type": "card_access", "value": -1.0, "metadata": {"card_id": "CLONED-001"}}],
            "delay": 1
        },
        {
            "name": "Camera Offline",
            "device": "IP Camera — Car Park",
            "readings": [{"data_type": "camera_status", "value": 0.0, "metadata": {}}],
            "delay": 1
        },
    ]

    for scenario in scenarios:
        device_name = scenario["device"]
        api_key = device_keys.get(device_name)
        if not api_key:
            print(f"  ✗ No key for {device_name}")
            continue

        headers = {"X-API-Key": api_key}
        print(f"\n  ► Injecting: {scenario['name']}")
        for reading in scenario["readings"]:
            try:
                r = await client.post(f"{BASE_URL}/api/data", headers=headers, json=reading, timeout=5)
                data = r.json() if r.status_code == 200 else {}
                alerts = data.get("alerts_generated", 0)
                print(f"    → {reading['data_type']} = {reading['value']} | {alerts} alert(s)")
            except Exception as e:
                print(f"    ✗ Error: {e}")
            await asyncio.sleep(scenario["delay"])

        await asyncio.sleep(3)


async def main(url: str, attack_mode: bool):
    global BASE_URL
    BASE_URL = url.rstrip("/")

    print(f"\n{'='*60}")
    print("  SCSS — Smart Campus Security System Simulator")
    print(f"{'='*60}")
    print(f"  Server: {BASE_URL}\n")

    async with httpx.AsyncClient() as client:
        # Auth
        token = await get_token(client)

        # Register all devices
        print("\n[DEVICES] Registering devices...")
        device_keys = await register_devices(client, token)

        if not device_keys:
            print("✗ No devices registered. Exiting.")
            return

        print(f"\n✓ {len(device_keys)} device(s) ready\n")

        # Launch simulator tasks
        print("[SIMULATION] Starting data transmission...\n")
        tasks = []
        for device in DEVICES:
            key = device_keys.get(device["name"])
            if key:
                tasks.append(simulate_device(client, device, key))

        if attack_mode:
            tasks.append(inject_attack_scenarios(client, device_keys))

        await asyncio.gather(*tasks)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SCSS IoT Device Simulator")
    parser.add_argument("--url", default="http://localhost:8000", help="Server base URL")
    parser.add_argument("--attack", action="store_true", help="Inject threat scenarios for demo")
    args = parser.parse_args()

    try:
        asyncio.run(main(args.url, args.attack))
    except KeyboardInterrupt:
        print("\n\nSimulator stopped.")
