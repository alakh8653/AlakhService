import 'dart:convert';
import 'package:shared_preferences/shared_preferences.dart';
import '../../../../core/errors/exceptions.dart';
import '../models/user_model.dart';

/// The last signed-in user, for showing the profile offline. Tokens live in TokenStore
/// (secure storage), never here.
abstract class AuthLocalDataSource {
  Future<void> cacheUser(UserModel user);
  Future<UserModel?> getCachedUser();
  Future<void> clearCache();
}

class AuthLocalDataSourceImpl implements AuthLocalDataSource {
  static const String _cachedUserKey = 'cached_user';

  @override
  Future<void> cacheUser(UserModel user) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_cachedUserKey, jsonEncode(user.toJson()));
  }

  @override
  Future<UserModel?> getCachedUser() async {
    final prefs = await SharedPreferences.getInstance();
    final jsonStr = prefs.getString(_cachedUserKey);
    if (jsonStr == null) return null;
    try {
      return UserModel.fromJson(jsonDecode(jsonStr) as Map<String, dynamic>);
    } catch (_) {
      throw const CacheException(message: 'Failed to parse cached user');
    }
  }

  @override
  Future<void> clearCache() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_cachedUserKey);
  }
}
