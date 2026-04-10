# AlakhService Mobile

Flutter mobile app for the AlakhService on-demand home services platform.

## Architecture
Clean Architecture with BLoC state management.
- **domain**: Entities, repositories (abstract), use cases
- **data**: Models, remote/local data sources, repository implementations
- **presentation**: BLoC, pages, widgets

## Setup
```bash
cp .env.example .env   # fill in your values
flutter pub get
flutter run
```

## Key Dependencies
| Package | Purpose |
|---|---|
| flutter_bloc | State management |
| go_router | Navigation |
| get_it | Dependency injection |
| dio | HTTP client |
| dartz | Either/functional patterns |
| equatable | Value equality |
| shared_preferences | Local storage |
