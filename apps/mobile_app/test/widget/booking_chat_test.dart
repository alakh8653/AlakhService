import 'package:alakh_service/core/network/api_client.dart';
import 'package:alakh_service/core/network/token_store.dart';
import 'package:alakh_service/features/chat/data/chat_api.dart';
import 'package:alakh_service/features/chat/presentation/booking_chat_page.dart';
import 'package:alakh_service/l10n/l10n.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../support/fake_adapter.dart';

Map<String, dynamic> msg(String id, String body, {bool mine = false, bool flagged = false, String? readAt, int minute = 0}) => {
      'id': id,
      'booking_id': 'b1',
      'sender_role': mine ? 'customer' : 'shop',
      'sender_name': mine ? 'Ravi S.' : 'Shop',
      'is_mine': mine,
      'body': body,
      'flagged': flagged,
      'created_at': DateTime.utc(2026, 10, 23, 9, minute).toIso8601String(),
      'read_at': readAt,
    };

/// booking_service's chat for booking b1: [pages] by page number (1 = newest), and the thread's flags.
class ChatServer {
  Map<int, List<Map<String, dynamic>>> pages;
  int perPage;
  int unread;
  bool canSend;
  String? openUntil;
  bool callingEnabled;
  ({int status, Object? body}) Function(RequestOptions r)? onSend;
  ({int status, Object? body}) Function(RequestOptions r)? onCall;

  ChatServer({
    required this.pages,
    this.perPage = 30,
    this.unread = 0,
    this.canSend = true,
    this.openUntil,
    this.callingEnabled = false,
    this.onSend,
    this.onCall,
  });

  late final adapter = FakeAdapter((r) {
    if (r.path.endsWith('/messages/read')) return (status: 200, body: {'marked': unread});
    if (r.path.endsWith('/call')) return onCall?.call(r) ?? (status: 501, body: {'detail': 'Calling is not enabled'});
    if (r.method == 'POST') {
      return onSend?.call(r) ??
          (status: 201, body: msg('new', (r.data as Map)['body'] as String, mine: true, minute: 59));
    }
    final page = (r.queryParameters['page'] as int?) ?? 1;
    final total = pages.values.fold<int>(0, (n, p) => n + p.length);
    return (
      status: 200,
      body: {
        'items': pages[page] ?? const [],
        'total': total,
        'page': page,
        'per_page': perPage,
        'unread': unread,
        'can_send': canSend,
        'open_until': openUntil,
        'calling_enabled': callingEnabled,
      },
    );
  });

  Iterable<RequestOptions> get reads => adapter.requests.where((r) => r.path.endsWith('/messages/read'));
}

Widget chatPage(ChatServer server, {Locale? locale}) => MaterialApp(
      locale: locale,
      supportedLocales: AppLocalizations.supportedLocales,
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      home: BookingChatPage(
        bookingId: 'b1',
        subtitle: 'Haircut',
        chatApi: ChatApi(ApiClient(dio: fakeDio(server.adapter), tokens: MemoryTokenStore())),
      ),
    );

/// Disposes the page so its poll timer stops before the test ends.
Future<void> closePage(WidgetTester tester) => tester.pumpWidget(const SizedBox());

