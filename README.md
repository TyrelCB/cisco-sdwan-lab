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
- scripts/sdv2.sh — helper for authenticated API calls
