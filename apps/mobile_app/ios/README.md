# iOS Build Configuration

## Minimum Requirements

| Setting        | Value  |
|----------------|--------|
| iOS Deployment | 13.0   |
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

## Google Maps API Key (`AppDelegate.swift`)

```swift
import GoogleMaps

@UIApplicationMain
class AppDelegate: FlutterAppDelegate {
  override func application(...) -> Bool {
    GMSServices.provideAPIKey("YOUR_GOOGLE_MAPS_API_KEY")
    return super.application(application, didFinishLaunchingWithOptions: launchOptions)
  }
}
```

## App Store Deployment

1. Set `PRODUCT_BUNDLE_IDENTIFIER` in `Runner.xcodeproj`
2. Configure signing in **Xcode → Signing & Capabilities**
3. Run `flutter build ipa --release`
4. Upload via **Xcode Organizer** or `xcrun altool`
