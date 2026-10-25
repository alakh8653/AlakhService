import 'package:alakh_service/core/network/api_client.dart';
import 'package:alakh_service/core/network/token_store.dart';
import 'package:alakh_service/features/profile/data/address_api.dart';
import 'package:alakh_service/features/profile/presentation/pages/addresses_page.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../support/fake_adapter.dart';

Widget page(FakeAdapter adapter) =>
    MaterialApp(home: AddressesPage(addressApi: AddressApi(ApiClient(dio: fakeDio(adapter), tokens: MemoryTokenStore()))));

void main() {
  testWidgets('deleting an address asks first and confirms', (tester) async {
    var deleted = false;
    final adapter = FakeAdapter((r) {
      if (r.method == 'DELETE') {
        deleted = true;
        return (status: 204, body: null);
      }
      return (
        status: 200,
        body: deleted
            ? <Object>[]
            : [
                {'id': 'a1', 'label': 'Home', 'street': '12 MG Road', 'city': 'Pune', 'state': 'MH', 'postal_code': '411001', 'is_default': true},
              ],
      );
    });
    await tester.pumpWidget(page(adapter));
    await tester.pumpAndSettle();

    await tester.tap(find.byTooltip('Options for Home'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Delete'));
    await tester.pumpAndSettle();
    expect(find.text('Delete "Home"?'), findsOneWidget);
    await tester.tap(find.text('Keep it'));
    await tester.pumpAndSettle();
    expect(deleted, isFalse);

    await tester.tap(find.byTooltip('Options for Home'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Delete'));
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(TextButton, 'Delete'));
    await tester.pumpAndSettle();

    expect(deleted, isTrue);
    expect(find.text('Address deleted'), findsOneWidget);
    expect(find.text('No saved addresses yet'), findsOneWidget);
    expect(find.text('Add address'), findsOneWidget); // the empty state leads somewhere
  });

  testWidgets('a failed load can be retried', (tester) async {
    var calls = 0;
    final adapter = FakeAdapter((_) => ++calls == 1 ? (status: 503, body: {'detail': 'Service unavailable'}) : (status: 200, body: <Object>[]));
    await tester.pumpWidget(page(adapter));
    await tester.pumpAndSettle();

    expect(find.text('Try Again'), findsOneWidget);
    await tester.tap(find.text('Try Again'));
    await tester.pumpAndSettle();
    expect(find.text('No saved addresses yet'), findsOneWidget);
  });
}
