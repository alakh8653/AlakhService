import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:alakh_service/core/network/api_client.dart';
import 'package:alakh_service/core/network/token_store.dart';
import 'package:alakh_service/features/chat/data/chat_api.dart';
import 'package:alakh_service/features/notifications/data/notifications_api.dart';
import 'package:alakh_service/features/shops/data/saved_shops_api.dart';
import 'package:alakh_service/offline/offline_queue.dart';
import 'package:alakh_service/offline/sync_manager.dart';
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// A gateway that can be switched off: while [up] is false every request fails as if there were no
/// network. Otherwise [reply] answers; requests that reached it are in [received].
class Gateway implements HttpClientAdapter {
  bool up = true;
  ({int status, Object? body}) Function(RequestOptions r) reply = (r) => (status: 200, body: <String, dynamic>{});
  final received = <RequestOptions>[];

  @override
  Future<ResponseBody> fetch(RequestOptions options, Stream<Uint8List>? requestStream, Future<void>? cancelFuture) async {
    if (!up) throw DioException.connectionError(requestOptions: options, reason: 'offline');
    received.add(options);
    final answer = reply(options);
    return ResponseBody.fromString(
      answer.body == null ? '' : jsonEncode(answer.body),
      answer.status,
      headers: {
        Headers.contentTypeHeader: [Headers.jsonContentType],
      },
    );
  }

  @override
  void close({bool force = false}) {}

  List<String> get paths => [for (final r in received) '${r.method} ${r.path}'];
}

Map<String, dynamic> message(String id, String body) => {
      'id': id,
      'booking_id': 'b1',
      'sender_role': 'customer',
      'sender_name': 'Ravi S.',
      'is_mine': true,
      'body': body,
      'flagged': false,
      'created_at': '2026-11-27T09:00:00Z',
    };

