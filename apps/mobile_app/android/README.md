# Android Build Configuration

Generated with `flutter create` (Flutter 3.47) and configured for AlakhService.

| Setting | Value |
|---|---|
| Application ID | `com.alakhservice.alakh_service` |
| `minSdk` | 24 (Flutter default; required by `flutter_secure_storage` 11) |
| `targetSdk` / `compileSdk` | Flutter defaults |
| Java | 17 |

## Permissions (`app/src/main/AndroidManifest.xml`)

`INTERNET`, `ACCESS_FINE_LOCATION`, `ACCESS_COARSE_LOCATION`, `CAMERA`, `USE_BIOMETRIC`,
`VIBRATE`, `POST_NOTIFICATIONS`, `RECEIVE_BOOT_COMPLETED`.

`MainActivity` extends `FlutterFragmentActivity`, which `local_auth` needs for the biometric prompt.

## Google Maps API Key

The manifest reads the key from a build placeholder. Provide it in `android/local.properties`
(git-ignored) or as an environment variable:

```
GOOGLE_MAPS_API_KEY=your-google-maps-api-key
```

## Release Build

```bash
flutter build apk --release
# or
flutter build appbundle --release
```

Release builds are currently signed with the debug key. Before publishing, create a release
keystore and a `key.properties` (both git-ignored) and add a `signingConfigs.release` block in
`app/build.gradle.kts`.
