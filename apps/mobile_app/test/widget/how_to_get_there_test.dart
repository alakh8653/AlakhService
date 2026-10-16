import 'package:alakh_service/core/network/api_client.dart';
import 'package:alakh_service/core/network/token_store.dart';
import 'package:alakh_service/features/directions/data/shop_location_api.dart';
import 'package:alakh_service/features/directions/presentation/how_to_get_there_sheet.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

import '../support/fake_adapter.dart';

Widget sheet(Map<String, dynamic> shop, List<Uri> opened) => MaterialApp(
      home: Scaffold(
        body: HowToGetThereSheet(
          key: ValueKey(shop['id']), // a different shop is a fresh sheet
          shopId: 'sh1',
          api: ShopLocationApi(ApiClient(dio: fakeDio(FakeAdapter((_) => (status: 200, body: shop))), tokens: MemoryTokenStore())),
          open: (uri) async {
            opened.add(uri);
            return true;
          },
        ),
      ),
    );

void main() {
  const pinned = {'id': 'sh1', 'name': 'Demo Salon', 'address': '12 MG Road', 'city': 'Pune', 'latitude': 18.5204, 'longitude': 73.8567};

  testWidgets('offers own vehicle, public transport, walking and Uber, and opens the right link', (tester) async {
    final opened = <Uri>[];
    await tester.pumpWidget(sheet(pinned, opened));
    await tester.pumpAndSettle();

    expect(find.text('Demo Salon'), findsOneWidget);
    expect(find.text('12 MG Road, Pune'), findsOneWidget);
    for (final title in ['Drive there', 'Public transport', 'Walk', 'Book an Uber', 'Ola, Rapido or another ride app']) {
      expect(find.text(title), findsOneWidget, reason: title);
    }
    await tester.tap(find.text('Public transport'));
    await tester.tap(find.text('Book an Uber'));
    expect(opened.map((u) => u.host), ['www.google.com', 'm.uber.com']);
    expect(opened.first.queryParameters['travelmode'], 'transit');
  });

  testWidgets('copies the address for other ride apps', (tester) async {
    String? copied;
    tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(SystemChannels.platform, (call) async {
      if (call.method == 'Clipboard.setData') copied = (call.arguments as Map)['text'] as String;
      return null;
    });
    await tester.pumpWidget(sheet(pinned, []));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Ola, Rapido or another ride app'));
    await tester.pump();
    expect(copied, 'Demo Salon, 12 MG Road, Pune');
    expect(find.textContaining('Paste it as the drop-off'), findsOneWidget);
  });

  testWidgets('without a map position there is no Uber link, and without an address it says so', (tester) async {
    await tester.pumpWidget(sheet({'id': 'sh1', 'name': 'Demo Salon', 'address': '12 MG Road', 'city': 'Pune'}, []));
    await tester.pumpAndSettle();
    expect(find.text('Drive there'), findsOneWidget);
    expect(find.text('Book an Uber'), findsNothing);

    await tester.pumpWidget(sheet({'id': 'sh2', 'name': 'New Shop'}, []));
    await tester.pumpAndSettle();
    expect(find.textContaining("hasn't added its address"), findsOneWidget);
  });
}
