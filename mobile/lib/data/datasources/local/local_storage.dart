import 'package:shared_preferences/shared_preferences.dart';

/// Thin wrapper around [SharedPreferences] exposed as a singleton.
/// For larger binary data, swap out the implementation for Hive.
class LocalStorage {
  LocalStorage._();
  static final LocalStorage instance = LocalStorage._();

  SharedPreferences? _prefs;

  Future<void> init() async {
    _prefs ??= await SharedPreferences.getInstance();
  }

  SharedPreferences get _p {
    assert(_prefs != null, 'LocalStorage.init() must be called before use.');
    return _prefs!;
  }

  // ── String ────────────────────────────────────────────────────────────────

  Future<bool> setString(String key, String value) => _p.setString(key, value);
  String? getString(String key) => _p.getString(key);

  // ── Bool ──────────────────────────────────────────────────────────────────

  Future<bool> setBool(String key, {required bool value}) => _p.setBool(key, value);
  bool? getBool(String key) => _p.getBool(key);

  // ── Int ───────────────────────────────────────────────────────────────────

  Future<bool> setInt(String key, int value) => _p.setInt(key, value);
  int? getInt(String key) => _p.getInt(key);

  // ── Generic ───────────────────────────────────────────────────────────────

  Future<bool> remove(String key) => _p.remove(key);

  Future<bool> clear() => _p.clear();

  bool containsKey(String key) => _p.containsKey(key);
}
