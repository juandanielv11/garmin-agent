#!/usr/bin/env python3
"""
garmin_sync.py

Descarga tus actividades de running desde Garmin Connect usando la
librería no oficial `garminconnect` y guarda un snapshot en data/activities.json
(y un CSV plano en data/activities.csv) para que otra herramienta (o Claude,
leyendo el repo) pueda usarlo para comparar plan vs. real.

Credenciales: se leen SOLO de variables de entorno, nunca hardcodeadas:
    GARMIN_EMAIL
    GARMIN_PASSWORD

En GitHub Actions esas variables vienen de GitHub Secrets (ver
.github/workflows/sync.yml). Localmente puedes exportarlas antes de correr
el script:

    export GARMIN_EMAIL="tu_correo@ejemplo.com"
    export GARMIN_PASSWORD="tu_password"
    python garmin_sync.py

Notas importantes (léelas antes de automatizar esto sin supervisión):
  - garminconnect es una librería NO oficial (ingeniería inversa del API
    interno de Garmin Connect). Garmin puede cambiar su API o su login sin
    aviso y romper este script.
  - Si Garmin activa un challenge de MFA/captcha en tu cuenta, el login
    automático fallará hasta que lo resuelvas manualmente entrando por la
    web/app una vez.
  - Se guarda un token de sesión en .garminconnect_tokens/ para evitar
    loguearte cada vez (reduce el riesgo de que Garmin pida verificación
    extra). No subas esa carpeta a git (ver .gitignore).
"""

import csv
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

try:
    from garminconnect import Garmin
except ImportError:
    print("Falta la librería 'garminconnect'. Instala con: pip install garminconnect", file=sys.stderr)
    sys.exit(1)

DATA_DIR = Path(__file__).parent / "data"
TOKEN_DIR = Path(__file__).parent / ".garminconnect_tokens"

# Cuántos días hacia atrás traer actividades en cada corrida.
# Ajusta si corres el sync con menos frecuencia (ej. 30 si es mensual).
LOOKBACK_DAYS = int(os.environ.get("GARMIN_LOOKBACK_DAYS", "14"))


def get_client() -> Garmin:
    email = os.environ.get("GARMIN_EMAIL")
    password = os.environ.get("GARMIN_PASSWORD")
    if not email or not password:
        print("Debes definir GARMIN_EMAIL y GARMIN_PASSWORD como variables de entorno.", file=sys.stderr)
        sys.exit(1)

    TOKEN_DIR.mkdir(exist_ok=True)
    client = Garmin(email=email, password=password)

    # Reusa tokens guardados si existen, para no hacer login completo cada vez.
    try:
        client.login(str(TOKEN_DIR))
    except Exception:
        # Si no hay tokens válidos, hace login completo con email/password.
        client.login()
        try:
            client.garth.dump(str(TOKEN_DIR))
        except Exception:
            pass

    return client


def is_running_activity(activity: dict) -> bool:
    activity_type = (activity.get("activityType") or {}).get("typeKey", "")
    return "running" in activity_type.lower()


def fetch_activities(client: Garmin, lookback_days: int) -> list:
    start = datetime.now() - timedelta(days=lookback_days)
    activities = client.get_activities_by_date(
        start.strftime("%Y-%m-%d"),
        datetime.now().strftime("%Y-%m-%d"),
        activitytype="running",
    )
    return activities


def normalize(activity: dict) -> dict:
    distance_km = round((activity.get("distance") or 0) / 1000, 2)
    duration_s = activity.get("duration") or 0
    avg_pace_min_per_km = None
    if distance_km > 0:
        avg_pace_min_per_km = round((duration_s / 60) / distance_km, 2)

    return {
        "activityId": activity.get("activityId"),
        "date": (activity.get("startTimeLocal") or "")[:10],
        "name": activity.get("activityName"),
        "distance_km": distance_km,
        "duration_min": round(duration_s / 60, 1),
        "avg_pace_min_per_km": avg_pace_min_per_km,
        "avg_hr": activity.get("averageHR"),
        "max_hr": activity.get("maxHR"),
        "elevation_gain_m": activity.get("elevationGain"),
        "calories": activity.get("calories"),
        "aerobic_training_effect": activity.get("aerobicTrainingEffect"),
        "anaerobic_training_effect": activity.get("anaerobicTrainingEffect"),
    }


def merge_with_existing(new_records: list, existing_path: Path) -> list:
    existing = []
    if existing_path.exists():
        try:
            existing = json.loads(existing_path.read_text())
        except Exception:
            existing = []

    by_id = {r["activityId"]: r for r in existing if r.get("activityId") is not None}
    for r in new_records:
        if r.get("activityId") is not None:
            by_id[r["activityId"]] = r

    merged = sorted(by_id.values(), key=lambda r: r.get("date") or "", reverse=True)
    return merged


def write_outputs(records: list):
    DATA_DIR.mkdir(exist_ok=True)
    json_path = DATA_DIR / "activities.json"
    csv_path = DATA_DIR / "activities.csv"

    json_path.write_text(json.dumps(records, indent=2, ensure_ascii=False))

    if records:
        fieldnames = list(records[0].keys())
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(records)

    meta_path = DATA_DIR / "last_sync.json"
    meta_path.write_text(json.dumps({
        "last_sync_utc": datetime.utcnow().isoformat() + "Z",
        "activity_count": len(records),
    }, indent=2))


def main():
    client = get_client()
    raw_activities = fetch_activities(client, LOOKBACK_DAYS)
    running_only = [a for a in raw_activities if is_running_activity(a)] if raw_activities else []
    normalized = [normalize(a) for a in running_only]

    existing_path = DATA_DIR / "activities.json"
    merged = merge_with_existing(normalized, existing_path)

    write_outputs(merged)
    print(f"OK: {len(normalized)} actividades nuevas/actualizadas. Total en data/activities.json: {len(merged)}")


if __name__ == "__main__":
    main()
