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

### Signing

`app/build.gradle.kts` signs release builds with a release keystore when one is configured, and
falls back to the debug key (with a build warning) when it is not. Debug-signed builds are fine
for testing but cannot be uploaded to Google Play.

1. Create a keystore once and keep it (and its passwords) somewhere safe. Losing it means you can
   no longer update the app:

   ```bash
   keytool -genkey -v -keystore ~/alakh-upload.jks -keyalg RSA -keysize 2048 \
     -validity 10000 -alias upload
   ```

2. Locally, create `android/key.properties` (git-ignored, as are `*.jks` and `*.keystore`):

   ```properties
   storeFile=/home/you/alakh-upload.jks
   storePassword=...
   keyAlias=upload
   keyPassword=...
   ```

   A relative `storeFile` is resolved against `android/app`.

3. In CI, set the same values as environment variables instead: `ANDROID_KEYSTORE_PATH`,
   `ANDROID_KEYSTORE_PASSWORD`, `ANDROID_KEY_ALIAS` and `ANDROID_KEY_PASSWORD`. The Mobile CI
   workflow does this from the repository secrets `ANDROID_KEYSTORE_BASE64`
   (`base64 -w0 alakh-upload.jks`), `ANDROID_KEYSTORE_PASSWORD`, `ANDROID_KEY_ALIAS` and
   `ANDROID_KEY_PASSWORD`. When the secrets are absent (forks, or before they are added) the
   APK is debug-signed.

Values in `key.properties` take precedence over the environment. All four must be set for the
release key to be used.
