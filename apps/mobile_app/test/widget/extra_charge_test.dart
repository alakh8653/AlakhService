import 'package:alakh_service/core/network/api_client.dart';
import 'package:alakh_service/core/network/token_store.dart';
import 'package:alakh_service/features/auth/domain/entities/user.dart';
import 'package:alakh_service/features/booking/data/datasources/booking_remote_datasource.dart';
import 'package:alakh_service/features/booking/data/extra_charge_api.dart';
import 'package:alakh_service/features/booking/data/repositories/booking_repository_impl.dart';
import 'package:alakh_service/features/booking/presentation/pages/booking_details_page.dart';
import 'package:alakh_service/features/chat/data/chat_api.dart';
import 'package:alakh_service/features/payment/data/payment_api.dart';
import 'package:alakh_service/features/shop_line/data/shop_line_api.dart';
import 'package:alakh_service/features/shop_owner/data/shop_owner_api.dart';
import 'package:alakh_service/features/shop_owner/presentation/owner_home_page.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../support/fake_adapter.dart';
import 'booking_history_page_test.dart' show Online, booking;

void main() {
  group('the customer', () {
    late Map<String, dynamic> current;
    late FakeAdapter adapter;

    setUp(() {
      current = {
        ...booking('b1', 'IN_PROGRESS', DateTime.now().add(const Duration(days: 1)).toUtc().toIso8601String()),
        'total_amount': 100000,
        'pending_extra_id': 'c1',
        'pending_extra_amount': 50000,
        'pending_extra_reason': 'New capacitor needed',
      };
      adapter = FakeAdapter((RequestOptions r) {
        if (r.path.endsWith('/approve')) {
          current = {...current, 'total_amount': 150000, 'extra_amount': 50000, 'pending_extra_id': null};
          return (status: 200, body: current);
        }
        if (r.path.endsWith('/decline')) {
          current = {...current, 'pending_extra_id': null};
          return (status: 200, body: current);
        }
        if (r.path.endsWith('/payments')) return (status: 200, body: <Object>[]);
        if (r.path.endsWith('/messages')) {
          return (status: 200, body: {'items': <Object>[], 'total': 0, 'page': 1, 'per_page': 1, 'unread': 0, 'can_send': true, 'calling_enabled': false});
        }
        return (status: 200, body: current);
      });
    });

    Future<void> pump(WidgetTester tester) async {
      tester.view.physicalSize = const Size(1200, 4000);
      addTearDown(tester.view.resetPhysicalSize);
      final client = ApiClient(dio: fakeDio(adapter), tokens: MemoryTokenStore());
      await tester.pumpWidget(MaterialApp(
        home: BookingDetailsPage(
          bookingId: 'b1',
          repository: BookingRepositoryImpl(remoteDataSource: BookingRemoteDataSourceImpl(apiClient: client), networkInfo: Online()),
          paymentApi: PaymentApi(client),
          chatApi: ChatApi(client),
          extraChargeApi: ExtraChargeApi(client),
        ),
      ));
      await tester.pumpAndSettle();
    }

    testWidgets('sees how much more, why, and the new total before answering', (tester) async {
      await pump(tester);
      expect(find.text('Extra charge to approve'), findsOneWidget);
      expect(find.text('₹500 more: New capacitor needed'), findsOneWidget);
      expect(find.text('New total if you approve: ₹1,500'), findsOneWidget);
    });

    testWidgets('approving asks first, then updates the price', (tester) async {
      await pump(tester);
      await tester.tap(find.widgetWithText(FilledButton, 'Approve'));
      await tester.pumpAndSettle();
      expect(adapter.requests.any((r) => r.path.endsWith('/approve')), isFalse);
      expect(find.text('Pay ₹500 more?'), findsOneWidget);
      await tester.tap(find.text('Yes, approve'));
      await tester.pumpAndSettle();
      expect(adapter.requests.any((r) => r.path.endsWith('/extra-charges/c1/approve')), isTrue);
      expect(find.text('Extra charge to approve'), findsNothing);
      expect(find.text('Includes ₹500 extra you approved'), findsOneWidget);
    });

    testWidgets('declining keeps the price', (tester) async {
      await pump(tester);
      await tester.tap(find.widgetWithText(OutlinedButton, 'Decline'));
      await tester.pumpAndSettle();
      expect(adapter.requests.any((r) => r.path.endsWith('/extra-charges/c1/decline')), isTrue);
      expect(find.text('Extra charge to approve'), findsNothing);
    });
  });

  group('the owner', () {
    Map<String, Object?> shop() => {'id': 's1', 'name': 'Ravi', 'owner_id': 'u1', 'category': 'electrical', 'verification_status': 'APPROVED'};

    Map<String, Object?> bookingJson({String status = 'IN_PROGRESS', String paid = 'UNPAID', String? pending}) => {
          'id': 'b1',
          'booking_number': 'BK1',
          'customer_display_name': 'Asha R.',
          'service_id': 'svc1',
          'status': status,
          'scheduled_at': '2026-11-03T06:00:00Z',
          'service_mode': 'AT_HOME',
          'total_amount': 100000,
          'payment_status': paid,
          'pending_extra_id': pending,
          'pending_extra_amount': pending == null ? null : 50000,
          'pending_extra_reason': pending == null ? null : 'Parts',
        };

    FakeAdapter adapterFor(Map<String, Object?> b) => FakeAdapter((RequestOptions r) {
          if (r.path.contains('/extra-charges')) return (status: 201, body: b);
          if (r.path.contains('/bookings/shop/')) {
            return (status: 200, body: {'items': [b], 'total': 1, 'page': 1, 'per_page': 100});
          }
          if (r.path.endsWith('/services') || r.path.contains('/services')) return (status: 200, body: <Object>[]);
          return (status: 200, body: shop());
        });

    Future<void> pump(WidgetTester tester, FakeAdapter adapter) async {
      tester.view.physicalSize = const Size(1200, 4000);
      addTearDown(tester.view.resetPhysicalSize);
      final client = ApiClient(dio: fakeDio(adapter), tokens: MemoryTokenStore());
      final api = ShopOwnerApi(client);
      await tester.pumpWidget(MaterialApp(
        home: OwnerHomePage(
          shop: const OwnedShop('s1', 'Ravi', {'svc1': 'Fan repair'}),
          user: User(id: 'u1', name: 'Ravi', phone: '+919876543210', role: 'user', isVerified: true, createdAt: DateTime(2026)),
          api: api,
          extraChargeApi: ExtraChargeApi(client),
          refreshEvery: const Duration(hours: 1),
        ),
      ));
      await tester.pumpAndSettle();
    }

    testWidgets('asks with a tap for the reason and the amount typed', (tester) async {
      final adapter = adapterFor(bookingJson());
      await pump(tester, adapter);
      await tester.tap(find.text('Add extra charge'));
      await tester.pumpAndSettle();
      expect(find.textContaining('The customer must approve'), findsOneWidget);
      await tester.tap(find.text('Spare parts'));
      await tester.pump();
      await tester.enterText(find.byKey(const ValueKey('extra-amount')), '500');
      await tester.tap(find.text('Send to customer'));
      await tester.pumpAndSettle();
      final sent = adapter.requests.firstWhere((r) => r.path.endsWith('/extra-charges') && r.method == 'POST');
      expect(sent.data['amount_cents'], 50000);
      expect(sent.data['reason'], 'Spare parts');
    });

    testWidgets('a request waiting shows, and can be taken back', (tester) async {
      final adapter = adapterFor(bookingJson(pending: 'c1'));
      await pump(tester, adapter);
      expect(find.text('Waiting for the customer: ₹500 more (Parts)'), findsOneWidget);
      expect(find.text('Add extra charge'), findsNothing);
      await tester.tap(find.text('Take back'));
      await tester.pumpAndSettle();
      expect(adapter.requests.any((r) => r.method == 'DELETE' && r.path.endsWith('/extra-charges/c1')), isTrue);
    });

    testWidgets('a paid or new booking offers no extra charge', (tester) async {
      await pump(tester, adapterFor(bookingJson(paid: 'PAID')));
      expect(find.text('Add extra charge'), findsNothing);
      await pump(tester, adapterFor(bookingJson(status: 'PENDING')));
      expect(find.text('Add extra charge'), findsNothing);
    });
  });
}
