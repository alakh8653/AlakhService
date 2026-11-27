import 'dart:async';

import 'package:dio/dio.dart';

import '../core/network/api_errors.dart';
import '../core/network/idempotency.dart';
import '../l10n/l10n.dart';
import 'offline_queue.dart';

/// A change the server turned down for good once it was sent (e.g. the chat closed while the phone was
/// offline), with the reason to show.
class DroppedRequest {
  final PendingRequest request;
  final String reason;

  const DroppedRequest(this.request, this.reason);
}

/// Sends changes that can wait for a connection: straight away when possible, otherwise from the
/// [OfflineQueue] as soon as the device is back online.
///
/// Only changes that are safe to repeat go through here: each carries an Idempotency-Key, or is a PUT
/// or DELETE. Anything that needs an answer now (a booking, a payment) does not.
class SyncManager {
  final OfflineQueue queue;
  final Dio dio;
  final Stream<bool>? online;

  /// How often to try again while changes are waiting and the device seems online (the server may have
  /// been the one down).
  final Duration retryEvery;

  /// Changes older than this, or turned away by a failing server this many times, are given up on.
  final Duration maxAge;
  final int maxAttempts;
  final DateTime Function() now;

  final _delivered = StreamController<PendingRequest>.broadcast();
  final _dropped = StreamController<DroppedRequest>.broadcast();
  StreamSubscription<bool>? _onlineSubscription;
  Timer? _retry;
  Future<void>? _running;
  bool _isOnline = true;

  SyncManager({
    required this.queue,
    required this.dio,
    this.online,
    this.retryEvery = const Duration(minutes: 1),
    this.maxAge = const Duration(days: 7),
    this.maxAttempts = 20,
    DateTime Function()? now,
  }) : now = now ?? DateTime.now;

  /// Each change as the server accepts it.
  Stream<PendingRequest> get delivered => _delivered.stream;

  /// Each change given up on, with why.
  Stream<DroppedRequest> get dropped => _dropped.stream;

  /// Starts sending: now, each time the device comes back online, and every [retryEvery] meanwhile.
  void start() {
    _onlineSubscription ??= online?.distinct().listen((isOnline) {
      _isOnline = isOnline;
      if (isOnline) sync();
    }, onError: (Object _) {});
    _retry ??= Timer.periodic(retryEvery, (_) {
      if (_isOnline && !queue.isEmpty) sync();
    });
    sync();
  }

  Future<void> dispose() async {
    _retry?.cancel();
    await _onlineSubscription?.cancel();
    await _delivered.close();
    await _dropped.close();
  }

  /// A new change to send, keyed so a repeat is harmless.
  PendingRequest request(
    PendingKind kind,
    String method,
    String path, {
    Map<String, dynamic>? data,
    String? ref,
    String? replaces,
  }) =>
      PendingRequest(
        id: newIdempotencyKey(),
        kind: kind,
        method: method,
        path: path,
        data: data,
        ref: ref,
        replaces: replaces,
        createdAt: now(),
      );

  /// Sends [request] now and returns the server's reply, or keeps it for later and returns null when
  /// there is no connection. Changes about the same [PendingRequest.ref] still waiting go first, so they
  /// arrive in the order they were made. A refusal from the server throws as usual.
  Future<Response<dynamic>?> send(PendingRequest request) async {
    final waitingAhead = request.ref != null && queue.items.any((r) => r.ref == request.ref && r.kind == request.kind);
    if (waitingAhead) {
      await queue.add(request);
      if (_isOnline) unawaited(sync());
      return null;
    }
    try {
      return await _fetch(request);
    } on DioException catch (e) {
      if (!isTransient(e)) rethrow;
    }
    await queue.add(request.retried());
    return null;
  }

  /// Sends every waiting change, oldest first. Safe to call at any time; overlapping calls share one pass.
  Future<void> sync() => _running ??= _pass().whenComplete(() => _running = null);

  /// Forgets every waiting change (signing out: they belong to that account).
  Future<void> clear() => queue.clear();

  Future<void> _pass() async {
    // What still has an earlier change waiting: later ones about it wait too, to keep their order.
    final held = <(PendingKind, String)>{};
    for (final request in List.of(queue.items)) {
      final ref = request.ref;
      if (ref != null && held.contains((request.kind, ref))) continue;
      if (now().difference(request.createdAt) > maxAge) {
        await _drop(request, currentL10n.offlineChangeExpired);
        continue;
      }
      try {
        await _fetch(request);
        await queue.remove(request.id);
        if (!_delivered.isClosed) _delivered.add(request);
      } on DioException catch (e) {
        if (!isTransient(e)) {
          await _drop(request, apiErrorMessage(e));
          continue;
        }
        final retried = request.retried();
        // Only the server's own errors count towards giving up; no network at all is what [maxAge] is for.
        if (e.response != null && retried.attempts >= maxAttempts) {
          await _drop(request, apiErrorMessage(e));
          continue;
        }
        await queue.replace(retried);
        // Still no way through: the rest would fail the same way.
        if (e.response == null) return;
        if (ref != null) held.add((request.kind, ref));
      }
    }
  }

  Future<void> _drop(PendingRequest request, String reason) async {
    await queue.remove(request.id);
    if (!_dropped.isClosed) _dropped.add(DroppedRequest(request, reason));
  }

  Future<Response<dynamic>> _fetch(PendingRequest request) => dio.request<dynamic>(
        request.path,
        data: request.data,
        options: Options(method: request.method, headers: {'Idempotency-Key': request.id}),
      );

  /// Whether trying again later may work: no connection, a timeout, or the server busy or down. A 401
  /// is the session's business (the client refreshes it or signs out), so it is kept too.
  static bool isTransient(DioException e) {
    switch (e.type) {
      case DioExceptionType.connectionError:
      case DioExceptionType.connectionTimeout:
      case DioExceptionType.sendTimeout:
      case DioExceptionType.receiveTimeout:
        return true;
      case DioExceptionType.unknown:
        return e.response == null;
      default:
        break;
    }
    final status = e.response?.statusCode;
    return status == null || status == 401 || status == 408 || status == 429 || status >= 500;
  }
}
