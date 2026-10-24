import 'package:alakh_service/core/network/api_client.dart';
import 'package:alakh_service/core/network/network_info.dart';
import 'package:alakh_service/core/network/token_store.dart';
import 'package:alakh_service/core/theme/app_theme.dart';
import 'package:alakh_service/features/auth/presentation/pages/forgot_password_page.dart';
import 'package:alakh_service/features/booking/data/availability_api.dart';
import 'package:alakh_service/features/booking/data/datasources/booking_remote_datasource.dart';
import 'package:alakh_service/features/booking/data/repositories/booking_repository_impl.dart';
import 'package:alakh_service/features/booking/domain/usecases/cancel_booking_usecase.dart';
import 'package:alakh_service/features/booking/domain/usecases/create_booking_usecase.dart';
import 'package:alakh_service/features/booking/presentation/bloc/booking_bloc.dart';
import 'package:alakh_service/features/booking/presentation/pages/booking_history_page.dart';
import 'package:alakh_service/features/booking/presentation/pages/booking_page.dart';
import 'package:alakh_service/features/directions/data/shop_location_api.dart';
import 'package:alakh_service/features/payment/data/payment_api.dart';
import 'package:alakh_service/features/payment/presentation/pages/payment_page.dart';
import 'package:alakh_service/features/profile/data/address_api.dart';
import 'package:alakh_service/features/queue/data/queue_api.dart';
import 'package:alakh_service/features/reviews/data/reviews_api.dart';
import 'package:alakh_service/features/services/domain/entities/service_entity.dart';
import 'package:alakh_service/features/services/presentation/pages/service_detail_page.dart';
import 'package:alakh_service/features/shops/data/shop_hours_api.dart';
import 'package:alakh_service/shared/widgets/service_card.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_test/flutter_test.dart';

import '../support/fake_adapter.dart';

class Online implements NetworkInfo {
  @override
  Future<bool> get isConnected async => true;
}

/// A 360 x 640 dp phone with the system text size at 130%.
Future<void> smallPhoneLargeText(WidgetTester tester, Widget home) async {
  tester.view.physicalSize = const Size(720, 1280);
  tester.view.devicePixelRatio = 2;
  addTearDown(tester.view.reset);
  await tester.pumpWidget(MaterialApp(
    theme: AppTheme.lightTheme,
    builder: (context, child) => MediaQuery(
      data: MediaQuery.of(context).copyWith(textScaler: const TextScaler.linear(1.3)),
      child: child!,
    ),
    home: home,
  ));
  await tester.pumpAndSettle();
}

final soon = DateTime.now().add(const Duration(days: 1)).toUtc().toIso8601String();

FakeAdapter backend() => FakeAdapter((r) {
      if (r.path.endsWith('/payments')) return (status: 200, body: <Object>[]);
      if (r.path.endsWith('/addresses')) {
        return (status: 200, body: [
          {'id': 'a1', 'label': 'Home', 'street': 'Flat 402, Sai Krupa Apartments, Near Shivaji Chowk', 'city': 'Pimpri-Chinchwad', 'state': 'Maharashtra', 'postal_code': '411018', 'is_default': true},
        ]);
      }
      if (r.path.endsWith('/reviews/summary')) {
        return (status: 200, body: {
          'average_rating': 4.6,
          'review_count': 1280,
          'distribution': [for (final s in [5, 4, 3, 2, 1]) {'stars': s, 'count': s * 100}],
        });
      }
      if (r.path.endsWith('/reviews')) {
        return (status: 200, body: {
          'total': 1280,
          'items': [
            {
              'id': 'r1', 'rating': 4, 'reviewer_name': 'Venkataraghavan S.', 'created_at': '2026-10-12T09:30:00Z',
              'comment': 'Screen replaced within the promised two hours, and they cleaned the keyboard too.',
              'reply': {'text': 'Thank you! Do come back for the battery check.', 'created_at': '2026-10-13T09:30:00Z', 'updated_at': '2026-10-13T09:30:00Z'},
            },
          ],
        });
      }
      if (r.path.endsWith('/availability')) {
        return (status: 200, body: {
          'hours_configured': true, 'status': 'AVAILABLE',
          'slots': [
            {'start': '2026-10-19T04:30:00Z', 'time': '10:00', 'remaining': 2},
            {'start': '2026-10-19T12:30:00Z', 'time': '18:00', 'remaining': 1},
          ],
        });
      }
      if (r.path.endsWith('/hours')) {
        return (status: 200, body: {
          'configured': true,
          'weekly': [for (var d = 0; d < 7; d++) {'day': d, 'intervals': [{'start': '10:00', 'end': '20:00'}]}],
          'holidays': <Object>[],
        });
      }
      if (r.path.contains('/shops/')) return (status: 200, body: {'name': 'Shree Ganesh Hair & Beauty Studio', 'address': '12 MG Road', 'city': 'Pune'});
      if (r.path.endsWith('/bookings')) {
        return (status: 200, body: {
          'items': [
            {
              'id': 'b1', 'booking_number': 'BK65682921', 'customer_id': 'u1', 'service_id': 's1', 'shop_id': 'shop-1',
              'provider_id': 'p1', 'status': 'PROVIDER_EN_ROUTE', 'scheduled_at': soon, 'total_amount': 12345600,
              'service_mode': 'PICKUP_DROP', 'item_description': 'Dell Inspiron 15, cracked screen and loose hinge',
              'ready_by': soon, 'created_at': soon, 'notes': 'Address: Flat 402, Sai Krupa Apartments, Pune',
            },
            {
              'id': 'b2', 'booking_number': 'BK1', 'customer_id': 'u1', 'service_id': 's1', 'shop_id': 'shop-1',
              'status': 'COMPLETED', 'scheduled_at': soon, 'total_amount': 30000, 'created_at': soon,
            },
          ],
        });
      }
      return (status: 200, body: <Object>[]);
    });

