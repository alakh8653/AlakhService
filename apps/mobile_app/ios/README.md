# iOS Build Configuration

## Minimum Requirements

| Setting        | Value  |
|----------------|--------|
| iOS Deployment | 15.0   |
| Xcode          | 15.0+  |
| Swift          | 5.9+   |

## Required Capabilities (`Runner.entitlements`)

- Maps (requires `NSLocationWhenInUseUsageDescription`)
- Biometrics (`NSFaceIDUsageDescription`)
- Camera (`NSCameraUsageDescription`)
- Photo Library (`NSPhotoLibraryUsageDescription`)
- Push Notifications

## `Info.plist` Keys

```xml
<key>NSLocationWhenInUseUsageDescription</key>
<string>AlakhService needs your location to show nearby providers.</string>

<key>NSLocationAlwaysAndWhenInUseUsageDescription</key>
<string>AlakhService uses your location to track your service provider.</string>

<key>NSCameraUsageDescription</key>
<string>AlakhService needs camera access to upload profile photos.</string>

<key>NSPhotoLibraryUsageDescription</key>
<string>AlakhService needs photo library access to select profile photos.</string>

<key>NSFaceIDUsageDescription</key>
<string>Use Face ID for quick and secure login.</string>
```

## Google Maps API Key

`AppDelegate.swift` reads `GMSApiKey` from `Info.plist`, which is filled from the
`GOOGLE_MAPS_API_KEY` build setting. Copy `Flutter/Secrets.xcconfig.example` to
`Flutter/Secrets.xcconfig` (git-ignored) and set the key there.

## Permissions (`Podfile`)

`permission_handler` only compiles in the permissions enabled in the `Podfile`'s
`post_install` hook: location (when in use), camera, photos and notifications. Add a
`PERMISSION_*=1` macro there before requesting any other permission.

## App Store Deployment

1. Set the bundle identifier (`com.alakhservice.alakhService` by default) in `Runner.xcodeproj`
2. Configure signing in **Xcode → Signing & Capabilities**
3. Run `flutter build ipa --release`
4. Upload via **Xcode Organizer** or `xcrun altool`
