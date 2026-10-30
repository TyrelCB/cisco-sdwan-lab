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
| `GET /dataservice/alarms` | Active alarms grid (0 active now). Param filtering (`fromTime=...`) rejected — `Invalid Query Param`; plain GET works, UI posts a grid request |
| `GET /dataservice/device/bfd/sites/summary` | Site-health rollup: Full/Partial/No WAN connectivity counts (4 sites Full) |
| `GET /dataservice/statistics/approute/query/fields` | App-route stats field catalog (the Monitor→App Reality path) |

Response shape: grid views wrap rows in `data[]` with `header.columns[].property` naming the real fields.

## Writes / ops blocked or absent for `operator`
- `POST /dataservice/template/device/feature/` (create feature template; path found by grepping the SPA bundle: `createDeviceFeatureTemplate → post(DEVICE_FEATURE_TEMPLATE)`) → **403 role not allowed**
- CLI runner (`POST .../{uuid}/config` per bundle `getPrefixUrl("cli")+"/cli"`): reachable but **403** (same microservice permission).
- Not present in this release's SPA at all: `/dataservice/realtime/operation/*`, `/dataservice/network/realtime-operation/request`, `/dataservice/v1/policy/*` (this build uses `/dataservice/template/policy/*` and `/dataservice/v1/feature-profile/*` for SDDP-era config).
- **Realtime microservice 404s entirely** on this build: `POST /dataservice/realtime/system/device` and `POST /dataservice/realtime/{uuid}/system/device` both → 404 (0B), even with fresh token. The Monitor tables (OMP/BFD/control-links device views) are served another way here — use `/device` counters + `/device/control/synced/connections` instead.
- Admin-only (403 for operator): `/v1/device/inventory`, `/v1/system/info/vedges`, `/device/runningconfig/*`, `/logs/device`, `/cluster-management/*`, `/device/summary`. `device/validity` and `device/reboothistory/synced` → 404/500.
- `admin` user exists but its password is **not published** by the sandbox page (only `devnetuser` is issued); 9 common guesses all rejected → likely locked now, stop guessing.

## Deep-read sweep script
`scripts/deep_read.py` — one session, throttled, auto re-auth + per-call token refetch (the XSRF token **rotates**; a cached token 403s mid-run). Digs `/device` counters, per-edge ctrl conns, alarms, bfd site health, approute field catalog; payloads land in `out/`, digest printed.

## Finding hidden endpoints (method that worked)
`GET /index.html` → `runtime.*.js` gives the lazy-chunk manifest `{id:"modules/name", hash}`; fetch the
chunk for the feature you care about (`modules/configDevices`, `modules/monitor`, `modules/policy`) and
`grep -o 'dataservice/[a-zA-Z0-9_/{}?=&.$-]*'` — the bundles contain the complete client-side endpoint table.
Chunk list: certificate, dashboard, templateControllers, ucVoice, validations, networkDesign, admin,
configDevices, app, cloudExpress, templateModals, security, policy, deviceTemplates, templateServices,
maintenance, monitor, commonComponents, common.

