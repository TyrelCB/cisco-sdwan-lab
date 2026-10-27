# Device roles & configuration — sandbox-sdwan-2 fabric

Evidence: `out/device-full.json` (inventory counters), `out/ctrl-conn-Edge{1..4}.json`,
`out/device-templates.json`. All values read via operator API, 2026-10-27.

## Manager01 — vManage (management plane)
- Single NMS: config, monitoring, the dataservice API. All 6 other devices report `connectedVManages: [100.0.0.1]`.
- Site 100 (`SITE_100`), system-ip **100.0.0.1**, domain-id 0, model `vmanage`, x86_64, **10 vCPU** (runs the microservice fleet — largest box).
- Version **20.18.2.1**. Cert Valid. 6 inbound DTLS control conns (4 edges + vSmart + vBond). DTLS listener 12546.
- `controller_basic` template group exists but is attached to vSmart, not vManage. No device groups.

## Controller01 — vSmart (control plane)
- The only route/policy computer: OMP terminates here, routes reflect between edges, policy pushes from here. Single instance — no vSmart redundancy (sandbox economy); if it dies, the overlay stops learning.
- Site 100, system-ip **100.0.0.101**, domain-id 1, 2 vCPU, version **20.18.2.1**, cert Valid.
- `ompPeers = 4` (exactly the four edges); 11 inbound control conns. DTLS 12346 (Edge4 reaches it on 12446 — different NAT path).
- **The only template attachment in the sandbox**: `controller_basic` (1 device attached).

## Validator01 — vBond (orchestration)
- Introducer/authenticator: devices orchlocate here first; it validates certs and introduces edges↔vSmart so DTLS forms. Carries no routes, no data.
- Site 100, system-ip **100.0.0.201**, model `vedge-cloud`, 2 vCPU, version **20.18.2.1**, cert Valid.
- No domain-id, `ompPeers = None` (vBond is out of OMP by design). 18 inbound control conns = the whole fabric keeping its vBond session.

## Edge1–Edge4 — Cisco Catalyst 8000V vEdges (sites 1–4)
Same design four times — a "one site template, four copies" teaching fabric.
- IOS-XE vEdge (`vedge-C8000V`, not vEdge-OS), x86_64, 4 vCPU, site-ids 1–4, system-ips **10.0.0.1–4**, domain-id 1, TZ UTC.
- Version **17.18.01a.0.182** — legacy train vs the 20.18.2.1 controllers. A real network would run the firmware-install action (`POST /dataservice/device/action/install/devices/vedge?groupId=all` exists here — but it's a write → operator gets 403).
- **Tunnel config**: 2 WAN colors per edge — `mpls` + `biz-internet`, encapsulation `dia` (single-diamond). 3 DTLS sessions per edge: 2× vSmart (one per color → either WAN can fail with control intact) + 1× vManage. **BFD 6/6 up** = 2 colors × 3 peers, every path live.
- Per-edge color nuance (from ctrl-conn dumps): Edge3's vManage session rides `mpls` (peer port 12946); Edge4 uses vSmart port 12446 / vManage 12846 — the 172.16.0.0/24 underlay is genuinely asymmetric per site, not a clone.

| Edge | site | system-ip | vsmart/mpls | vsmart/biz-internet | vmanage (color, port) |
|---|---|---|---|---|---|
| Edge1 | 1 | 10.0.0.1 | up :12346 | up :12346 | biz-internet :12546 |
| Edge2 | 2 | 10.0.0.2 | up :12346 | up :12346 | biz-internet :12546 |
| Edge3 | 3 | 10.0.0.3 | up :12346 | up :12346 | **mpls :12946** |
| Edge4 | 4 | 10.0.0.4 | up **:12446** | up **:12446** | biz-internet :12846 |

## Config-source reality
- `edge_basic` device template: 0 devices attached → **edges are effectively CLI-managed** (consistent with `template/config/attached/{uuid}` → "No config available").
- Policy posture is minimal: 33 lists (22 app, 8 SLA, 3 local-app), 0 ACL definitions, 0 mesh definitions.

## One-sentence architecture
Four CLI-configured dual-WAN C8000V edges around a singleton vManage/vSmart/vBond trio co-located at "site 100" (SF Bay geo), every control path duplicated across both colors, zero policy complexity — a deliberately minimal, fully-green teaching fabric where the interesting constraint is the operator-role API wall, not the network.
