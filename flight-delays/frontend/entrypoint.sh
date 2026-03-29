#!/bin/sh
set -e

PORT_VAL="${PORT:-80}"

if [ -z "$API_UPSTREAM" ]; then
  echo "ERROR: API_UPSTREAM is not set." >&2
  echo "Set it in Railway (or Docker) to your FastAPI service base URL with no trailing slash," >&2
  echo "e.g. https://your-backend-service.up.railway.app" >&2
  echo "Use the public HTTPS URL unless both services share a private network." >&2
  exit 1
fi

sed "s/__PORT__/${PORT_VAL}/g" /etc/nginx/nginx.conf.template \
  | sed "s|__API_UPSTREAM__|${API_UPSTREAM}|g" \
  > /etc/nginx/nginx.conf

exec nginx -g 'daemon off;'
