import 'dart:async';
import 'dart:typed_data';

import 'package:alakh_service/app/app_view.dart';
import 'package:alakh_service/core/network/api_client.dart';
import 'package:alakh_service/core/network/token_store.dart';
import 'package:alakh_service/core/settings/app_settings.dart';
import 'package:alakh_service/features/chat/data/chat_api.dart';
import 'package:alakh_service/features/chat/presentation/booking_chat_page.dart';
import 'package:alakh_service/offline/offline_queue.dart';
import 'package:alakh_service/offline/sync_manager.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'booking_chat_test.dart' show ChatServer, msg;

/// [server]'s answers while [up]; no network at all otherwise.
class Switchable implements HttpClientAdapter {
  final HttpClientAdapter server;
  bool up = true;

  Switchable(this.server);

  @override
  Future<ResponseBody> fetch(RequestOptions options, Stream<Uint8List>? requestStream, Future<void>? cancelFuture) {
    if (!up) throw DioException.connectionError(requestOptions: options, reason: 'offline');
    return server.fetch(options, requestStream, cancelFuture);
  }

  @override
  void close({bool force = false}) {}
}

void main() {
  testWidgets('a message written offline waits with a clock, then goes out once back online', (tester) async {
    SharedPreferences.setMockInitialValues({});
    final prefs = await SharedPreferences.getInstance();
    final sent = <String>[];
    final server = ChatServer(
      pages: {
        1: [msg('m1', 'Your slot is at 10', minute: 1)],
      },
      onSend: (r) {
        final body = (r.data as Map)['body'] as String;
        sent.add('$body ${r.headers['Idempotency-Key']}');
        return (status: 201, body: msg('m2', body, mine: true, minute: 5));
      },
    );
    final network = Switchable(server.adapter);
    final client = ApiClient(
      dio: Dio(BaseOptions(baseUrl: 'http://api.test'))..httpClientAdapter = network,
      tokens: MemoryTokenStore(),
    );
    final queue = OfflineQueue(prefs);
    final online = StreamController<bool>.broadcast();
    final sync = SyncManager(queue: queue, dio: client.dio, online: online.stream)..start();

    await tester.pumpWidget(
      BlocProvider.value(
        value: SettingsCubit(prefs),
        child: AppView(
          online: online.stream,
          waiting: _count(queue),
          home: BookingChatPage(bookingId: 'b1', chatApi: ChatApi(client, offline: sync), pollInterval: const Duration(hours: 1)),
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Your slot is at 10'), findsOneWidget);

    network.up = false;
    online.add(false);
    await tester.pump();
    await tester.enterText(find.byType(TextField), 'Running 10 min late');
    await tester.pump();
    await tester.tap(find.byTooltip('Send'));
    await tester.pumpAndSettle();

    expect(find.text('Running 10 min late'), findsOneWidget);
    expect(find.byIcon(Icons.schedule), findsOneWidget);
    expect(find.text("You're offline. 1 change will be sent when you're back online."), findsOneWidget);
    expect(sent, isEmpty);

    network.up = true;
    online.add(true);
    await tester.pumpAndSettle();

    expect(sent, hasLength(1));
    expect(sent.single, startsWith('Running 10 min late '));
    expect(queue.isEmpty, isTrue);
    expect(find.byIcon(Icons.schedule), findsNothing);
    await tester.pumpWidget(const SizedBox());
    await tester.pump(const Duration(seconds: 5)); // let "Back online" go
    sync.dispose(); // stops its retry timer
    online.close();
  });

  testWidgets('a message the server turns down once back online is reported', (tester) async {
    SharedPreferences.setMockInitialValues({});
    final prefs = await SharedPreferences.getInstance();
    final server = ChatServer(
      pages: {1: const []},
      onSend: (r) => (status: 409, body: {'detail': 'This chat is closed'}),
    );
    final network = Switchable(server.adapter);
    final client = ApiClient(
      dio: Dio(BaseOptions(baseUrl: 'http://api.test'))..httpClientAdapter = network,
      tokens: MemoryTokenStore(),
    );
    final sync = SyncManager(queue: OfflineQueue(prefs), dio: client.dio);
    addTearDown(sync.dispose);

    await tester.pumpWidget(MaterialApp(
      home: BookingChatPage(bookingId: 'b1', chatApi: ChatApi(client, offline: sync), pollInterval: const Duration(hours: 1)),
    ));
    await tester.pumpAndSettle();

    network.up = false;
    await tester.enterText(find.byType(TextField), 'See you');
    await tester.pump();
    await tester.tap(find.byTooltip('Send'));
    await tester.pumpAndSettle();
    expect(find.byIcon(Icons.schedule), findsOneWidget);

    network.up = true;
    sync.sync();
    await tester.pumpAndSettle();

    expect(find.text('A message could not be sent: This chat is closed'), findsOneWidget);
    expect(find.byIcon(Icons.schedule), findsNothing);
    await tester.pumpWidget(const SizedBox());
  });
}

ValueNotifier<int> _count(OfflineQueue queue) {
  final count = ValueNotifier(queue.items.length);
  queue.pending.addListener(() => count.value = queue.pending.value.length);
  return count;
}
