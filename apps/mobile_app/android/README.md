# Android Build Configuration

## SDK Versions

| Setting          | Value |
|------------------|-------|
| `minSdkVersion`  | 21    |
| `targetSdkVersion` | 34  |
| `compileSdkVersion` | 34 |

## Required Permissions (`AndroidManifest.xml`)

```xml
<uses-permission android:name="android.permission.INTERNET" />
<uses-permission android:name="android.permission.ACCESS_FINE_LOCATION" />
<uses-permission android:name="android.permission.ACCESS_COARSE_LOCATION" />
<uses-permission android:name="android.permission.CAMERA" />
<uses-permission android:name="android.permission.READ_EXTERNAL_STORAGE" />
<uses-permission android:name="android.permission.USE_BIOMETRIC" />
<uses-permission android:name="android.permission.USE_FINGERPRINT" />
<uses-permission android:name="android.permission.VIBRATE" />
<uses-permission android:name="android.permission.RECEIVE_BOOT_COMPLETED" />
```

## Google Maps API Key

Add your key inside `android/app/src/main/AndroidManifest.xml`:

```xml
<meta-data
    android:name="com.google.android.geo.API_KEY"
    android:value="YOUR_GOOGLE_MAPS_API_KEY" />
```

Also set it in `android/local.properties`:

```
GOOGLE_MAPS_API_KEY=your-google-maps-api-key
```

## ProGuard / R8

ProGuard rules are pre-configured in `android/app/proguard-rules.pro`.
Ensure `minifyEnabled` is `true` for release builds.

## Release Build

```bash
flutter build apk --release
# or
flutter build appbundle --release
```
