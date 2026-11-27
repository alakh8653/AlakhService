import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// What a [PendingRequest] does, so screens can show the ones that concern them.
enum PendingKind {
  /// A chat message on booking [PendingRequest.ref].
  chatMessage,

  /// A notification (or all of them) marked read.
  notificationRead,

  /// A shop saved or removed from the saved shops ([PendingRequest.ref] is the shop).
  savedShop,
}

/// A change made while offline, waiting to be sent to the API gateway.
///
/// [id] doubles as the request's Idempotency-Key, so sending it twice (a reply lost on a bad network)
/// changes nothing on the server.
@immutable
class PendingRequest {
  final String id;
  final PendingKind kind;

  /// GET is never queued: only POST, PUT and DELETE.
  final String method;
  final String path;
  final Map<String, dynamic>? data;

  /// What the change is about (a booking or shop id), for screens and for keeping its order.
  final String? ref;

  /// A later change with the same key replaces this one (saving then unsaving a shop sends only the
  /// last).
  final String? replaces;
  final DateTime createdAt;
  final int attempts;

  const PendingRequest({
    required this.id,
    required this.kind,
    required this.method,
    required this.path,
    this.data,
    this.ref,
    this.replaces,
    required this.createdAt,
    this.attempts = 0,
  });

  PendingRequest retried() => PendingRequest(
        id: id,
        kind: kind,
        method: method,
        path: path,
        data: data,
        ref: ref,
        replaces: replaces,
        createdAt: createdAt,
        attempts: attempts + 1,
      );

  Map<String, dynamic> toJson() => {
        'id': id,
        'kind': kind.name,
        'method': method,
        'path': path,
        'data': data,
        'ref': ref,
        'replaces': replaces,
        'created_at': createdAt.toUtc().toIso8601String(),
        'attempts': attempts,
      };

  /// Null for an entry this version of the app does not understand (written by a newer one).
  static PendingRequest? fromJson(Map<String, dynamic> json) {
    final kind = PendingKind.values.where((k) => k.name == json['kind']).firstOrNull;
    final createdAt = DateTime.tryParse((json['created_at'] as String?) ?? '');
    if (kind == null || createdAt == null || json['id'] is! String || json['path'] is! String) return null;
    return PendingRequest(
      id: json['id'] as String,
      kind: kind,
      method: (json['method'] as String?) ?? 'POST',
      path: json['path'] as String,
      data: (json['data'] as Map?)?.cast<String, dynamic>(),
      ref: json['ref'] as String?,
      replaces: json['replaces'] as String?,
      createdAt: createdAt.toLocal(),
      attempts: (json['attempts'] as num?)?.toInt() ?? 0,
    );
  }
}

/// The changes waiting to be sent, oldest first, kept in shared_preferences so they survive the app
/// being closed. [pending] lets screens show them and rebuild as they go out.
class OfflineQueue {
  static const String storageKey = 'offline_queue_v2';

  final SharedPreferences _prefs;
  final ValueNotifier<List<PendingRequest>> pending;

  OfflineQueue(this._prefs) : pending = ValueNotifier(List.unmodifiable(_read(_prefs)));

  static List<PendingRequest> _read(SharedPreferences prefs) {
    final raw = prefs.getString(storageKey);
    if (raw == null) return const [];
    try {
      return [
        for (final entry in jsonDecode(raw) as List<dynamic>)
          if (PendingRequest.fromJson((entry as Map).cast<String, dynamic>()) case final request?) request,
      ];
    } catch (_) {
      // A damaged entry must not stop the app from starting.
      return const [];
    }
  }

  List<PendingRequest> get items => pending.value;
  bool get isEmpty => items.isEmpty;

  /// Waiting changes of one [kind] about [ref], oldest first.
  List<PendingRequest> about(PendingKind kind, String ref) =>
      [for (final r in items) if (r.kind == kind && r.ref == ref) r];

  Future<void> add(PendingRequest request) => _save([
        for (final r in items)
          if (request.replaces == null || r.replaces != request.replaces) r,
        request,
      ]);

  Future<void> remove(String id) => _save([for (final r in items) if (r.id != id) r]);

  Future<void> replace(PendingRequest request) => _save([for (final r in items) r.id == request.id ? request : r]);

  Future<void> clear() => _save(const []);

  Future<void> _save(List<PendingRequest> next) async {
    pending.value = List.unmodifiable(next);
    if (next.isEmpty) {
      await _prefs.remove(storageKey);
    } else {
      await _prefs.setString(storageKey, jsonEncode([for (final r in next) r.toJson()]));
    }
  }
}
