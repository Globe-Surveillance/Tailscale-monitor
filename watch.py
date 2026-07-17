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

OFFLINE_AFTER = 360        # يعتبر الجهاز Offline بعد 6 دقائق
REMINDER_EVERY = 3600      # تذكير كل ساعة

STATE = "state.json"


def fail(msg):
    print(msg)
    sys.exit(1)


if not TS_TOKEN:
    fail("TS_API_TOKEN non défini")

if not TG_TOKEN:
    fail("TG_BOT_TOKEN non défini")

if not TG_CHAT:
    fail("TG_CHAT_ID non défini")


def tg(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            json={
                "chat_id": TG_CHAT,
                "text": msg,
            },
            timeout=15,
        ).raise_for_status()
    except Exception as e:
        print(f"Telegram: {e}")


def get_devices():
    r = requests.get(
        "https://api.tailscale.com/api/v2/tailnet/-/devices",
        headers={
            "Authorization": f"Bearer {TS_TOKEN}",
            "Accept": "application/json",
        },
        timeout=20,
    )

    if r.status_code == 401:
        fail("TS_API_TOKEN invalide")

    r.raise_for_status()

    return r.json()["devices"]


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

    host = device.get("name", "").split(".")[0].lower()

    if WATCH and host not in WATCH:
        continue

    seen[host] = device.get("lastSeen", "Inconnu")

    if is_down(device):
        down_now.add(host)


try:
    with open(STATE) as f:
        state = json.load(f)
except Exception:
    state = {"down": {}}

down_before = state.get("down", {})

new_state = {"down": {}}

#
# Nouveaux OFFLINE + rappels
#
for host in sorted(down_now):

    now_iso = now.isoformat()

    if host not in down_before:

        tg(
            f"🚨 ALERTE DE SUPERVISION\n\n"
            f"Serveur : {host}\n"
            f"État : Hors ligne 🔴\n"
            f"Dernière communication : {seen[host]}\n\n"
            f"Le serveur est indisponible.\n"
            f"Une intervention est recommandée."
        )

        new_state["down"][host] = {
            "since": now_iso,
            "last_alert": now_iso,
        }

    else:

        last_alert = datetime.fromisoformat(
            down_before[host]["last_alert"]
        )

        if (now - last_alert).total_seconds() >= REMINDER_EVERY:

            tg(
                f"⚠️ RAPPEL DE SUPERVISION\n\n"
                f"Serveur : {host}\n"
                f"État : Toujours hors ligne 🔴\n"
                f"Dernière communication : {seen[host]}\n\n"
                f"Le serveur est toujours indisponible."
            )

            last_alert_iso = now_iso

        else:
            last_alert_iso = down_before[host]["last_alert"]

        new_state["down"][host] = {
            "since": down_before[host]["since"],
            "last_alert": last_alert_iso,
        }

#
# Retour ONLINE
#
for host in sorted(down_before):

    if host not in down_now:

        tg(
            f"✅ SERVEUR RÉTABLI\n\n"
            f"Serveur : {host}\n"
            f"État : En ligne 🟢\n\n"
            f"Le serveur est de nouveau accessible et fonctionne normalement."
        )


with open(STATE, "w") as f:
    json.dump(new_state, f, indent=2)

print(
    f"Surveillance terminée | "
    f"Surveillés: {len(seen)} | "
    f"Hors ligne: {len(down_now)}"
)
