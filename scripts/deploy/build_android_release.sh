#!/usr/bin/env bash
# Build the Android release (Play Store .aab, or an .apk for testers) and refuse to build one
# that would ship with placeholder settings or the debug signing key.
#
#   scripts/deploy/build_android_release.sh          # app bundle for the Play Store
#   scripts/deploy/build_android_release.sh apk      # APK to install directly on phones
#
# Settings come from the environment, or from apps/mobile_app/release.env (git-ignored; copy
# apps/mobile_app/release.env.example). Signing comes from apps/mobile_app/android/key.properties
# or the ANDROID_KEYSTORE_* variables, exactly as android/app/build.gradle.kts reads them.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
APP="$ROOT/apps/mobile_app"
KIND="${1:-appbundle}"
case "$KIND" in
  appbundle | apk) ;;
  *) echo "usage: $0 [appbundle|apk]" >&2; exit 2 ;;
esac

if [ -f "$APP/release.env" ]; then
  # Values already in the environment win over the file.
  while IFS='=' read -r key value; do
    key="$(echo "$key" | tr -d '[:space:]')"
    case "$key" in '' | \#*) continue ;; esac
    value="$(echo "$value" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' -e 's/^"\(.*\)"$/\1/')"
    if [ -z "${!key:-}" ]; then export "$key=$value"; fi
  done < "$APP/release.env"
fi

errors=()
fail() { errors+=("$1"); }

for name in API_BASE_URL LEGAL_BASE_URL APP_LINK_DOMAIN SUPPORT_EMAIL SUPPORT_PHONE; do
  if [ -z "${!name:-}" ]; then fail "$name is not set"; fi
done

placeholder='example\.|changeme|your-?domain|<DOMAIN>|localhost|10\.0\.2\.2|127\.0\.0\.1'
for name in API_BASE_URL LEGAL_BASE_URL APP_LINK_DOMAIN SUPPORT_EMAIL; do
  value="${!name:-}"
  if [ -n "$value" ] && echo "$value" | grep -qiE "$placeholder"; then
    fail "$name looks like a placeholder or a dev address: $value"
  fi
done
for name in API_BASE_URL LEGAL_BASE_URL; do
  value="${!name:-}"
  if [ -n "$value" ] && [[ "$value" != https://* ]]; then fail "$name must start with https://: $value"; fi
done
if [ -n "${APP_LINK_DOMAIN:-}" ] && [[ "$APP_LINK_DOMAIN" == *://* || "$APP_LINK_DOMAIN" == */* ]]; then
  fail "APP_LINK_DOMAIN is a bare domain, without https:// or a path: $APP_LINK_DOMAIN"
fi
if [ -n "${SUPPORT_EMAIL:-}" ] && ! echo "$SUPPORT_EMAIL" | grep -qE '^[^@[:space:]]+@[^@[:space:]]+\.[^@[:space:]]+$'; then
  fail "SUPPORT_EMAIL is not an email address: $SUPPORT_EMAIL"
fi
if [ -n "${SUPPORT_PHONE:-}" ]; then
  if ! echo "$SUPPORT_PHONE" | grep -qE '^\+[0-9]{10,15}$'; then
    fail "SUPPORT_PHONE must be in international format with no spaces, e.g. +919876543210: $SUPPORT_PHONE"
  elif echo "$SUPPORT_PHONE" | grep -qE '^\+91?0+$|^\+[0-9]0{9,}$|1234567890'; then
    fail "SUPPORT_PHONE is a placeholder number: $SUPPORT_PHONE"
  fi
fi

# The app-link domain is also baked into the Android manifest and iOS entitlements from app_links.xcconfig.
xc_domain="$(sed -n 's/^[[:space:]]*APP_LINK_DOMAIN[[:space:]]*=[[:space:]]*\([^[:space:]]*\).*/\1/p' "$APP/app_links.xcconfig" | head -n1)"
if [ -n "${APP_LINK_DOMAIN:-}" ] && [ "$xc_domain" != "$APP_LINK_DOMAIN" ]; then
  fail "APP_LINK_DOMAIN ($APP_LINK_DOMAIN) differs from apps/mobile_app/app_links.xcconfig ($xc_domain); set the same domain in both"
fi

# Signing: the same sources, in the same order, as android/app/build.gradle.kts.
key_props="$APP/android/key.properties"
prop() { [ -f "$key_props" ] && sed -n "s/^[[:space:]]*$1[[:space:]]*=[[:space:]]*//p" "$key_props" | tail -n1 | sed 's/[[:space:]]*$//'; }
store_file="$(prop storeFile || true)"; store_file="${store_file:-${ANDROID_KEYSTORE_PATH:-}}"
store_pass="$(prop storePassword || true)"; store_pass="${store_pass:-${ANDROID_KEYSTORE_PASSWORD:-}}"
key_alias="$(prop keyAlias || true)"; key_alias="${key_alias:-${ANDROID_KEY_ALIAS:-}}"
key_pass="$(prop keyPassword || true)"; key_pass="${key_pass:-${ANDROID_KEY_PASSWORD:-}}"
if [ -z "$store_file" ] || [ -z "$store_pass" ] || [ -z "$key_alias" ] || [ -z "$key_pass" ]; then
  fail "no release signing key: create apps/mobile_app/android/key.properties (docs/DEPLOYMENT.md, \"Android release\")"
else
  # A relative storeFile resolves against android/app, as Gradle does.
  case "$store_file" in /*) store_path="$store_file" ;; ~*) store_path="${store_file/#\~/$HOME}" ;; *) store_path="$APP/android/app/$store_file" ;; esac
  if [ ! -f "$store_path" ]; then fail "the keystore file does not exist: $store_path"; fi
fi

if [ ${#errors[@]} -gt 0 ]; then
  echo "Refusing to build an Android release:" >&2
  for e in "${errors[@]}"; do echo "  - $e" >&2; done
  exit 1
fi

if [ -n "${CHECK_ONLY:-}" ]; then
  echo "Android release settings OK."
  exit 0
fi

version="$(sed -n 's/^version:[[:space:]]*//p' "$APP/pubspec.yaml")"
echo "Building $KIND $version for $API_BASE_URL (support $SUPPORT_EMAIL, $SUPPORT_PHONE)"
if [ -z "${GOOGLE_MAPS_API_KEY:-}" ] && ! grep -qs '^GOOGLE_MAPS_API_KEY=.' "$APP/android/local.properties"; then
  echo "Note: GOOGLE_MAPS_API_KEY is not set; maps will not load in this build." >&2
fi

cd "$APP"
flutter pub get
flutter build "$KIND" --release \
  "--dart-define=API_BASE_URL=$API_BASE_URL" \
  "--dart-define=LEGAL_BASE_URL=$LEGAL_BASE_URL" \
  "--dart-define=APP_LINK_DOMAIN=$APP_LINK_DOMAIN" \
  "--dart-define=SUPPORT_EMAIL=$SUPPORT_EMAIL" \
  "--dart-define=SUPPORT_PHONE=$SUPPORT_PHONE"

if [ "$KIND" = appbundle ]; then
  echo "Done: apps/mobile_app/build/app/outputs/bundle/release/app-release.aab (upload this to Play)"
else
  echo "Done: apps/mobile_app/build/app/outputs/flutter-apk/app-release.apk"
fi
echo "Next upload: raise version: in apps/mobile_app/pubspec.yaml first (the number after + must go up)."
