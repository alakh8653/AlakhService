import '../../security/secure_storage.dart';

/// Where the signed-in session's tokens live.
abstract class TokenStore {
  Future<String?> accessToken();
  Future<String?> refreshToken();
  Future<void> save({required String accessToken, required String refreshToken});
  Future<void> clear();
}

/// Tokens in the platform keystore/keychain.
class SecureTokenStore implements TokenStore {
  final SecureStorageService _storage;

  SecureTokenStore([SecureStorageService? storage]) : _storage = storage ?? SecureStorageService();

  // A keystore that can't be read (e.g. restored from another device) means no session.
  @override
  Future<String?> accessToken() => _readOrNull(_storage.getAccessToken);

  @override
  Future<String?> refreshToken() => _readOrNull(_storage.getRefreshToken);

  static Future<String?> _readOrNull(Future<String?> Function() read) async {
    try {
      return await read();
    } catch (_) {
      return null;
    }
  }

  @override
  Future<void> save({required String accessToken, required String refreshToken}) async {
    await _storage.saveAccessToken(accessToken);
    await _storage.saveRefreshToken(refreshToken);
  }

  @override
  Future<void> clear() => _storage.clearTokens();
}

/// Tokens kept in memory only (tests, or platforms without secure storage).
class MemoryTokenStore implements TokenStore {
  String? _access;
  String? _refresh;

  @override
  Future<String?> accessToken() async => _access;

  @override
  Future<String?> refreshToken() async => _refresh;

  @override
  Future<void> save({required String accessToken, required String refreshToken}) async {
    _access = accessToken;
    _refresh = refreshToken;
  }

  @override
  Future<void> clear() async {
    _access = null;
    _refresh = null;
  }
}
