import 'dart:convert';
import 'package:shared_preferences/shared_preferences.dart';

/// Simple key-value cache backed by [SharedPreferences].
///
/// Entries can optionally carry a TTL. Expired entries are discarded on read.
class AppCacheManager {
  static const String _prefix = 'cache_';

  Future<void> set(
    String key,
    dynamic value, {
    Duration? ttl,
  }) async {
    final prefs = await SharedPreferences.getInstance();
    final entry = _CacheEntry(
      value: value,
      expiresAt: ttl != null ? DateTime.now().add(ttl) : null,
    );
    await prefs.setString(_prefix + key, jsonEncode(entry.toJson()));
  }

  Future<T?> get<T>(String key) async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_prefix + key);
    if (raw == null) return null;
    final entry = _CacheEntry.fromJson(
      jsonDecode(raw) as Map<String, dynamic>,
    );
    if (entry.isExpired) {
      await prefs.remove(_prefix + key);
      return null;
    }
    return entry.value as T?;
  }

  Future<void> remove(String key) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_prefix + key);
  }

  Future<void> clearAll() async {
    final prefs = await SharedPreferences.getInstance();
    final keys = prefs.getKeys().where((k) => k.startsWith(_prefix));
    for (final key in keys) {
      await prefs.remove(key);
    }
  }

  Future<bool> has(String key) async => await get(key) != null;
}

class _CacheEntry {
  final dynamic value;
  final DateTime? expiresAt;

  _CacheEntry({required this.value, this.expiresAt});

  bool get isExpired =>
      expiresAt != null && DateTime.now().isAfter(expiresAt!);

  Map<String, dynamic> toJson() => {
        'value': value,
        'expires_at': expiresAt?.toIso8601String(),
      };

  factory _CacheEntry.fromJson(Map<String, dynamic> json) => _CacheEntry(
        value: json['value'],
        expiresAt: json['expires_at'] != null
            ? DateTime.parse(json['expires_at'] as String)
            : null,
      );
}
