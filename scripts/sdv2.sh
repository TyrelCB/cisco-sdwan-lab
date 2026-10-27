#!/usr/bin/env bash
# Authenticated call to the Catalyst SD-WAN sandbox vManage dataservice API.
# Usage: sdv2.sh GET /dataservice/system/status
#        sdv2.sh POST /dataservice/device/cli '{"deviceType":"c8000v","command":"show version","deviceId":["10.0.0.1"]}'
#        sdv2.sh REAUTH     # force re-login
HOST=sandbox-sdwan-2.cisco.com
USER=devnetuser
PASS="${SDWAN_PASS:-RG!_Yw919_83}"
JAR="${SDWAN_JAR:-/tmp/sdv2_cookies.txt}"

reauth() {
  rm -f "$JAR"
  curl -s -k -c "$JAR" -X POST "https://$HOST/j_security_check" \
    --data-urlencode "j_username=$USER" --data-urlencode "j_password=$PASS" -o /dev/null
}

method=$1; path=$2; body=$3
[ "$method" = "REAUTH" ] && { reauth; echo reauthed; exit 0; }

get_token() { curl -s -k -b "$JAR" -c "$JAR" "https://$HOST/dataservice/client/token"; }
token=$(get_token)
# token is a 64-256 char hex string; anything else (login HTML) means dead session
if ! [[ "$token" =~ ^[0-9A-F]{64,256}$ ]]; then reauth; token=$(get_token); fi
if ! [[ "$token" =~ ^[0-9A-F]{64,256}$ ]]; then echo "auth failed: token endpoint returned non-hex" >&2; exit 1; fi

args=(-s -k -b "$JAR" -c "$JAR" -X "$method" -H "X-XSRF-TOKEN: $token")
[ -n "$body" ] && args+=(-H 'Content-Type: application/json' -d "$body")
curl "${args[@]}" "https://$HOST$path"
