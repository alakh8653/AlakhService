# Caddy reverse proxy with both web dashboards and the public site (deploy/site) built in as static files.
# Built by docker-compose.prod.yml (context: repository root). The API address is baked into the
# JavaScript at build time, so changing DOMAIN means rebuilding this image (deploy.sh does).

FROM node:22-alpine AS shop
WORKDIR /app
COPY apps/shop_dashboard_web/package.json apps/shop_dashboard_web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY apps/shop_dashboard_web/ ./
ARG API_BASE_URL
# The public site, for the Terms/Privacy/Grievance links (they are not pages of the dashboard).
ARG SITE_URL
RUN test -n "$API_BASE_URL" && test -n "$SITE_URL" && VITE_API_BASE_URL="$API_BASE_URL" VITE_SITE_URL="$SITE_URL" npm run build

FROM node:22-alpine AS admin
WORKDIR /app
COPY apps/admin_dashboard_web/package.json apps/admin_dashboard_web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY apps/admin_dashboard_web/ ./
ARG API_BASE_URL
RUN test -n "$API_BASE_URL" && VITE_API_BASE_URL="$API_BASE_URL" npm run build

FROM caddy:2.10-alpine
COPY --from=shop /app/dist /srv/shop
COPY --from=admin /app/dist /srv/admin
# The Caddyfile is mounted from deploy/Caddyfile so it can be edited without a rebuild;
# this copy is only a fallback.
COPY deploy/Caddyfile /etc/caddy/Caddyfile
# The public site (legal pages, account deletion, app links); also mounted from deploy/site.
COPY deploy/site /srv/site
