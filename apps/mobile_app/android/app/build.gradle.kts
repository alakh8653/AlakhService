import java.util.Properties

plugins {
    id("com.android.application")
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
}

// Secrets come from android/local.properties (git-ignored) or the environment, never from source.
val localProperties = Properties().apply {
    val file = rootProject.file("local.properties")
    if (file.exists()) file.inputStream().use { load(it) }
}
// The app-link domain, kept with the iOS one in ../app_links.xcconfig ("KEY = value" lines also read
// as Java properties; its // comment lines come out as one harmless "//" key).
val appLinkDomain: String = Properties().apply {
    val file = rootProject.file("../app_links.xcconfig")
    if (file.exists()) file.inputStream().use { load(it) }
}.getProperty("APP_LINK_DOMAIN")?.trim()?.takeIf { it.isNotEmpty() } ?: "alakhservice.in"

val googleMapsApiKey: String =
    localProperties.getProperty("GOOGLE_MAPS_API_KEY") ?: System.getenv("GOOGLE_MAPS_API_KEY") ?: ""

// Release signing: android/key.properties (git-ignored) or ANDROID_KEYSTORE_* environment
// variables (CI). Without either, release builds fall back to the debug key, which is fine for
// local testing but cannot be published.
val keyProperties = Properties().apply {
    val file = rootProject.file("key.properties")
    if (file.exists()) file.inputStream().use { load(it) }
}
fun signingValue(property: String, env: String): String? =
    keyProperties.getProperty(property)?.takeIf { it.isNotBlank() }
        ?: System.getenv(env)?.takeIf { it.isNotBlank() }
val releaseStoreFile = signingValue("storeFile", "ANDROID_KEYSTORE_PATH")
val releaseStorePassword = signingValue("storePassword", "ANDROID_KEYSTORE_PASSWORD")
val releaseKeyAlias = signingValue("keyAlias", "ANDROID_KEY_ALIAS")
val releaseKeyPassword = signingValue("keyPassword", "ANDROID_KEY_PASSWORD")
val hasReleaseSigning = listOf(releaseStoreFile, releaseStorePassword, releaseKeyAlias, releaseKeyPassword)
    .all { it != null }

android {
    namespace = "com.alakhservice.alakh_service"
    // Some plugins must be compiled against API 37 (compileSdk only;
    // targetSdk stays on the Flutter default, so runtime behaviour is unchanged).
    compileSdk = maxOf(flutter.compileSdkVersion, 37)
    ndkVersion = flutter.ndkVersion

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    defaultConfig {
        applicationId = "com.alakhservice.alakh_service"
        // You can update the following values to match your application needs.
        // For more information, see: https://flutter.dev/to/review-gradle-config.
        minSdk = flutter.minSdkVersion
        targetSdk = flutter.targetSdkVersion
        // Uses the version code from pubspec.yaml. When using split APKs, 1000 * ABI_VERSION
        // is added automatically by Flutter. (https://developer.android.com/studio/build/configure-apk-splits#configure-APK-versions)
        // You can force using the value of versionCode by specifying the `-P force-version-code-ignoring-abi=true`
        // flag during build.
        versionCode = flutter.versionCode
        versionName = flutter.versionName
        manifestPlaceholders["googleMapsApiKey"] = googleMapsApiKey
        manifestPlaceholders["appLinkDomain"] = appLinkDomain
    }

    signingConfigs {
        if (hasReleaseSigning) {
            create("release") {
                // A relative storeFile resolves against android/app, like Flutter's template.
                storeFile = file(releaseStoreFile!!)
                storePassword = releaseStorePassword
                keyAlias = releaseKeyAlias
                keyPassword = releaseKeyPassword
            }
        }
    }

    buildTypes {
        release {
            signingConfig = if (hasReleaseSigning) {
                signingConfigs.getByName("release")
            } else {
                logger.warn("No release keystore configured; signing the release build with the debug key.")
                signingConfigs.getByName("debug")
            }
        }
    }
}

kotlin {
    compilerOptions {
        jvmTarget = org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17
    }
}

flutter {
    source = "../.."
}

// Push (Firebase Cloud Messaging): only with android/app/google-services.json from the Firebase
// console. Without it the build still works and the app runs without push.
if (file("google-services.json").exists()) {
    apply(plugin = "com.google.gms.google-services")
} else {
    logger.warn("No android/app/google-services.json; building without push notifications.")
}
