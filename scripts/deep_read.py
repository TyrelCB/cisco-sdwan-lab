#!/usr/bin/env python3
"""Deep read-side sweep of the DevNet SD-WAN sandbox (sandbox-sdwan-2).

One authenticated session, throttled requests, auto re-auth on redirect.
Saves every payload to out/ and prints a compact digest.
"""
import json, os, re, sys, time, urllib.request, ssl, http.cookiejar

BASE = "https://sandbox-sdwan-2.cisco.com"
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "out")
os.makedirs(OUT, exist_ok=True)

creds = {"user": os.environ.get("SDWAN_USER", "devnetuser"),
         "pass": os.environ.get("SDWAN_PASS", "RG!_Yw919_83")}
HEX_TOKEN = re.compile(r"^[0-9A-F]{64,256}$")
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(
    urllib.request.HTTPCookieProcessor(cj),
    urllib.request.HTTPSHandler(context=ctx))

def login():
    data = (f"j_username={creds['user']}&j_password={creds['pass']}").encode()
    req = urllib.request.Request(BASE + "/j_security_check", data=data, method="POST")
    try:
        opener.open(req, timeout=30).read()
    except Exception:
        pass
    tok = opener.open(BASE + "/dataservice/client/token", timeout=30).read().decode().strip()
    return tok if HEX_TOKEN.match(tok) else None

TOKEN = None

def login_token():
    """Return a fresh XSRF token for the current session (rotates), or None."""
    try:
        tok = opener.open(BASE + "/dataservice/client/token", timeout=30).read().decode().strip()
        return tok if HEX_TOKEN.match(tok) else None
    except Exception:
        return None

def get(path, name):
    global TOKEN
    for attempt in (1, 2):
        try:
            # token rotates per session-state; refetch before each call
            TOKEN = login_token()
            req = urllib.request.Request(BASE + "/dataservice/" + path.lstrip("/"))
            if TOKEN:
                req.add_header("X-XSRF-TOKEN", TOKEN)
            body = opener.open(req, timeout=40).read()
        except urllib.error.HTTPError as e:
            print(f"  GET {path}: HTTP {e.code}")
            time.sleep(3); continue
        # if we bounced to login HTML, re-auth once and retry
        if body.lstrip().startswith(b"<"):
            TOKEN = login()
            if TOKEN is None or attempt == 2:
                print(f"  GET {path}: session lost")
                return None
            continue
        open(os.path.join(OUT, name), "wb").write(body)
        print(f"  GET {path}: {len(body)}B -> out/{name}")
        time.sleep(2)
        return json.loads(body)
    return None

def realtime(device_ids, tables, name):
    global TOKEN
    payload = json.dumps({"deviceId": device_ids, "tables": tables}).encode()
    req = urllib.request.Request(BASE + "/dataservice/realtime/system/device",
                                 data=payload, method="POST",
                                 headers={"Content-Type": "application/json",
                                          "X-XSRF-TOKEN": TOKEN or ""})
    try:
        body = opener.open(req, timeout=60).read()
    except urllib.error.HTTPError as e:
        print(f"  realtime {name}: HTTP {e.code}"); return None
    if body.lstrip().startswith(b"<"):
        print(f"  realtime {name}: session lost"); return None
    open(os.path.join(OUT, name), "wb").write(body)
    print(f"  realtime {name}: {len(body)}B -> out/{name}")
    time.sleep(2)
    return json.loads(body)

def main():
    global TOKEN
    TOKEN = login()
    if TOKEN is None:
        print("login failed (locked?); try again in a few minutes"); sys.exit(1)
    print("authenticated")

    # Operator-verified working reads (all 200 with devnetuser on 20.x):
    #   /device                       inventory + per-device counters:
    #       controlConnections, bfdSessions/bfdSessionsUp, ompPeers,
    #       certificate-validity, reachability, version, uptime, cpu counts
    #   /alarms?...                   active alarms
    #   /device/bfd/sites/summary     per-site WAN health rollup
    #   /statistics/approute/query/fields   stats field catalog
    #   /device/control/synced/connections?deviceId=<sysip>  per-edge DTLS detail
    # Admin-only (403 for operator): /v1/device/inventory, /v1/system/info/*,
    # /device/runningconfig/*, /logs/*, cluster-management/*, device/validity (404),
    # realtime microservice (404). /system/device/control needs a valid category.

    inv = get("device", "device-full.json")
    devices = (inv or {}).get("data", [])
    get("alarms", "alarms.json")
    get("device/bfd/sites/summary", "bfd-sites-summary.json")
    get("statistics/approute/query/fields", "approute-fields.json")
    for e in [d for d in devices if d.get("personality") == "vedge"]:
        get(f"device/control/synced/connections?deviceId={e['system-ip']}",
            f"ctrl-conn-{e['host-name']}.json")

    print("\n== digest ==")
    for d in devices:
        print(f"  site={d.get('site-id'):>4} {d.get('personality'):>8} {d.get('host-name')}"
              f" ver={d.get('version')} reach={d.get('reachability')}"
              f" ctrl={d.get('controlConnections')} omp_peers={d.get('ompPeers')}"
              f" bfd={d.get('bfdSessionsUp')}/{d.get('bfdSessions')}"
              f" cert={d.get('certificate-validity')}")
    try:
        b = json.load(open(os.path.join(OUT, "bfd-sites-summary.json")))
        for d in b.get("data", []):
            print("site health:", d.get("status"), "-",
                  [(x["name"], x["count"]) for x in d.get("statusList", [])])
    except Exception as ex:
        print("bfd digest failed:", ex)
    try:
        a = json.load(open(os.path.join(OUT, "alarms.json")))
        data = a.get("data", {})
        rows = data.get("alarms", []) if isinstance(data, dict) else data
        print(f"active alarms: {len(rows or [])}")
        for r in (rows or [])[:10]:
            print("  ", r.get("severity"), r.get("type"), r.get("system-ip"), r.get("message"))
    except Exception as ex:
        print("alarm digest failed:", ex)

if __name__ == "__main__":
    main()
