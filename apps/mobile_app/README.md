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

For local development, start auth_service with `LOG_OTP_CODES=true` to read sign-up and password-reset
codes from its log instead of configuring Twilio (`TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`,
`TWILIO_FROM_NUMBER`).

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
- 💳 Payment for confirmed bookings (the server prices the booking; gateway checkout is not yet integrated,
  so online payments are recorded as pending)
- ⭐ Rating the shop after a completed booking
- 📊 Joining a walk-in queue and watching your position
- 🔔 In-app notifications
- 👤 Profile editing
- 🌙 Dark / Light theme support

## Running Tests

```bash
flutter test
```
