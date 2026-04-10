import 'package:flutter_dotenv/flutter_dotenv.dart';

/// Supported deployment environments.
enum AppEnvironment { development, staging, production }

/// Application-wide configuration loaded from environment variables.
class AppConfig {
  AppConfig._();

  static AppEnvironment get environment {
    final env = dotenv.env['APP_ENV'] ?? 'development';
    return AppEnvironment.values.firstWhere(
      (e) => e.name == env,
      orElse: () => AppEnvironment.development,
    );
  }

  static String get baseUrl {
    return switch (environment) {
      AppEnvironment.production => dotenv.env['PROD_BASE_URL'] ?? 'https://api.alakhservice.com',
      AppEnvironment.staging => dotenv.env['STAGING_BASE_URL'] ?? 'https://staging-api.alakhservice.com',
      AppEnvironment.development => dotenv.env['DEV_BASE_URL'] ?? 'http://localhost:3000',
    };
  }

  static String get apiKey => dotenv.env['API_KEY'] ?? '';

  static int get connectTimeoutMs => int.tryParse(dotenv.env['CONNECT_TIMEOUT_MS'] ?? '') ?? 30000;
  static int get receiveTimeoutMs => int.tryParse(dotenv.env['RECEIVE_TIMEOUT_MS'] ?? '') ?? 30000;

  static bool get isDebug => environment != AppEnvironment.production;
}
