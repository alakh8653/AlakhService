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

# Copy environment config
cp .env.example .env
# Edit .env with your actual keys

# Run code generation
flutter pub run build_runner build --delete-conflicting-outputs

# Start the app
flutter run
```

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

- 🔐 Phone-based authentication with OTP verification
- 📍 Real-time service provider tracking (Google Maps)
- 📅 Service booking and scheduling
- 💳 Integrated payment flow
- 🔔 Push notifications
- 📊 Queue status monitoring
- 👤 User & provider profile management
- 🌙 Dark / Light theme support
- 🔒 Biometric authentication
- 📶 Offline support with sync queue

## Running Tests

```bash
flutter test
```
