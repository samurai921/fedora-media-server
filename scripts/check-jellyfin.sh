#!/usr/bin/env bash
set -euo pipefail
if [[ $# -gt 1 || ( $# -eq 1 && "$1" != --gpu ) ]]; then
  echo "Usage: bash scripts/check-jellyfin.sh [--gpu]" >&2
  exit 2
fi
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
public_url="${JELLYFIN_PUBLIC_URL:-https://jellyfin.mediadima.ru}"
docker compose config -q
docker compose ps jellyfin
systemctl is-active docker.service xray-jellyfin-client.service
systemctl is-enabled docker.service xray-jellyfin-client.service
for url in "http://127.0.0.1:8096/health" "${public_url%/}/health"; do
  status="$(curl --silent --show-error --fail --connect-timeout 5 --max-time 15 --output /dev/null --write-out '%{http_code}' "$url")"
  [[ "$status" == 200 ]] || { echo "Unexpected HTTP $status: $url" >&2; exit 1; }
  printf 'OK HTTP %s: %s\n' "$status" "$url"
done
if [[ "${1:-}" == --gpu ]]; then
  docker compose exec -T -u abc jellyfin nvidia-smi --query-gpu=name,driver_version --format=csv,noheader
  docker compose exec -T -u abc jellyfin /usr/lib/jellyfin-ffmpeg/ffmpeg \
    -hide_banner -loglevel error -f lavfi -i testsrc2=size=1280x720:rate=30 \
    -t 2 -c:v h264_nvenc -f null -
  echo 'OK NVIDIA NVENC (synthetic H.264 test)'
fi
