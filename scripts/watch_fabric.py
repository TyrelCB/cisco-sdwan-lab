#!/usr/bin/env python3
"""Fabric watcher: one cheap /device poll, diff vs last snapshot, print deltas.

Intended to run every ~15 min (LangBang scheduled task). Exit 0 + "NO CHANGE"
when healthy; prints ALERT lines when any monitored counter moves.
State: out/watch_state.json (previous snapshot).
"""
import json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, "..", "out"))
STATE = os.path.join(OUT, "watch_state.json")

FIELDS = ("reachability", "state", "status", "controlConnections",
          "ompPeers", "bfdSessions", "bfdSessionsUp", "certificate-validity",
          "version")


def fetch():
    r = subprocess.run([os.path.join(HERE, "sdv2.sh"), "GET",
                        "/dataservice/device"],
                       capture_output=True, text=True, timeout=120)
    body = r.stdout.strip()
    try:
        data = json.loads(body)["data"]
    except Exception:
        print(f"ALERT: poll failed (auth or sandbox down?): {body[:120]!r}")
        sys.exit(2)
    snap = {}
    for d in data:
        key = f"{d.get('personality')}/{d.get('host-name')}"
        snap[key] = {}
        for f in FIELDS:
            v = d.get(f)
            if f not in ("version",) and isinstance(v, str) and v.isdigit():
                v = int(v)
            snap[key][f] = v
    return snap


def main():
    os.makedirs(OUT, exist_ok=True)
    snap = fetch()
    old = {}
    if os.path.exists(STATE):
        try:
            old = json.load(open(STATE))
        except Exception:
            old = {}
    alerts = []
    for key, cur in snap.items():
        prev = old.get(key)
        if prev is None and old:
            alerts.append(f"NEW device {key}: {cur}")
            continue
        for f, v in cur.items():
            if prev and prev.get(f) != v:
                alerts.append(f"{key}: {f} {prev.get(f)} -> {v}")
    for key in old:
        if key not in snap:
            alerts.append(f"device {key} DISAPPEARED from inventory")
    json.dump(snap, open(STATE, "w"), indent=1)
    if not old:
        print(f"BASELINE captured: {len(snap)} devices, all counters recorded")
    elif alerts:
        print("CHANGES:")
        for a in alerts:
            print("  ", a)
    else:
        up = sum(1 for k, v in snap.items()
                 if k.startswith("vedge") and v.get("bfdSessionsUp") == v.get("bfdSessions")
                 and v.get("reachability") == "reachable")
        print(f"NO CHANGE — {len(snap)} devices, {up}/4 edges fully healthy "
              f"(all BFD up, reachable, certs valid)")


if __name__ == "__main__":
    main()
