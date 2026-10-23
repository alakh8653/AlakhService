import 'dart:async';

import 'package:alakh_service/app/app_view.dart';
import 'package:alakh_service/app/offline_banner.dart';
import 'package:alakh_service/core/settings/app_settings.dart';
import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

const offlineText = "You're offline. Showing saved info; bookings will need a connection.";

class _FakeConnectivity extends Fake implements Connectivity {
  _FakeConnectivity(this.now, this.changes);

  final List<ConnectivityResult> now;
  final Stream<List<ConnectivityResult>> changes;

  @override
  Future<List<ConnectivityResult>> checkConnectivity() async => now;

  @override
  Stream<List<ConnectivityResult>> get onConnectivityChanged => changes;
}

/// A screen with state of its own, to check it survives the strip coming and going.
class _Counter extends StatefulWidget {
  const _Counter();

  @override
  State<_Counter> createState() => _CounterState();
}

class _CounterState extends State<_Counter> {
  int taps = 0;

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: const Text('Home')),
        body: TextButton(onPressed: () => setState(() => taps++), child: Text('Tapped $taps')),
      );
}

Future<void> pumpApp(WidgetTester tester, Stream<bool> online, {String language = 'en'}) async {
  SharedPreferences.setMockInitialValues({'language': language});
  final settings = SettingsCubit(await SharedPreferences.getInstance());
  await tester.pumpWidget(BlocProvider.value(value: settings, child: AppView(home: const _Counter(), online: online)));
  await tester.pump();
}

void main() {
  testWidgets('shows the offline strip app-wide, then "Back online" briefly', (tester) async {
    final online = StreamController<bool>(sync: true); // each change reaches the strip before the next frame
    addTearDown(online.close);
    await pumpApp(tester, online.stream);

    online.add(true);
    await tester.pump();
    expect(find.text(offlineText), findsNothing);
    expect(find.text('Back online'), findsNothing); // online from the start: nothing to say

    await tester.tap(find.text('Tapped 0'));
    online.add(false);
    await tester.pump();
    expect(find.text(offlineText), findsOneWidget);
    expect(find.text('Tapped 1'), findsOneWidget); // the screen kept its state

    // Screens pushed on top get it too: it lives above the navigator.
    tester.state<NavigatorState>(find.byType(Navigator)).push(
          MaterialPageRoute<void>(builder: (_) => const Scaffold(body: Text('Booking'))),
        );
    await tester.pumpAndSettle();
    expect(find.text('Booking'), findsOneWidget);
    expect(find.text(offlineText), findsOneWidget);

    online.add(true);
    await tester.pump();
    expect(find.text(offlineText), findsNothing);
    expect(find.text('Back online'), findsOneWidget);

    await tester.pump(const Duration(seconds: 3));
    expect(find.text('Back online'), findsNothing);
  });

  testWidgets('reads in Hindi when the app does', (tester) async {
    await pumpApp(tester, Stream.value(false), language: 'hi');
    expect(find.text('आप ऑफ़लाइन हैं। सेव की गई जानकारी दिख रही है; बुकिंग के लिए इंटरनेट चाहिए।'), findsOneWidget);
  });

  test('online status starts from the current state and follows changes', () async {
    final changes = StreamController<List<ConnectivityResult>>();
    final status = onlineStatus(_FakeConnectivity([ConnectivityResult.none], changes.stream));
    final seen = <bool>[];
    final sub = status.listen(seen.add);
    await Future<void>.delayed(Duration.zero);
    changes
      ..add([ConnectivityResult.wifi])
      ..add([ConnectivityResult.mobile, ConnectivityResult.vpn])
      ..add([ConnectivityResult.none]);
    await Future<void>.delayed(Duration.zero);
    expect(seen, [false, true, true, false]);
    await sub.cancel();
    await changes.close();
  });
}
