import 'dart:convert';
import 'package:shared_preferences/shared_preferences.dart';

/// Represents a single deferred API action stored in the offline queue.
class QueuedAction {
  final String id;
  final String type;
  final Map<String, dynamic> payload;
  final DateTime createdAt;
  int retryCount;

  QueuedAction({
    required this.id,
    required this.type,
    required this.payload,
    required this.createdAt,
    this.retryCount = 0,
  });

  Map<String, dynamic> toJson() => {
        'id': id,
        'type': type,
        'payload': payload,
        'created_at': createdAt.toIso8601String(),
        'retry_count': retryCount,
      };

  factory QueuedAction.fromJson(Map<String, dynamic> json) => QueuedAction(
        id: json['id'] as String,
        type: json['type'] as String,
        payload: json['payload'] as Map<String, dynamic>,
        createdAt: DateTime.parse(json['created_at'] as String),
        retryCount: json['retry_count'] as int? ?? 0,
      );
}

/// Persistent FIFO queue for offline actions backed by [SharedPreferences].
class OfflineQueue {
  static const String _key = 'offline_queue';
  static const int maxRetries = 3;

  Future<List<QueuedAction>> getPending() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_key);
    if (raw == null) return [];
    final list = jsonDecode(raw) as List<dynamic>;
    return list
        .map((e) => QueuedAction.fromJson(e as Map<String, dynamic>))
        .where((a) => a.retryCount < maxRetries)
        .toList();
  }

  Future<void> enqueue(QueuedAction action) async {
    final prefs = await SharedPreferences.getInstance();
    final existing = await getPending();
    existing.add(action);
    await prefs.setString(
      _key,
      jsonEncode(existing.map((a) => a.toJson()).toList()),
    );
  }

  Future<void> remove(String id) async {
    final prefs = await SharedPreferences.getInstance();
    final existing = await getPending();
    existing.removeWhere((a) => a.id == id);
    await prefs.setString(
      _key,
      jsonEncode(existing.map((a) => a.toJson()).toList()),
    );
  }

  Future<void> incrementRetry(String id) async {
    final prefs = await SharedPreferences.getInstance();
    final existing = await getPending();
    for (final a in existing) {
      if (a.id == id) a.retryCount++;
    }
    await prefs.setString(
      _key,
      jsonEncode(existing.map((a) => a.toJson()).toList()),
    );
  }

  Future<void> clear() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_key);
  }
}