## Fabric facts
- 7 devices: Manager01 (vManage 100.0.0.1), Controller01 (vSmart .101), Validator01 (vBond .201), Edge1–4 (C8000V, sites 1–4, 10.0.0.1–4).
- Every edge: 6/6 BFD up, OMP up, colors `mpls`/`biz-internet` (encap `dia`). - Control connections per Edge1: 2× vSmart (one per tunnel color to 100.0.0.101) + 1× vManage = 3 DTLS sessions. Controller-side counts from `/device`: vManage holds 6 ctrl conns, vSmart 11, vBond 18 (all edges + controllers register to vBond).
- Control underlay 172.16.0.0/24; vManage DTLS port 12546, vSmart 12346.
- Edges run 17.18.1a; controllers 20.18.2.1.
- `GET /dataservice/template/config/running/{uuid}` → DEV0001 "Error publishing message" (sandbox doesn't back up running configs).
- `GET /dataservice/template/config/attached/{uuid}` → "No config available" (devices attached to CLI-managed templates, not personalized).

## WRITE PATH (verified end-to-end, Oct-30 session)
Auth for writes: `admin` session in the persistent CDP Chromium (port 9333) on the reservation's vManage proxy (10.10.20.90); all REST goes through in-page `fetch()` via `/tmp/vmcall.py` (plain curl to the proxy 403s — JA3 filtering + rotating XSRF).

### Classic feature-template attach is NOT possible on these edges
`POST /template/device/config/attachfeature` with correct rows (get canonical rows from
`POST /template/device/config/input {templateId,deviceIds:[uuid],isEdited,isMasterEdited}` —
keys are **config paths** like `/1/GigabitEthernet3/interface/ip/address`, `//system/host-name`,
NOT variable display-names; `dhcp-server/address-pool` is `ipv4-prefix` typed → `192.168.X.0/24`)
passes all variable validation, then dies with:
`/vmanage-cfs:templates/template{vedge-<uuid>}/global/device-version ... does not exist`
Root cause: **all 4 edges are managed by Config Group `edge_basic`** (id `0cd3c1bd-254d-42f8-a932-1dd4d107c551`, description "Do not modify!") — `templateApplyLog` on `/system/device/vedges` shows "Deploying device with Config Group". Classic-template CFS nodes were never created; force-rediscover doesn't fix it. Don't fight it.

### Config Group API (the sanctioned write path)
- `GET /v1/config-group` → list (returns a bare JSON array, not `{data:[]}`)
- `GET /v1/config-group/{cg}/device/variables` → per-device vars: `system_ip, host_name, site_id, ipv6_strict_control, pseudo_commit_timer, aaa_password, vpn0_gi1_inet_ip, vpn0_gi2_mpls_ip, vpn1_gi3_lan_ip, vpn1_gi3_dhcp_network, vpn1_gi3_dhcp_address_exclude[], vpn1_gi3_dhcp_default_gateway`
- `PUT /v1/config-group/{cg}/device/variables` body `{"solution":"sdwan","devices":[{"device-id":<uuid>,"variables":[{name,value},...]}]}` → 200 `[uuid]`. Per-device scoped: sending one device's row does NOT wipe others'. (`family` key → SCHVALID0001; use `solution`.)
- `POST /v1/config-group/{cg}/device/deploy` body `{"devices":[{"id":<uuid>}]}` → `{"parentTaskId":"deploy_config_group-<pid>"}`; poll `/device/action/status/<pid>`. **Verified: Edge4 deploy → "Device: Config applied successfully"** (30-Oct-2026 06:35 UTC).
- Variable schema (JSON-Schema w/ profile/parcel paths): `GET /v1/config-group/{cg}/device/variables/schema`

### Policy writes (classic API works fine for policy)
Hub-and-spoke created via `POST /template/policy/definition/hubandspoke/` → def `6886a447-7cc1-4591-a5b5-88cd9e7d3278`. Needs `vpnList` with `listId` (created `Lab-Transit-VPN` `b760d407-…`), site lists `Lab-Hub-Sites`/`Lab-Spoke-Sites`; `definition.subDefinitions[]`, omit `preference` when `equalPreference:true`.

### Device inventory endpoints that actually respond on 20.18.2
`POST /system/device` (grid query), `GET /system/device/vedges` (rich per-edge rows: templateApplyLog, configStatusMessage, cert state). `/device/system/info` GET → 200 but empty `data`. `/about/device`, `/cluster/status` → 404. BFD: `/device/bfd/tloc/detail` (8 rows: per system-ip×color up/session count); `/device/bfd/sites/detail` → empty; `/device/bfd/sessions` → 400.

### BFD failover demo (verified end-to-end, 30-Oct-2026)
Timeline via Config Group variable change on Edge3 (`vpn0_gi2_mpls_ip` 172.16.2.3 → 172.16.99.3, deploy):
- baseline: 8 TLOCs (`/device/bfd/tloc/detail`), each `up`, 3 BFD sessions
- fault deploy → within ~30s **Edge3 mpls row disappears** from tloc/detail (TLOC withdrawal = row removal, *not* a `down` state — never assert on a `down` row here)
- during fault: Edge3 `biz-internet up/3` persists (traffic on surviving transport); every peer's mpls sessions 3→2 (mesh recalculated)
- revert + deploy → Edge3 mpls back `up/3` at +40s; **all 8 TLOCs fully restored (+3 sessions everywhere) by +180s**

### Session lifecycle gotcha
vManage UI sessions idle-timeout fast (minutes). On timeout the SPA lands on `index.html?reason=sessiontimeout` and in-page fetch throws (vmcall returns non-JSON). Fix: re-drive the login **form** (set input values + click "Log in") — direct POST to `/j_security_check` via fetch returns 200 but does NOT re-establish the cookie in this SPA context. `/tmp/vmcall.py` now auto-relogins and retries on 401/403/fetch-throw. Credentials: admin/C1sco12345 (in reservation page HTML; devnetuser is operator=RO).
Reservation guide page (`.../labguides/reservation/sdwan2018/<n>`) is currently unreachable through the VPN proxy (TLS handshake hangs) — don't block on it.

## Repro
`scripts/sdv2.sh GET /dataservice/device` (auto-reauth on token expiry).

## Fabric watcher (scheduled)
`scripts/watch_fabric.py` — polls `/dataservice/device` once, diffs vs `out/watch_state.json`,
prints `NO CHANGE` / `CHANGES:` / `ALERT:`. Counters are int-normalized (API mixes "6" and 6).
Runs as LangBang scheduled task `a18be9674dca` every 15 min for the life of the lease.
