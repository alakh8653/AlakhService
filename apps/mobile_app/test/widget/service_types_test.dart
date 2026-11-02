import 'package:alakh_service/core/network/api_client.dart';
import 'package:alakh_service/core/network/token_store.dart';
import 'package:alakh_service/features/auth/domain/entities/user.dart';
import 'package:alakh_service/features/home/presentation/pages/all_services_page.dart';
import 'package:alakh_service/features/shop_owner/data/shop_owner_api.dart';
import 'package:alakh_service/features/shop_owner/presentation/shop_setup_page.dart';
import 'package:alakh_service/l10n/app_localizations.dart';
import 'package:alakh_service/shared/service_types.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../support/fake_adapter.dart';

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  group('the list of service types', () {
    test('ids are unique, and the ones shops are already saved with are all still there', () {
      final ids = serviceTypes.map((t) => t.id).toList();
      expect(ids.toSet(), hasLength(ids.length));
      expect(ids, containsAll(const [
        'salon', 'beauty', 'spa', 'clinic', 'vehicle_repair', 'electronics_repair', 'appliance_repair', 'cleaning',
        'plumbing', 'electrical', 'repair', 'office', 'other',
      ]));
    });

    test('everything on the home screen is a real type', () {
      for (final id in homeServiceTypeIds) {
        expect(serviceTypeById(id), isNotNull, reason: id);
      }
    });

    test('every type has a name in English and in Hindi, and each group is used', () async {
      final en = await AppLocalizations.delegate.load(const Locale('en'));
      final hi = await AppLocalizations.delegate.load(const Locale('hi'));
      for (final type in serviceTypes) {
        expect(type.label(en), isNotEmpty, reason: type.id);
        expect(type.label(hi), isNot(type.label(en)), reason: '${type.id} is not translated');
      }
      for (final group in ServiceGroup.values) {
        expect(serviceTypes.where((t) => t.group == group), isNotEmpty, reason: '$group');
      }
    });
  });

  testWidgets('All services lists every type by group, and picking one opens it', (tester) async {
    ServiceType? picked;
    await tester.pumpWidget(MaterialApp(
      home: Builder(
        builder: (context) => TextButton(
          onPressed: () => Navigator.push<void>(
            context,
            MaterialPageRoute(builder: (_) => AllServicesPage(onPick: (type) => picked = type)),
          ),
          child: const Text('open'),
        ),
      ),
    ));
    await tester.tap(find.text('open'));
    await tester.pumpAndSettle();
    expect(find.text('Beauty and grooming'), findsOneWidget);
    await tester.scrollUntilVisible(find.text('Carpenter'), 200, scrollable: find.byType(Scrollable).first);
    await tester.ensureVisible(find.text('Carpenter'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Carpenter'));
    await tester.pumpAndSettle();
    expect(picked?.id, 'carpentry');
  });

  testWidgets('setup suggests services for the type of work, and they go into the form', (tester) async {
    tester.view.physicalSize = const Size(1200, 3000);
    addTearDown(tester.view.resetPhysicalSize);
    final adapter = FakeAdapter((RequestOptions r) => (status: 200, body: <String, Object?>{}));
    final user = User(id: 'u1', name: 'Ravi', phone: '+919876543210', role: 'user', isVerified: true, createdAt: DateTime(2026));
    await tester.pumpWidget(MaterialApp(
      home: ShopSetupPage(user: user, api: ShopOwnerApi(ApiClient(dio: fakeDio(adapter), tokens: MemoryTokenStore()))),
    ));
    await tester.pumpAndSettle();
    await tester.tap(find.byType(DropdownButtonFormField<String>));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Salon').last);
    await tester.pumpAndSettle();
    await tester.tap(find.text('At my shop'));
    await tester.pumpAndSettle();
    final fields = find.byType(TextFormField);
    await tester.enterText(fields.at(1), 'Pune');
    await tester.enterText(fields.at(2), '12 MG Road');
    await tester.tap(find.text('Continue'));
    await tester.pumpAndSettle();

    expect(find.text('Haircut'), findsOneWidget);
    await tester.tap(find.text('Haircut'));
    await tester.pumpAndSettle();
    // In the empty form rather than beside it, and no longer offered.
    expect(find.byType(TextFormField), findsNWidgets(3));
    expect(find.widgetWithText(ActionChip, 'Haircut'), findsNothing);
    await tester.tap(find.text('Beard trim'));
    await tester.pumpAndSettle();
    // A second one gets its own form: as many as they like.
    expect(find.byType(TextFormField), findsNWidgets(6));
  });
}