ApiClient client(FakeAdapter adapter) => ApiClient(dio: fakeDio(adapter), tokens: MemoryTokenStore());

BookingBloc bloc(ApiClient c) {
  final repo = BookingRepositoryImpl(remoteDataSource: BookingRemoteDataSourceImpl(apiClient: c), networkInfo: Online());
  return BookingBloc(createBookingUseCase: CreateBookingUseCase(repo), cancelBookingUseCase: CancelBookingUseCase(repo), bookingRepository: repo);
}

const longService = ServiceEntity(
  id: 's1', name: 'Laptop screen replacement with free diagnosis', description: 'Original panels.', category: '',
  basePrice: 124999, priceUnit: '120 min', durationMinutes: 120, shopId: 'shop-1',
  serviceModes: [ServiceMode.atShop, ServiceMode.atHome, ServiceMode.pickupDrop], homeVisitFee: 199, pickupFee: 149,
);

void main() {
  // Any RenderFlex overflow fails these tests.
  testWidgets('booking form fits', (tester) async {
    final c = client(backend());
    await smallPhoneLargeText(tester, BlocProvider(
      create: (_) => bloc(c),
      child: BookingPage(
        serviceId: 's1', serviceName: longService.name, servicePrice: 124999, addressApi: AddressApi(c), availabilityApi: AvailabilityApi(c),
        serviceModes: longService.serviceModes, homeVisitFee: 199, pickupFee: 149,
      ),
    ));
    await tester.tap(find.textContaining('Pickup & drop'));
    await tester.pumpAndSettle();
    expect(find.text('Confirm Booking'), findsOneWidget);
  });

  testWidgets('bookings list fits', (tester) async {
    final c = client(backend());
    await smallPhoneLargeText(tester, BlocProvider(create: (_) => bloc(c), child: BookingHistoryPage(paymentApi: PaymentApi(c))));
    expect(find.text('Booking #BK65682921'), findsOneWidget);
  });

  testWidgets('service details and card fit', (tester) async {
    final c = client(backend());
    await smallPhoneLargeText(tester, ServiceDetailPage(
      service: longService, shopApi: ShopLocationApi(c), queueApi: QueueApi(c), reviewsApi: ReviewsApi(c), hoursApi: ShopHoursApi(c),
    ));
    expect(find.text('Book Now'), findsOneWidget);
    expect(find.textContaining(RegExp('Open now|Closed')), findsOneWidget);
    await tester.scrollUntilVisible(find.text('See all reviews (1280)'), 200);
    expect(find.text('Venkataraghavan S.'), findsOneWidget);
    await smallPhoneLargeText(tester, const Scaffold(body: ServiceCard(service: longService)));
  });

  testWidgets('payment fits', (tester) async {
    await smallPhoneLargeText(tester, PaymentPage(
      amount: 124999, bookingId: 'b1', bookingNumber: 'BK65682921', serviceName: longService.name,
      paymentApi: PaymentApi(client(backend())),
    ));
    expect(find.text('Pay ₹1,24,999'), findsOneWidget);
  });

  testWidgets('forgot password fits', (tester) async {
    await smallPhoneLargeText(tester, const ForgotPasswordPage());
    expect(find.text('Send Code'), findsOneWidget);
  });
}
