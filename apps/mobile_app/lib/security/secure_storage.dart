import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// Thin wrapper around [FlutterSecureStorage] for storing sensitive values
/// such as auth tokens and encryption keys.
class SecureStorageService {
  static const FlutterSecureStorage _storage = FlutterSecureStorage(
    aOptions: AndroidOptions(encryptedSharedPreferences: true),
    iOptions: IOSOptions(
      accessibility: KeychainAccessibility.first_unlock_this_device,
    ),
  );

  Future<void> write(String key, String value) =>
      _storage.write(key: key, value: value);

  Future<String?> read(String key) => _storage.read(key: key);

  Future<void> delete(String key) => _storage.delete(key: key);

  Future<void> deleteAll() => _storage.deleteAll();

  Future<bool> containsKey(String key) => _storage.containsKey(key: key);

  Future<Map<String, String>> readAll() => _storage.readAll();

  // Convenience helpers for common token operations.

  Future<void> saveAccessToken(String token) =>
      write('access_token', token);

  Future<String?> getAccessToken() => read('access_token');

  Future<void> saveRefreshToken(String token) =>
      write('refresh_token', token);

  Future<String?> getRefreshToken() => read('refresh_token');

  Future<void> clearTokens() async {
    await delete('access_token');
    await delete('refresh_token');
  }
}
