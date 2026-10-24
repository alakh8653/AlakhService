#!/bin/sh
# Entrypoint of the alertmanager container. Alertmanager does not expand environment variables,
# so this writes /tmp/alertmanager.yml from them:
#   ALERT_EMAIL_TO + SMTP_HOST/SMTP_PORT/SMTP_USERNAME/SMTP_PASSWORD/SMTP_FROM_EMAIL  -> email
#   TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID                                            -> Telegram
# Either, both or neither (then alerts are only visible in Grafana / Prometheus).
# Usage outside the container (to test): OUT=/tmp/am.yml sh render-and-start.sh --render-only
set -eu

out=${OUT:-/tmp/alertmanager.yml}
umask 077

# YAML single-quoted string: double any single quote.
q() { printf "'%s'" "$(printf '%s' "$1" | sed "s/'/''/g")"; }

email=""
telegram=""
[ -n "${ALERT_EMAIL_TO:-}" ] && [ -n "${SMTP_HOST:-}" ] && email=1
[ -n "${TELEGRAM_BOT_TOKEN:-}" ] && [ -n "${TELEGRAM_CHAT_ID:-}" ] && telegram=1

{
  echo "# Generated at container start by render-and-start.sh; edit that script, not this file."
  echo "global:"
  echo "  resolve_timeout: 5m"
  if [ -n "$email" ]; then
    echo "  smtp_smarthost: $(q "${SMTP_HOST}:${SMTP_PORT:-587}")"
    echo "  smtp_from: $(q "${SMTP_FROM_EMAIL:-$SMTP_USERNAME}")"
    echo "  smtp_auth_username: $(q "${SMTP_USERNAME:-}")"
    echo "  smtp_auth_password: $(q "${SMTP_PASSWORD:-}")"
    echo "  smtp_require_tls: true"
  fi
  echo "route:"
  echo "  receiver: owner"
  echo "  group_by: [alertname, service, upstream]"
  echo "  group_wait: 30s"
  echo "  group_interval: 5m"
  echo "  repeat_interval: 4h"
  echo "receivers:"
  echo "  - name: owner"
  if [ -n "$email" ]; then
    echo "    email_configs:"
    echo "      - to: $(q "$ALERT_EMAIL_TO")"
    echo "        send_resolved: true"
  fi
  if [ -n "$telegram" ]; then
    echo "    telegram_configs:"
    echo "      - bot_token: $(q "$TELEGRAM_BOT_TOKEN")"
    echo "        chat_id: ${TELEGRAM_CHAT_ID}"
    echo "        send_resolved: true"
  fi
} > "$out"

if [ -z "$email" ] && [ -z "$telegram" ]; then
  echo "alertmanager: no ALERT_EMAIL_TO/SMTP_HOST or TELEGRAM_* set; alerts will not be sent anywhere" >&2
fi

[ "${1:-}" = "--render-only" ] && exit 0

exec /bin/alertmanager \
  --config.file="$out" \
  --storage.path=/alertmanager \
  "$@"
