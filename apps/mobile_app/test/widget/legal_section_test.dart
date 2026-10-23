import 'package:alakh_service/core/network/api_client.dart';
import 'package:alakh_service/core/network/token_store.dart';
import 'package:alakh_service/features/legal/data/legal_api.dart';
import 'package:alakh_service/features/profile/data/data_export_api.dart';
import 'package:alakh_service/features/profile/presentation/pages/legal_section.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../support/fake_adapter.dart';

void main() {
  testWidgets('legal links open in the browser, and Download my data asks compliance for an export',
      (tester) async {
    final exports = <Map<String, dynamic>>[];
    final adapter = FakeAdapter((r) {
      if (r.path.endsWith('/legal/current')) return (status: 503, body: null);
      if (r.method == 'POST') {
        final created = {'id': 'e1', 'user_id': 'u1', 'status': 'PENDING', 'requested_at': DateTime.now().toUtc().toIso8601String()};
        exports.add(created);
        return (status: 201, body: created);
      }
      return (status: 200, body: exports);
    });
    final client = ApiClient(dio: fakeDio(adapter), tokens: MemoryTokenStore());
    final opened = <String>[];
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: SingleChildScrollView(
          child: LegalSection(
            userId: 'u1',
            legalApi: LegalApi(client),
            dataExportApi: DataExportApi(client),
            open: (uri) async {
              opened.add(uri.toString());
              return true;
            },
          ),
        ),
      ),
    ));
    await tester.pumpAndSettle();

    // The server gave no links: the build's own pages are used.
    await tester.tap(find.text('Refund policy'));
    expect(opened, ['${LegalLinks.baseUrl}/refunds']);

    expect(find.text('Get a copy of your account, bookings and payments'), findsOneWidget);
    await tester.tap(find.text('Download my data'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Request'));
    await tester.pumpAndSettle();

    final post = adapter.requests.singleWhere((r) => r.method == 'POST');
    expect(post.path, '/api/v1/gdpr/export');
    expect(post.data, {'user_id': 'u1'});
    expect(find.text('Requested: Today. We\'re preparing it.'), findsOneWidget);
  });
}
