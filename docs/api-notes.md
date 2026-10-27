# vManage dataservice API — field notes (sandbox-sdwan-2, 20.18.2)

## Auth (verified working)
1. `POST /j_security_check` form-encoded `j_username` / `j_password` → 200 + `content-length: 0` + fresh `JSESSIONID`. (Failed logins *also* return 200 — with the login page HTML. Check `content-length`.)
2. `GET /dataservice/client/token` → raw hex CSRF token (needs session cookie).
3. Every call: cookie jar **and** `X-XSRF-TOKEN: <token>` header. Stale token → `SessionTokenFilter: Token ... does not match`.
- `devnetuser` is in the **operator** group: reads OK, template/policy **writes → 403 "Access forbidden: role not allowed"**. Only `admin` exists besides it.

## Read endpoints that work (200)
| Endpoint | Returns |
|---|---|
| `GET /dataservice/device` | Full inventory: reachability, BFD up/total, ctrl conns, OMP, version, cert validity |
| `GET /dataservice/network/status` | Topology element status (vSmart/vManage/vBond/edges summary) |
| `GET /dataservice/template/feature` | 142 feature templates (factory + `edge_basic*`/`controller_basic*` sets) |
| `GET /dataservice/template/device` | 19 device-template groups (`devicesAttached`, feature count) |
| `GET /dataservice/template/policy/list` | 33 policy lists: 8 sla, 22 app, 3 localApp |
| `GET /dataservice/template/policy/definition/acl` | 0 (no ACL definitions) |
| `GET /dataservice/template/policy/definition/mesh` | 0 (no mesh defs) |
| `GET /dataservice/device/control/synced/connections?deviceId=<sysip>` | Per-edge DTLS control connections (peer-type, system-ip, ports) |
| `GET /dataservice/device/bfd/state/device/tloc?deviceId=<sysip>` | Per-device BFD color summary |
| `GET /dataservice/admin/user` | Users + groups (shows devnetuser=operator) |
| `GET /dataservice/statistics/system/query/fields` | Stats field metadata |
| `GET /dataservice/client/navigation` | SPA nav tree = capability map for this user |

Response shape: grid views wrap rows in `data[]` with `header.columns[].property` naming the real fields.

## Writes / ops blocked or absent for `operator`
- `POST /dataservice/template/device/feature/` (create feature template; path found by grepping the SPA bundle: `createDeviceFeatureTemplate → post(DEVICE_FEATURE_TEMPLATE)`) → **403 role not allowed**
- CLI runner (`POST .../{uuid}/config` per bundle `getPrefixUrl("cli")+"/cli"`): reachable but **403** (same microservice permission).
- Not present in this release's SPA at all: `/dataservice/realtime/operation/*`, `/dataservice/network/realtime-operation/request`, `/dataservice/v1/policy/*` (this build uses `/dataservice/template/policy/*` and `/dataservice/v1/feature-profile/*` for SDDP-era config).

## Finding hidden endpoints (method that worked)
`GET /index.html` → `runtime.*.js` gives the lazy-chunk manifest `{id:"modules/name", hash}`; fetch the
chunk for the feature you care about (`modules/configDevices`, `modules/monitor`, `modules/policy`) and
`grep -o 'dataservice/[a-zA-Z0-9_/{}?=&.$-]*'` — the bundles contain the complete client-side endpoint table.
Chunk list: certificate, dashboard, templateControllers, ucVoice, validations, networkDesign, admin,
configDevices, app, cloudExpress, templateModals, security, policy, deviceTemplates, templateServices,
maintenance, monitor, commonComponents, common.

## Fabric facts
- 7 devices: Manager01 (vManage 100.0.0.1), Controller01 (vSmart .101), Validator01 (vBond .201), Edge1–4 (C8000V, sites 1–4, 10.0.0.1–4).
- Every edge: 6/6 BFD up, OMP up, colors `mpls`/`biz-internet` (encap `dia`). Control connections per Edge1: 2× vSmart (one per tunnel color to 100.0.0.101) + 1× vManage = 3 DTLS sessions.
- Control underlay 172.16.0.0/24; vManage DTLS port 12546, vSmart 12346.
- Edges run 17.18.1a; controllers 20.18.2.1.
- `GET /dataservice/template/config/running/{uuid}` → DEV0001 "Error publishing message" (sandbox doesn't back up running configs).
- `GET /dataservice/template/config/attached/{uuid}` → "No config available" (devices attached to CLI-managed templates, not personalized).

## Repro
`scripts/sdv2.sh GET /dataservice/device` (auto-reauth on token expiry).
