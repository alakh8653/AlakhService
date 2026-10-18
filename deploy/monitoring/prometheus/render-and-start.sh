#!/bin/sh
# Entrypoint of the prometheus container: Prometheus does not expand environment variables in
# its config, so fill in the domain and put the gateway's metrics token in a file it can read.
set -eu
: "${DOMAIN:?DOMAIN is not set}"
: "${METRICS_TOKEN:?METRICS_TOKEN is not set}"
umask 077
printf '%s' "$METRICS_TOKEN" > /tmp/metrics_token
sed "s/__DOMAIN__/${DOMAIN}/g" /etc/prometheus/prometheus.yml > /tmp/prometheus.yml
exec /bin/prometheus \
  --config.file=/tmp/prometheus.yml \
  --storage.tsdb.path=/prometheus \
  --storage.tsdb.retention.time=15d \
  --storage.tsdb.retention.size=2GB \
  "$@"
