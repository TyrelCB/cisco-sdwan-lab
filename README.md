# Cisco Catalyst SD-WAN Always-On Lab

Live session against the DevNet Catalyst SD-WAN sandbox (sandbox-sdwan-2.cisco.com), 2026-10-27.

![Topology](diagrams/sdwan-overview.png)

## Fabric

| Host | Role | Site | System-IP | Version |
|---|---|---|---|---|
| Manager01 | vManage | 100 | 100.0.0.1 | 20.18.2.1 |
| Controller01 | vSmart | 100 | 100.0.0.101 | 20.18.2.1 |
| Validator01 | vBond | 100 | 100.0.0.201 | 20.18.2.1 |
| Edge1–Edge4 | vEdge C8000V | 1–4 | 10.0.0.1–4 | 17.18.1a |

All edges: BFD 6/6 up, 3 control connections, OMP up.

## Notes
- docs/api-notes.md — auth flow + endpoint findings
- docs/device-breakdown.md — per-device role/configuration breakdown
- scripts/sdv2.sh — helper for authenticated API calls

## What the API session found (2026-10-27)

- **Auth**: `j_security_check` → CSRF token → `X-XSRF-TOKEN` header. See `docs/api-notes.md`.
- **Fabric health**: `/dataservice/network/status` — vSmart 1/1, vBond 1/1, vEdge 4/4 all *normal*, zero warnings/errors. Every edge shows BFD 6/6 up and 3 DTLS control connections (2× vSmart over both tunnel colors + 1× vManage).
- **Templates**: 142 feature templates, 19 device-template groups (`edge_basic`, `controller_basic`, factory default sets for ISR/C1111/vEdge/SDBranch/cloud ICGWs).
- **Policy**: 33 policy lists (22 app, 8 SLA-class, 3 local-app), 0 ACL definitions, 0 mesh defs — the sandbox ships a minimal policy posture.
- **Role limit**: `devnetuser` = **operator** group. All reads work; template/policy writes and the CLI-runner microservice return **403 "Access forbidden: role not allowed"**. The template-push demo is therefore documented but not executed (see api-notes for the exact request that 403s).
- **Endpoint discovery**: the SPA's lazy JS chunks carry the full endpoint table — recipe in `docs/api-notes.md`.

## Layout
- `diagrams/sdwan-overview.svg|png` — architecture diagram (hand-authored SVG)
- `docs/api-notes.md` — verified endpoints, gotchas, discovery method
- `scripts/sdv2.sh` — authenticated API caller (auto-reauth)
- `out/` — captured API evidence (inventory, BFD, control conns, templates, policy lists)