void main() {
  testWidgets('shows my and the shop\'s messages, hides numbers, flags and receipts, and marks read on open',
      (tester) async {
    final server = ChatServer(unread: 1, pages: {
      1: [
        msg('m1', 'Hi, is 10am fine?', mine: true, readAt: DateTime.utc(2026, 10, 23, 9, 2).toIso8601String()),
        msg('m2', 'Yes. Call me on 98765 43210', flagged: true, minute: 3),
        msg('m3', 'See you then', mine: true, minute: 4),
      ],
    });
    await tester.pumpWidget(chatPage(server));
    await tester.pumpAndSettle();

    expect(find.text('Hi, is 10am fine?'), findsOneWidget);
    expect(find.text('Shop'), findsOneWidget);
    // The number never shows, even if the server missed it.
    expect(find.textContaining('98765'), findsNothing);
    expect(find.text('Yes. Call me on •••'), findsOneWidget);
    expect(find.text('Contact details are hidden to keep you safe'), findsOneWidget);
    // The first of mine was read by the shop, the second only sent.
    expect(find.byIcon(Icons.done_all), findsOneWidget);
    expect(find.byIcon(Icons.done), findsOneWidget);
    // My messages sit on the right, the shop's on the left.
    expect(tester.getCenter(find.text('See you then')).dx, greaterThan(tester.getCenter(find.text('Shop')).dx));
    expect(server.reads, hasLength(1));
    // No calling on this booking: no button.
    expect(find.text('Call shop'), findsNothing);
    await closePage(tester);
  });

  testWidgets('loads earlier pages on request', (tester) async {
    final server = ChatServer(perPage: 2, pages: {
      1: [msg('m2', 'Second', minute: 2), msg('m3', 'Third', minute: 3)],
      2: [msg('m1', 'First', minute: 1)],
    });
    await tester.pumpWidget(chatPage(server));
    await tester.pumpAndSettle();
    expect(find.text('First'), findsNothing);
    expect(server.reads, isEmpty, reason: 'nothing unread');

    await tester.tap(find.text('Load earlier messages'));
    await tester.pumpAndSettle();
    expect(find.text('First'), findsOneWidget);
    expect(find.text('Load earlier messages'), findsNothing);
    expect(server.adapter.requests.last.queryParameters['page'], 2);
    await closePage(tester);
  });

  testWidgets('checks for new messages every 10 seconds while open', (tester) async {
    final server = ChatServer(pages: {
      1: [msg('m1', 'Hello', mine: true)],
    });
    await tester.pumpWidget(chatPage(server));
    await tester.pumpAndSettle();

    server.pages = {
      1: [
        msg('m1', 'Hello', mine: true, readAt: DateTime.utc(2026, 10, 23, 9, 1).toIso8601String()),
        msg('m2', 'Hello! We are open till 8', minute: 2),
      ],
    };
    server.unread = 1;
    await tester.pump(const Duration(seconds: 10));
    await tester.pumpAndSettle();

    expect(find.text('Hello! We are open till 8'), findsOneWidget);
    expect(find.byIcon(Icons.done_all), findsOneWidget, reason: 'the receipt updates too');
    expect(server.reads, hasLength(1));
    await closePage(tester);
  });

  testWidgets('sends a message, and shows the server\'s reason when it refuses one', (tester) async {
    var calls = 0;
    final server = ChatServer(
      pages: {1: []},
      onSend: (r) => ++calls == 1
          ? (status: 201, body: msg('new', 'On my way', mine: true, minute: 30))
          : (status: 429, body: {'detail': "You're sending messages too quickly. Please wait a moment."}),
    );
    await tester.pumpWidget(chatPage(server));
    await tester.pumpAndSettle();
    expect(find.text('No messages yet. Ask the shop anything about this booking.'), findsOneWidget);

    await tester.enterText(find.byType(TextField), 'On my way');
    await tester.pump();
    await tester.tap(find.byTooltip('Send'));
    await tester.pumpAndSettle();
    expect(find.text('On my way'), findsOneWidget);
    expect(tester.widget<TextField>(find.byType(TextField)).controller!.text, isEmpty);

    await tester.enterText(find.byType(TextField), 'Again');
    await tester.pump();
    await tester.tap(find.byTooltip('Send'));
    await tester.pumpAndSettle();
    expect(find.text("You're sending messages too quickly. Please wait a moment."), findsOneWidget);
    await closePage(tester);
  });

  testWidgets('a closed chat is read-only and says since when', (tester) async {
    final server = ChatServer(
      canSend: false,
      openUntil: DateTime.utc(2026, 10, 20, 12).toIso8601String(),
      pages: {
        1: [msg('m1', 'Thanks for coming')],
      },
    );
    await tester.pumpWidget(chatPage(server));
    await tester.pumpAndSettle();

    expect(find.byType(TextField), findsNothing);
    expect(find.textContaining('This chat closed'), findsOneWidget);
    expect(find.textContaining('You can still read it.'), findsOneWidget);
    await closePage(tester);
  });

  testWidgets('a 409 on sending turns the chat read-only', (tester) async {
    final server = ChatServer(pages: {1: []});
    server.onSend = (r) {
      server.canSend = false;
      return (status: 409, body: {'detail': 'This booking is closed; its chat is read-only'});
    };
    await tester.pumpWidget(chatPage(server));
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField), 'Hello?');
    await tester.pump();
    await tester.tap(find.byTooltip('Send'));
    await tester.pumpAndSettle();

    expect(find.text('This booking is closed; its chat is read-only'), findsOneWidget);
    expect(find.byType(TextField), findsNothing);
    await closePage(tester);
  });

  testWidgets('Call shop shows only when calling is on, with the server\'s message', (tester) async {
    final server = ChatServer(
      callingEnabled: true,
      pages: {1: []},
      onCall: (_) => (
        status: 202,
        body: {'status': 'ringing', 'call_id': 'c1', 'callee': 'shop', 'message': "We're calling you now. Pick up to be connected."},
      ),
    );
    await tester.pumpWidget(chatPage(server));
    await tester.pumpAndSettle();

    await tester.tap(find.text('Call shop'));
    await tester.pumpAndSettle();
    expect(find.text("We're calling you now. Pick up to be connected."), findsOneWidget);
    await closePage(tester);
  });

  testWidgets('reads in Hindi', (tester) async {
    final server = ChatServer(pages: {
      1: [msg('m1', 'नमस्ते', flagged: true)],
    }, canSend: false);
    await tester.pumpWidget(chatPage(server, locale: const Locale('hi')));
    await tester.pumpAndSettle();

    expect(find.text('दुकान से चैट'), findsOneWidget);
    expect(find.text('आपकी सुरक्षा के लिए संपर्क जानकारी छिपाई गई है'), findsOneWidget);
    expect(find.text('यह चैट बंद हो गई है। आप इसे अब भी पढ़ सकते हैं।'), findsOneWidget);
    await closePage(tester);
  });

  test('numbers are hidden from message text, other figures kept', () {
    expect(hidePhoneNumbers('Call +91 98765-43210 now'), 'Call ••• now');
    expect(hidePhoneNumbers('It costs ₹1,200 and takes 45 min'), 'It costs ₹1,200 and takes 45 min');
  });
}
