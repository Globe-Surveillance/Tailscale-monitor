#!/usr/bin/env python3

import json
import os
import sys
from datetime import datetime, timezone

import requests

TS_TOKEN = os.getenv("TS_API_TOKEN")
TG_TOKEN = os.getenv("TG_BOT_TOKEN")
TG_CHAT = os.getenv("TG_CHAT_ID")

WATCH = {
    "srv-backstage",
    "srv-bml",
    "srv-laayoune",
    "synology-nas",
}

OFFLINE_AFTER = 360
STATE = "state.json"


def fail(msg):
    print(f"ERROR: {msg}")
    sys.exit(1)


if not TS_TOKEN:
    fail("TS_API_TOKEN non défini")

if not TG_TOKEN:
    fail("TG_BOT_TOKEN non défini")

if not TG_CHAT:
    fail("TG_CHAT_ID non défini")


def tg(msg):
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            json={
                "chat_id": TG_CHAT,
                "text": msg,
            },
            timeout=15,
        )
        r.raise_for_status()
    except Exception as e:
        print(f"Erreur Telegram: {e}")


def get_devices():
    url = "https://api.tailscale.com/api/v2/tailnet/-/devices"

    try:
        r = requests.get(
            url,
            headers={
                "Authorization": f"Bearer {TS_TOKEN}",
                "Accept": "application/json",
            },
            timeout=20,
        )

        if r.status_code == 401:
            fail(
                "Authentification Tailscale refusée (401).\n"
                "Vérifie que TS_API_TOKEN est un API Access Token valide."
                f"\nRéponse API: {r.text}"
            )

        r.raise_for_status()

        data = r.json()

        if "devices" not in data:
            fail(f"Réponse inattendue de l'API Tailscale : {data}")

        return data["devices"]

    except requests.RequestException as e:
        fail(f"Erreur API Tailscale: {e}")


now = datetime.now(timezone.utc)


def is_down(device):
    if "connectedToControl" in device:
        return not device["connectedToControl"]

    last_seen = device.get("lastSeen")

    if not last_seen:
        return True

    last_seen = datetime.fromisoformat(
        last_seen.replace("Z", "+00:00")
    )

    return (now - last_seen).total_seconds() > OFFLINE_AFTER


devices = get_devices()

down_now = set()
seen = {}

for device in devices:
    hostname = device.get("name", "").split(".")[0].lower()

    if WATCH and hostname not in WATCH:
        continue

    seen[hostname] = device.get("lastSeen", "Inconnu")

    if is_down(device):
        down_now.add(hostname)


try:
    with open(STATE, "r") as f:
        down_before = set(json.load(f).get("down", []))
except (FileNotFoundError, json.JSONDecodeError):
    down_before = set()


for host in sorted(down_now):
    tg(
        f"🚨 ALERTE DE SUPERVISION\n\n"
        f"Serveur : {host}\n"
        f"État : Hors ligne 🔴\n"
        f"Dernière communication : {seen[host]}\n\n"
        f"Le serveur est toujours indisponible.\n"
        f"Une intervention est recommandée."
    )


for host in sorted(down_before - down_now):
    tg(
        f"✅ SERVEUR RÉTABLI\n\n"
        f"Serveur : {host}\n"
        f"État : En ligne 🟢\n\n"
        f"Le serveur est de nouveau accessible et fonctionne normalement."
    )


with open(STATE, "w") as f:
    json.dump({"down": sorted(down_now)}, f)

print(
    f"Surveillance terminée. "
    f"Serveurs surveillés: {len(seen)} | "
    f"Hors ligne: {len(down_now)}"
)
