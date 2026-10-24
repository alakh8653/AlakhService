import 'package:alakh_service/core/network/api_client.dart';
import 'package:alakh_service/core/network/token_store.dart';
import 'package:alakh_service/features/auth/data/datasources/auth_remote_datasource.dart';
import 'package:alakh_service/features/auth/presentation/pages/register_page.dart';
import 'package:alakh_service/features/legal/data/legal_api.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../support/fake_adapter.dart';
import 'auth_flow_test.dart' show FakeAuth, app, blocFor;

LegalApi legalFrom(FakeAdapter adapter) => LegalApi(ApiClient(dio: fakeDio(adapter), tokens: MemoryTokenStore()));

Future<void> fillForm(WidgetTester tester) async {
  await tester.enterText(find.byType(TextFormField).at(0), 'Priya Sharma');
  await tester.enterText(find.byType(TextFormField).at(1), '9876543210');
  await tester.enterText(find.byType(TextFormField).at(2), 'Passw0rd!');
}

Future<void> submit(WidgetTester tester) async {
  await tester.ensureVisible(find.text('Create account'));
  await tester.tap(find.text('Create account'));
  await tester.pump();
}

void main() {
  final current = FakeAdapter((_) => (
        status: 200,
        body: {
          'terms_version': '2026-11',
          'terms_url': 'https://legal.test/terms',
          'privacy_url': 'https://legal.test/privacy',
          'refund_url': 'https://legal.test/refunds',
          'grievance_url': 'https://legal.test/grievance',
        },
      ));

  testWidgets('sign-up needs the Terms ticked', (tester) async {
    final repo = FakeAuth();
    await tester.pumpWidget(app(blocFor(repo), home: RegisterPage(legalApi: legalFrom(current))));
    await tester.pumpAndSettle();
    await fillForm(tester);
    await submit(tester);

    expect(find.text('Please accept the Terms and Privacy Policy'), findsOneWidget);
    expect(repo.calls, isEmpty);
  });

  testWidgets('sends the Terms version from the server, and the links open its pages', (tester) async {
    final repo = FakeAuth();
    final opened = <Uri>[];
    await tester.pumpWidget(app(
      blocFor(repo),
      home: RegisterPage(legalApi: legalFrom(current), open: (uri) async {
        opened.add(uri);
        return true;
      }),
    ));
    await tester.pumpAndSettle();
    await fillForm(tester);

    await tester.ensureVisible(find.text('Privacy Policy'));
    await tester.tap(find.text('Terms of Service'));
    await tester.tap(find.text('Privacy Policy'));
    expect(opened.map((u) => u.toString()), ['https://legal.test/terms', 'https://legal.test/privacy']);

    await tester.tap(find.byType(Checkbox));
    await submit(tester);
    await tester.pumpAndSettle();
    expect(repo.calls.first, 'register 9876543210');
    expect(repo.termsVersion, '2026-11');
  });

  testWidgets('falls back to the build\'s Terms version when the server can\'t say', (tester) async {
    final repo = FakeAuth();
    final down = FakeAdapter((_) => (status: 503, body: {'detail': 'down'}));
    await tester.pumpWidget(app(blocFor(repo), home: RegisterPage(legalApi: legalFrom(down))));
    await tester.pumpAndSettle();
    await fillForm(tester);
    await tester.ensureVisible(find.byType(Checkbox));
    await tester.tap(find.byType(Checkbox));
    await submit(tester);
    await tester.pumpAndSettle();
    expect(repo.termsVersion, '2026-10');
  });

  test('registration sends accepted_terms_version to auth_service', () async {
    final adapter = FakeAdapter((_) => (status: 201, body: {'id': 'u1'}));
    await AuthRemoteDataSourceImpl(apiClient: ApiClient(dio: fakeDio(adapter), tokens: MemoryTokenStore()))
        .register(name: 'Priya', phone: '9876543210', password: 'Passw0rd!', acceptedTermsVersion: '2026-11');
    expect(adapter.requests.single.data, containsPair('accepted_terms_version', '2026-11'));
  });
}
