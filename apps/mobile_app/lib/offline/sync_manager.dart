import 'dart:async';
import 'offline_queue.dart';
import 'cache_manager.dart';

/// Coordinates periodic synchronisation of queued offline actions.
class SyncManager {
  final OfflineQueue queue;
  final AppCacheManager cacheManager;

  Timer? _syncTimer;
  bool _isSyncing = false;

  SyncManager({required this.queue, required this.cacheManager});

  /// Starts background sync with the given [interval].
  void start({Duration interval = const Duration(minutes: 5)}) {
    _syncTimer?.cancel();
    _syncTimer = Timer.periodic(interval, (_) => sync());
  }

  void stop() => _syncTimer?.cancel();

  /// Processes all pending items in the offline queue.
  Future<void> sync() async {
    if (_isSyncing) return;
    _isSyncing = true;
    try {
      final pending = await queue.getPending();
      for (final action in pending) {
        try {
          await _dispatch(action);
          await queue.remove(action.id);
        } catch (_) {
          await queue.incrementRetry(action.id);
        }
      }
    } finally {
      _isSyncing = false;
    }
  }

  Future<void> _dispatch(QueuedAction action) async {
    // Concrete implementations should handle each action type and call
    // the relevant API. This stub simulates a successful dispatch.
    await Future.delayed(const Duration(milliseconds: 100));
  }
}
