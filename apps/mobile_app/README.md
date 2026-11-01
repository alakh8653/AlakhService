# AlakhService Mobile App

Enterprise-grade on-demand service booking application built with Flutter.

## Prerequisites

- Flutter SDK **3.10+** (Dart 3.0+)
- Android Studio / Xcode for platform builds
- A running instance of the AlakhService backend

## Setup

```bash
# Clone and navigate
git clone https://github.com/your-org/AlakhService.git
cd apps/mobile_app

# Install dependencies
flutter pub get

# Run code generation
dart run build_runner build --delete-conflicting-outputs

# Start the app against your API gateway (defaults to https://api.alakhservice.com).
# On the Android emulator the host machine is 10.0.2.2.
flutter run --dart-define=API_BASE_URL=http://10.0.2.2:3000
```

All requests go through the API gateway under `/api/v1`. The access and refresh tokens are kept in the
platform keystore; an expired access token is refreshed once and the request retried, and if the refresh
token is rejected the app returns to the sign-in screen.

Live tracking needs a Google Maps key: set `GOOGLE_MAPS_API_KEY` in `android/local.properties` or the
environment.

For local development, `make dev` starts auth_service with `LOG_OTP_CODES=true`, so sign-up and
password-reset codes appear in `docker compose logs auth_service` instead of needing an SMS provider
(MSG91 or Twilio).

## Architecture

The app follows **Clean Architecture** with the **BLoC** pattern:

```
lib/
├── core/               # Shared infrastructure (DI, network, theme, errors)
├── features/           # Feature modules (auth, services, booking, ...)
│   └── <feature>/
│       ├── data/       # Models, data sources, repository implementations
│       ├── domain/     # Entities, repository interfaces, use cases
│       └── presentation/ # BLoC, pages, widgets
├── shared/             # Reusable widgets and utilities
├── offline/            # Offline sync & caching
└── security/           # Encryption, secure storage, biometrics
```

## Features

- 🔐 Sign-up by phone with an SMS code; sign-in by phone or email; password reset by SMS code
- 🔎 Service catalogue browsing and search
- 📅 Booking, booking history and cancellation
- 📍 Live provider location while a booking is in progress (Google Maps)
- 💳 Payment for confirmed bookings: Razorpay checkout (UPI, cards, net banking) or cash. The server prices
  the booking, opens the Razorpay order and only counts the payment once Razorpay's signature verifies.
  Online payments need `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET` and `RAZORPAY_WEBHOOK_SECRET` on payment_service;
  without them the app offers cash only
- ⭐ Rating the shop after a completed booking
- 🧰 Provider mode: anyone a shop has assigned a job to gets a **Jobs** tab to move each job along
  (on the way → started → completed). While a job is under way the app shares the provider's location
  with that customer (foreground only, every 15 s); it stops when the job is done
- 📊 Joining a walk-in queue and watching your position
- 🔔 In-app notifications, and push notifications through Firebase Cloud Messaging (see below)
- 💬 A chat with the shop on each booking (contact details are hidden; masked calls when enabled)
- 🔗 App links: `https://{domain}/b/{booking_id}` opens the booking, `/reset-password?token=...` the reset screen
- 👤 Profile editing
- 🌙 Dark / Light theme support

## Release configuration (fill in before publishing)

| What | Where | Without it |
|---|---|---|
| Firebase (push) | `android/app/google-services.json` and `ios/Runner/GoogleService-Info.plist` (add the plist to the Runner target in Xcode), both from the Firebase console for `com.alakhservice.alakh_service`. iOS also needs an APNs key uploaded to Firebase and the Push Notifications capability. | The app runs normally without push; Gradle applies the google-services plugin only when the JSON exists. |
| App-link domain | `APP_LINK_DOMAIN` in `app_links.xcconfig` (the one place for Android and iOS), plus `--dart-define=APP_LINK_DOMAIN=...` if it is not the placeholder `alakhservice.in`. The site must serve `/.well-known/assetlinks.json` with the release key's SHA-256 fingerprint and `/.well-known/apple-app-site-association` with the Team ID. | Links open in the browser instead of the app. |
| Legal pages | `--dart-define=LEGAL_BASE_URL=https://...` (placeholder `https://alakhservice.in`); the server's `GET /api/v1/legal/current` links win when it answers. | The placeholder links. |
| Support contact | `--dart-define=SUPPORT_EMAIL=... --dart-define=SUPPORT_PHONE=...` | Placeholders. |
| Release signing | `android/key.properties` or `ANDROID_KEYSTORE_*` (see `android/README.md`); iOS team and profiles in Xcode. | Debug-signed, not uploadable. |

The Android `applicationId` `com.alakhservice.alakh_service` (and the iOS bundle id) is **permanent once the
first build is uploaded to Google Play**: it cannot be changed afterwards without publishing a new app.

The app icon and splash come from `tool/make_brand_assets.py` (`assets/branding/`); regenerate the platform
files with `dart run flutter_launcher_icons` and `dart run flutter_native_splash:create`.

## Running Tests

```bash
flutter test
```
