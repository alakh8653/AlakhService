import 'package:alakh_service/app/home_shell.dart';
import 'package:alakh_service/core/network/api_client.dart';
import 'package:alakh_service/core/network/token_store.dart';
import 'package:alakh_service/features/auth/domain/entities/user.dart';
import 'package:alakh_service/features/jobs/data/jobs_api.dart';
import 'package:alakh_service/features/shop_line/data/shop_line_api.dart';
import 'package:alakh_service/features/shop_owner/data/shop_owner_api.dart';
import 'package:alakh_service/shared/widgets/bottom_nav_bar.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  group('remembering why someone joined', () {
    test('nothing saved means a customer', () async {
      SharedPreferences.setMockInitialValues({});
      expect(await OwnerIntent.read(), isFalse);
    });

    test('offering services is remembered, and can be taken back', () async {
      SharedPreferences.setMockInitialValues({});
      await OwnerIntent.save(true);
      expect(await OwnerIntent.read(), isTrue);
      await OwnerIntent.save(false);
      expect(await OwnerIntent.read(), isFalse);
    });
  });

  group('booking services and running a business, in one app', () {
    test('a customer sees only the booking tabs', () {
      expect(visibleTabs(businessMode: false, ownsShop: false, hasJobs: false),
          [HomeTab.home, HomeTab.services, HomeTab.bookings, HomeTab.profile]);
    });

    test('working, an owner sees only their business', () {
      expect(visibleTabs(businessMode: true, ownsShop: true, hasJobs: true), [HomeTab.shop, HomeTab.jobs, HomeTab.profile]);
      expect(visibleTabs(businessMode: true, ownsShop: true, hasJobs: false), [HomeTab.shop, HomeTab.profile]);
    });

    test('booking, an owner sees what any customer sees, not their jobs', () {
      expect(visibleTabs(businessMode: false, ownsShop: true, hasJobs: true),
          [HomeTab.home, HomeTab.services, HomeTab.bookings, HomeTab.profile]);
    });

    test('staff with no shop keep Jobs, since they have no business side', () {
      expect(visibleTabs(businessMode: false, ownsShop: false, hasJobs: true),
          [HomeTab.home, HomeTab.services, HomeTab.bookings, HomeTab.jobs, HomeTab.profile]);
    });

    test('a stale business setting with no shop still shows the booking tabs', () {
      expect(visibleTabs(businessMode: true, ownsShop: false, hasJobs: false).first, HomeTab.home);
    });

    testWidgets('the bar on the business side has only its own tabs', (tester) async {
      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          bottomNavigationBar: AppBottomNavBar(currentIndex: 0, onTap: (_) {}, showShopLine: true, showJobs: true, businessMode: true),
        ),
      ));
      expect(find.text('My shop'), findsOneWidget);
      expect(find.text('Jobs'), findsOneWidget);
      expect(find.text('Profile'), findsOneWidget);
      expect(find.text('Home'), findsNothing);
      expect(find.text('Bookings'), findsNothing);
    });
  });

  test('the shell still takes its API overrides', () {
    final user = User(
      id: 'u1',
      name: 'Ravi',
      phone: '+919876543210',
      role: 'user',
      isVerified: true,
      createdAt: DateTime(2026),
    );
    final client = ApiClient(dio: Dio(), tokens: MemoryTokenStore());
    final shell = HomeShell(
      user: user,
      jobsApi: JobsApi(client),
      shopLineApi: ShopLineApi(client),
      ownerApi: ShopOwnerApi(client),
    );
    expect(shell.ownerApi, isNotNull);
  });
}
