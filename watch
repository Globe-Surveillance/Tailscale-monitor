#!/usr/bin/env python3
import json
import os
from datetime import datetime, timezone
import requests

TS_TOKEN = os.environ["TS_API_TOKEN"]
TG_TOKEN = os.environ["TG_BOT_TOKEN"]
TG_CHAT = os.environ["TG_CHAT_ID"]

WATCH = {
    "srv-backstage",
    "srv-bml",
    "srv-laayoune",
    "synology-nas"
}

OFFLINE_AFTER = 360
STATE = "state.json"


def tg(msg):
    resp = requests.post(
        f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
        json={
            "chat_id": TG_CHAT,
            "text": msg
        },
        timeout=10
    )
    resp.raise_for_status()


r = requests.get(
    "https://api.tailscale.com/api/v2/tailnet/-/devices",
    headers={"Authorization": f"Bearer {TS_TOKEN}"},
    timeout=15
)
r.raise_for_status()

now = datetime.now(timezone.utc)


def is_down(d):
    if "connectedToControl" in d:
        return not d["connectedToControl"]

    last = d.get("lastSeen")
    if not last:
        return True

    last = datetime.fromisoformat(last.replace("Z", "+00:00"))
    return (now - last).total_seconds() > OFFLINE_AFTER


down_now = set()
seen = {}

for d in r.json()["devices"]:
    key = d["name"].split(".")[0].lower()

    if WATCH and key not in WATCH:
        continue

    seen[key] = d.get("lastSeen", "?")

    if is_down(d):
        down_now.add(key)


try:
    with open(STATE) as f:
        down_before = set(json.load(f)["down"])
except (FileNotFoundError, json.JSONDecodeError, KeyError):
    down_before = set()


# Envoie un rappel à chaque exécution tant que le serveur est hors ligne
for k in sorted(down_now):
    tg(
        f"🚨 ALERTE DE SUPERVISION\n\n"
        f"Serveur : {k}\n"
        f"État : Hors ligne 🔴\n"
        f"Dernière communication : {seen[k]}\n\n"
        f"Le serveur est toujours indisponible.\n"
        f"Une intervention est recommandée."
    )


# Notification lorsque le serveur revient en ligne
for k in sorted(down_before - down_now):
    tg(
        f"✅ SERVEUR RÉTABLI\n\n"
        f"Serveur : {k}\n"
        f"État : En ligne 🟢\n\n"
        f"Le serveur est de nouveau accessible et fonctionne normalement."
    )


with open(STATE, "w") as f:
    json.dump({"down": sorted(down_now)}, f)
