import 'package:alakh_service/core/network/api_client.dart';
import 'package:alakh_service/core/network/token_store.dart';
import 'package:alakh_service/features/booking/data/availability_api.dart';
import 'package:alakh_service/features/booking/data/datasources/booking_remote_datasource.dart';
import 'package:alakh_service/features/booking/data/repositories/booking_repository_impl.dart';
import 'package:alakh_service/features/booking/domain/usecases/cancel_booking_usecase.dart';
import 'package:alakh_service/features/booking/domain/usecases/create_booking_usecase.dart';
import 'package:alakh_service/features/booking/presentation/bloc/booking_bloc.dart';
import 'package:alakh_service/features/booking/presentation/pages/booking_page.dart';
import 'package:alakh_service/features/packages/data/packages_api.dart';
import 'package:alakh_service/features/packages/presentation/packages_widgets.dart';
import 'package:alakh_service/features/payment/data/payment_api.dart';
import 'package:alakh_service/features/payment/data/razorpay_checkout.dart';
import 'package:alakh_service/features/profile/data/address_api.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_test/flutter_test.dart';

import '../support/fake_adapter.dart';
import 'booking_page_test.dart' as booking_page show Online, now, pickDateAndTime, server;
import 'feature_pages_test.dart' show FakeCheckout;

const offer = {'id': 'pk1', 'service_id': 's1', 'name': '5 haircuts', 'visits': 5, 'price_cents': 120000, 'valid_days': 90};
Map<String, Object?> owned({int left = 3, bool usable = true}) => {
      'id': 'pp1',
      'package_id': 'pk1',
      'shop_id': 'shop-1',
      'service_id': 's1',
      'name': '5 haircuts',
      'visits_total': 5,
      'visits_left': left,
      'price_cents': 120000,
      'status': 'ACTIVE',
      'expires_at': '2027-01-20T10:00:00Z',
      'usable': usable,
    };

ApiClient clientFor(FakeAdapter adapter) => ApiClient(dio: fakeDio(adapter), tokens: MemoryTokenStore());

void main() {
  test('a package saves what its visits would cost one by one', () {
    final o = PackageOffer.fromJson(offer);
    expect(o.savingOn(300), 300); // 5 x ₹300 = ₹1,500 for ₹1,200
    expect(o.savingOn(200), 0);
  });

  testWidgets('a service shows its packages and one can be bought online', (tester) async {
    final adapter = FakeAdapter((r) => r.path.endsWith('/buy')
        ? (status: 201, body: {
            'purchase_id': 'pp1',
            'payment': {
              'id': 'pay1',
              'amount_cents': 120000,
              'status': 'PENDING',
              'checkout': {'key_id': 'rzp', 'order_id': 'order_p', 'amount_cents': 120000, 'currency': 'INR'},
            },
          })
        : r.path.endsWith('/verify')
        ? (status: 200, body: {'id': 'pay1', 'amount_cents': 120000, 'status': 'COMPLETED'})
        : (status: 200, body: [offer]));
    final client = clientFor(adapter);
    final checkout = FakeCheckout(const CheckoutPaid(orderId: 'order_p', paymentId: 'rzp_1', signature: 's'));
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: PackageOffers(
          serviceId: 's1',
          servicePrice: 300,
          api: PackagesApi(client),
          paymentApi: PaymentApi(client),
          checkoutLauncher: checkout,
        ),
      ),
    ));
    await tester.pumpAndSettle();

    expect(find.text('5 haircuts'), findsOneWidget);
    expect(find.text('5 visits · valid 90 days · save ₹300'), findsOneWidget);
    await tester.tap(find.text('Buy ₹1,200'));
    await tester.pumpAndSettle();
    expect(checkout.opened?.orderId, 'order_p');
    expect(adapter.requests.where((r) => r.path.endsWith('/payments/pay1/verify')), hasLength(1));
    expect(find.text('5 haircuts is ready. Choose it when you book.'), findsOneWidget);
  });

  testWidgets('a visit can be booked with the package, for nothing more', (tester) async {
    final base = booking_page.server();
    final adapter = FakeAdapter((r) => r.path.endsWith('/packages/mine') ? (status: 200, body: [owned()]) : base.handler(r));
    final client = clientFor(adapter);
    final repo = BookingRepositoryImpl(remoteDataSource: BookingRemoteDataSourceImpl(apiClient: client), networkInfo: booking_page.Online());
    await tester.pumpWidget(MaterialApp(
      home: BlocProvider(
        create: (_) => BookingBloc(
          createBookingUseCase: CreateBookingUseCase(repo),
          cancelBookingUseCase: CancelBookingUseCase(repo),
          bookingRepository: repo,
        ),
        child: BookingPage(
          serviceId: 's1',
          serviceName: 'Haircut',
          servicePrice: 300,
          addressApi: AddressApi(client),
          availabilityApi: AvailabilityApi(client),
          packagesApi: PackagesApi(client),
          clock: booking_page.now,
        ),
      ),
    ));
    await tester.pumpAndSettle();

    expect(find.text('5 haircuts · 3 visits left'), findsOneWidget);
    await tester.ensureVisible(find.text('Use my package'));
    await tester.tap(find.text('Use my package'));
    await tester.pumpAndSettle();
    expect(find.text('₹0'), findsWidgets);

    await booking_page.pickDateAndTime(tester);
    await tester.tap(find.text('Confirm Booking'));
    await tester.pumpAndSettle();
    final sent = adapter.requests.singleWhere((r) => r.method == 'POST' && r.path.endsWith('/bookings'));
    expect((sent.data as Map)['package_purchase_id'], 'pp1');
  });

  testWidgets('my packages show the visits left, and those used up', (tester) async {
    final adapter = FakeAdapter((r) => (status: 200, body: [owned(), {...owned(left: 0, usable: false), 'id': 'pp0'}]));
    await tester.pumpWidget(MaterialApp(home: MyPackagesPage(api: PackagesApi(clientFor(adapter)))));
    await tester.pumpAndSettle();
    expect(find.textContaining('3 of 5 visits left'), findsOneWidget);
    expect(find.text('Used up or expired'), findsOneWidget);
  });
}