void main() {
  late Gateway gateway;
  late ApiClient client;
  late OfflineQueue queue;
  late StreamController<bool> online;
  late SyncManager sync;
  var clock = DateTime(2026, 11, 27, 9);

  Future<void> setUpWith(Map<String, Object> saved) async {
    SharedPreferences.setMockInitialValues(saved);
    gateway = Gateway();
    client = ApiClient(
      dio: Dio(BaseOptions(baseUrl: 'http://api.test'))..httpClientAdapter = gateway,
      tokens: MemoryTokenStore(),
    );
    queue = OfflineQueue(await SharedPreferences.getInstance());
    online = StreamController<bool>.broadcast();
    clock = DateTime(2026, 11, 27, 9);
    sync = SyncManager(queue: queue, dio: client.dio, online: online.stream, now: () => clock);
  }

  setUp(() => setUpWith({}));

  /// The device reports no network, so nothing is tried until it says otherwise.
  Future<void> goOffline() async {
    gateway.up = false;
    sync.start();
    online.add(false);
    await pumpEventQueue();
  }
  tearDown(() async {
    await sync.dispose();
    await online.close();
  });

  test('a message sent online goes straight out, with its key', () async {
    gateway.reply = (r) => (status: 201, body: message('m1', 'Hi'));
    final chat = ChatApi(client, offline: sync);

    final sent = await chat.send('b1', 'Hi');

    expect(sent?.id, 'm1');
    expect(queue.isEmpty, isTrue);
    expect(gateway.received.single.headers['Idempotency-Key'], isNotEmpty);
  });

  test('offline, messages wait in order and go out with the same key once back online', () async {
    gateway.up = false;
    final chat = ChatApi(client, offline: sync);

    expect(await chat.send('b1', 'Running late'), isNull);
    expect(await chat.send('b1', '10 minutes'), isNull);
    expect([for (final r in chat.pending('b1')) r.data?['body']], ['Running late', '10 minutes']);
    final keys = [for (final r in queue.items) r.id];

    final delivered = <String>[];
    sync.delivered.listen((r) => delivered.add(r.data?['body'] as String));
    gateway
      ..up = true
      ..reply = (r) => (status: 201, body: message('m', (r.data as Map)['body'] as String));
    sync.start();
    online.add(true);
    await pumpEventQueue();

    expect([for (final r in gateway.received) (r.data as Map)['body']], ['Running late', '10 minutes']);
    expect([for (final r in gateway.received) r.headers['Idempotency-Key']], keys);
    expect(delivered, ['Running late', '10 minutes']);
    expect(queue.isEmpty, isTrue);
  });

  test('a message written while earlier ones wait goes behind them, even online', () async {
    gateway.up = false;
    final chat = ChatApi(client, offline: sync);
    await chat.send('b1', 'first');
    gateway
      ..up = true
      ..reply = (r) => (status: 201, body: message('m', (r.data as Map)['body'] as String));

    expect(await chat.send('b1', 'second'), isNull);
    await pumpEventQueue();

    expect([for (final r in gateway.received) (r.data as Map)['body']], ['first', 'second']);
  });

  test('what the server turns down is dropped with its reason; the rest still goes', () async {
    gateway.up = false;
    final chat = ChatApi(client, offline: sync);
    await chat.send('b1', 'too late');
    await chat.send('b2', 'fine');
    final dropped = <DroppedRequest>[];
    sync.dropped.listen(dropped.add);

    gateway
      ..up = true
      ..reply = (r) => r.path.contains('b1')
          ? (status: 409, body: {'detail': 'This chat is closed'})
          : (status: 201, body: message('m2', 'fine'));
    await sync.sync();
    await pumpEventQueue();

    expect(dropped.single.request.ref, 'b1');
    expect(dropped.single.reason, 'This chat is closed');
    expect(gateway.received, hasLength(2));
    expect(queue.isEmpty, isTrue);
  });

  test('a server error keeps the change, and later ones about the same booking wait behind it', () async {
    await goOffline();
    final chat = ChatApi(client, offline: sync);
    await chat.send('b1', 'one');
    await chat.send('b1', 'two');
    await chat.send('b2', 'other chat');

    gateway
      ..up = true
      ..reply = (r) => (r.data as Map)['body'] == 'one'
          ? (status: 503, body: {'detail': 'busy'})
          : (status: 201, body: message('m', (r.data as Map)['body'] as String));
    await sync.sync();

    expect([for (final r in gateway.received) (r.data as Map)['body']], ['one', 'other chat']);
    expect([for (final r in queue.items) r.data?['body']], ['one', 'two']);
    expect(queue.items.first.attempts, 2); // tried when written, and now
  });

  test('no network for a long time never uses up the tries; a failing server does', () async {
    await goOffline();
    final small = SyncManager(queue: queue, dio: client.dio, maxAttempts: 3, now: () => clock);
    addTearDown(small.dispose);
    await ChatApi(client, offline: small).send('b1', 'patient');
    for (var i = 0; i < 10; i++) {
      await small.sync();
    }
    expect(queue.items, hasLength(1));

    gateway
      ..up = true
      ..reply = (r) => (status: 500, body: {'detail': 'boom'});
    for (var i = 0; i < 3; i++) {
      await small.sync();
    }
    expect(queue.isEmpty, isTrue);
  });

  test('changes that waited a week are given up on', () async {
    gateway.up = false;
    await ChatApi(client, offline: sync).send('b1', 'old');
    final dropped = <DroppedRequest>[];
    sync.dropped.listen(dropped.add);

    clock = clock.add(const Duration(days: 8));
    gateway.up = true;
    await sync.sync();
    await pumpEventQueue();

    expect(dropped, hasLength(1));
    expect(gateway.received, isEmpty);
  });

  test('waiting changes survive the app being closed', () async {
    gateway.up = false;
    await ChatApi(client, offline: sync).send('b1', 'kept');
    final saved = (await SharedPreferences.getInstance()).getString(OfflineQueue.storageKey)!;

    await setUpWith({OfflineQueue.storageKey: saved});

    expect([for (final r in queue.items) r.data?['body']], ['kept']);
    expect(queue.items.single.kind, PendingKind.chatMessage);
  });

  test('a damaged or unknown saved entry does not stop the app', () async {
    await setUpWith({
      OfflineQueue.storageKey: jsonEncode([
        {'id': 'x', 'kind': 'fromTheFuture', 'path': '/a', 'created_at': '2026-11-27T09:00:00Z'},
        {
          'id': 'y',
          'kind': 'notificationRead',
          'method': 'POST',
          'path': '/api/v1/notifications/read-all',
          'created_at': '2026-11-27T09:00:00Z',
        },
      ]),
    });
    expect([for (final r in queue.items) r.id], ['y']);

    await setUpWith({OfflineQueue.storageKey: 'not json'});
    expect(queue.isEmpty, isTrue);
  });

  test('saving then removing a shop offline sends only the last choice, and the list reflects it', () async {
    await goOffline();
    final shops = SavedShopsApi(client, offline: sync);
    await shops.save('s1');
    await shops.unsave('s1');
    expect([for (final r in queue.items) r.method], ['DELETE']);

    gateway
      ..up = true
      ..reply = (r) => r.method == 'GET'
          ? (status: 200, body: [
              {'id': 's1', 'name': 'Glow Salon'},
              {'id': 's2', 'name': 'Fix-It'},
            ])
          : (status: 204, body: null);
    // Listed before the change has gone out: the removed shop is not shown.
    expect([for (final s in await shops.list()) s.id], ['s2']);

    await sync.sync();
    expect(gateway.paths.last, 'DELETE /api/v1/shops/s1/favorite');
  });

  test('read marks made offline go out once, the latest replacing the same one', () async {
    gateway.up = false;
    final notifications = NotificationsApi(client, offline: sync);
    await notifications.markRead('n1');
    await notifications.markRead('n1');
    await notifications.markAllRead();
    expect(queue.items, hasLength(2));

    gateway.up = true;
    await sync.sync();
    expect(gateway.paths, ['POST /api/v1/notifications/n1/read', 'POST /api/v1/notifications/read-all']);
  });

  test('without an offline queue, a failure surfaces as before', () async {
    gateway.up = false;
    await expectLater(ChatApi(client).send('b1', 'Hi'), throwsA(anything));
  });

  test('signing out forgets what is waiting', () async {
    gateway.up = false;
    await ChatApi(client, offline: sync).send('b1', 'Hi');
    await sync.clear();
    expect(queue.isEmpty, isTrue);
    expect((await SharedPreferences.getInstance()).getString(OfflineQueue.storageKey), isNull);
  });
}
