import 'package:alakh_service/app/shell_navigation.dart';
import 'package:alakh_service/core/network/api_client.dart';
import 'package:alakh_service/features/booking/data/availability_api.dart';
import 'package:alakh_service/features/booking/data/coupon_api.dart';
import 'package:alakh_service/core/network/network_info.dart';
import 'package:alakh_service/core/network/token_store.dart';
import 'package:alakh_service/features/booking/data/datasources/booking_remote_datasource.dart';
import 'package:alakh_service/features/booking/data/repositories/booking_repository_impl.dart';
import 'package:alakh_service/features/booking/domain/usecases/cancel_booking_usecase.dart';
import 'package:alakh_service/features/booking/domain/usecases/create_booking_usecase.dart';
import 'package:alakh_service/features/booking/presentation/bloc/booking_bloc.dart';
import 'package:alakh_service/features/booking/presentation/pages/booking_page.dart';
import 'package:alakh_service/features/profile/data/address_api.dart';
import 'package:alakh_service/features/services/domain/entities/service_entity.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_test/flutter_test.dart';

import '../support/fake_adapter.dart';

class Online implements NetworkInfo {
  @override
  Future<bool> get isConnected async => true;
}

/// A day of a shop that hasn't published opening hours.
Map<String, Object?> noHours(String date) => {'hours_configured': false, 'status': 'NOT_CONFIGURED', 'slots': <Object>[]};

/// A day of a shop with hours: its free times ("HH:MM" India time to UTC start), or why there are none.
Map<String, Object?> withHours({String status = 'AVAILABLE', Map<String, String> slots = const {}, String? note}) => {
      'hours_configured': true,
      'status': status,
      'holiday_note': note,
      'slots': [for (final MapEntry(:key, :value) in slots.entries) {'start': value, 'time': key, 'remaining': 1}],
    };

/// user_service has one saved address; booking_service lists [availability] for each date (YYYY-MM-DD)
/// and accepts the booking (after [failFirst] tries that fail, as when the network drops).
FakeAdapter server({int failFirst = 0, Map<String, Object?> Function(String date) availability = noHours}) {
  var bookingTries = 0;
  return FakeAdapter((r) => r.path.endsWith('/availability')
    ? (status: 200, body: availability(r.queryParameters['date'] as String))
    : r.path.endsWith('/addresses')
    ? (status: 200, body: [
        {'id': 'addr-1', 'label': 'Home', 'street': '12 MG Road', 'city': 'Pune', 'state': 'MH', 'postal_code': '411001', 'is_default': true},
      ])
    : ++bookingTries <= failFirst
    ? (status: 503, body: {'detail': 'Booking service unavailable'})
    : (status: 201, body: {
        'id': 'b1',
        'booking_number': 'BK1',
        'customer_id': 'u1',
        'service_id': 's1',
        'status': 'PENDING',
        'scheduled_at': '2026-11-01T05:00:00Z',
        'duration_minutes': 120,
        'total_amount': 459900,
        'service_mode': 'PICKUP_DROP',
        'created_at': '2026-10-16T00:00:00Z',
      }));
}

/// The Idempotency-Key header of each booking request sent so far.
List<Object?> keysSent(FakeAdapter adapter) =>
    adapter.requests.where((r) => r.method == 'POST').map((r) => r.headers['Idempotency-Key']).toList();

/// 2 PM on a Sunday: today's slots from 2:30 PM, tomorrow is Monday 19 Oct.
DateTime now() => DateTime(2026, 10, 18, 14);

Widget page(
  FakeAdapter adapter, {
  List<String> modes = const [ServiceMode.atShop, ServiceMode.pickupDrop],
  CouponApi? coupons,
  DateTime Function() clock = now,
}) {
  final client = ApiClient(dio: fakeDio(adapter), tokens: MemoryTokenStore());
  final repo = BookingRepositoryImpl(remoteDataSource: BookingRemoteDataSourceImpl(apiClient: client), networkInfo: Online());
  return MaterialApp(
    home: BlocProvider(
      create: (_) => BookingBloc(
        createBookingUseCase: CreateBookingUseCase(repo),
        cancelBookingUseCase: CancelBookingUseCase(repo),
        bookingRepository: repo,
      ),
      child: BookingPage(
        serviceId: 's1',
        serviceName: 'Laptop screen repair',
        servicePrice: 4500,
        addressApi: AddressApi(client),
        availabilityApi: AvailabilityApi(client),
        serviceModes: modes,
        pickupFee: 99,
        couponApi: coupons,
        clock: clock,
      ),
    ),
  );
}

Future<void> pickDateAndTime(WidgetTester tester) async {
  await tester.ensureVisible(find.text('Tomorrow'));
  await tester.pumpAndSettle();
  await tester.tap(find.text('Tomorrow'));
  await tester.pumpAndSettle();
  await tester.ensureVisible(find.text('11:00 AM'));
  await tester.pumpAndSettle();
  await tester.tap(find.text('11:00 AM'));
  await tester.pumpAndSettle();
}

Future<void> confirm(WidgetTester tester) async {
  await tester.ensureVisible(find.text('Confirm Booking'));
  await tester.pumpAndSettle();
  await tester.tap(find.text('Confirm Booking'));
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('pickup & drop asks where to collect from and what, and sends it with the fee shown', (tester) async {
    tester.view.physicalSize = const Size(1080, 2400);
    addTearDown(tester.view.reset);
    final adapter = server();
    await tester.pumpWidget(page(adapter));
    await tester.pumpAndSettle();

    // At the shop by default: no address or item needed.
    expect(find.text('Visit the shop'), findsOneWidget);
    expect(find.text('What should we collect?'), findsNothing);
    expect(find.text('Saved address'), findsNothing);
    expect(find.text('₹4,500'), findsNWidgets(3)); // service line, total, and the bar at the bottom

    await tester.tap(find.text('Pickup & drop (+₹99)'));
    await tester.pumpAndSettle();
    expect(find.text('Pickup & drop fee'), findsOneWidget);
    expect(find.text('₹4,599'), findsNWidgets(2)); // the pickup fee is part of the price
    expect(find.text('Collect from'), findsOneWidget);
    expect(find.textContaining('Home: 12 MG Road'), findsOneWidget); // the default address is chosen

    await pickDateAndTime(tester);
    await confirm(tester);
    expect(adapter.requests.where((r) => r.method == 'POST'), isEmpty); // the item is required

    await tester.enterText(
      find.ancestor(of: find.textContaining('Honda Activa'), matching: find.byType(TextFormField)),
      'Dell XPS 13, cracked screen',
    );
    await confirm(tester);

    final request = adapter.requests.singleWhere((r) => r.method == 'POST');
    final sent = request.data as Map;
    expect(DateTime.parse(sent['scheduled_at'] as String).toLocal(), DateTime(2026, 10, 19, 11));
    expect(request.headers['Idempotency-Key'], matches(RegExp(r'^[0-9a-f]{32}$')));
    expect(sent['service_mode'], 'PICKUP_DROP');
    expect(sent['address_id'], 'addr-1');
    expect(sent['item_description'], 'Dell XPS 13, cracked screen');
    expect(sent['notes'], contains('Address: 12 MG Road'));
  });

  testWidgets('a shop-only service shows no choice and sends no address', (tester) async {
    tester.view.physicalSize = const Size(1080, 2400);
    addTearDown(tester.view.reset);
    final adapter = server();
    await tester.pumpWidget(page(adapter, modes: const [ServiceMode.atShop]));
    await tester.pumpAndSettle();
    expect(find.text('How would you like it?'), findsNothing);

    await pickDateAndTime(tester);
    await confirm(tester);
    final sent = adapter.requests.singleWhere((r) => r.method == 'POST').data as Map;
    expect(sent['service_mode'], 'AT_SHOP');
    expect(sent.containsKey('address_id'), isFalse);
    expect(sent['notes'], isNot(contains('Address:')));
  });

  testWidgets('a retry after an error sends the same Idempotency-Key; a changed booking gets a new one', (tester) async {
    tester.view.physicalSize = const Size(1080, 2400);
    addTearDown(tester.view.reset);
    final adapter = server(failFirst: 2);
    await tester.pumpWidget(page(adapter, modes: const [ServiceMode.atShop]));
    await tester.pumpAndSettle();
    await pickDateAndTime(tester);

    await confirm(tester);
    expect(find.text('Booking service unavailable'), findsOneWidget);
    await confirm(tester); // the customer taps again: the same attempt
    final keys = keysSent(adapter);
    expect(keys, hasLength(2));
    expect(keys[0], matches(RegExp(r'^[0-9a-f]{32}$')));
    expect(keys[1], keys[0]);
    final bodies = adapter.requests.where((r) => r.method == 'POST').map((r) => r.data).toList();
    expect(bodies[1], bodies[0]);

    // Something changed, so it is a different booking request and must not reuse the key.
    await tester.enterText(
      find.ancestor(of: find.text('Any special instructions...'), matching: find.byType(TextFormField)),
      'Please call on arrival',
    );
    await confirm(tester);
    final third = keysSent(adapter)[2];
    expect(third, matches(RegExp(r'^[0-9a-f]{32}$')));
    expect(third, isNot(keys[0]));
  });

  testWidgets('each new booking starts with its own Idempotency-Key', (tester) async {
    tester.view.physicalSize = const Size(1080, 2400);
    addTearDown(tester.view.reset);
    final first = server();
    await tester.pumpWidget(page(first, modes: const [ServiceMode.atShop]));
    await tester.pumpAndSettle();
    await pickDateAndTime(tester);
    await confirm(tester);

    // Booked: the page closes. Booking again opens a new page.
    await tester.pumpWidget(const SizedBox());
    final second = server();
    await tester.pumpWidget(page(second, modes: const [ServiceMode.atShop]));
    await tester.pumpAndSettle();
    await pickDateAndTime(tester);
    await confirm(tester);

    expect(keysSent(first), hasLength(1));
    expect(keysSent(second), hasLength(1));
    expect(keysSent(second).single, isNot(keysSent(first).single));
  });

  testWidgets('only times still ahead are offered: today starts half an hour from now', (tester) async {
    tester.view.physicalSize = const Size(1080, 2400);
    addTearDown(tester.view.reset);
    await tester.pumpWidget(page(server(), modes: const [ServiceMode.atShop]));
    await tester.pumpAndSettle();

    expect(find.text('Today'), findsOneWidget); // selected first
    expect(find.text('2:00 PM'), findsNothing);
    expect(find.text('2:30 PM'), findsOneWidget);
    expect(find.text('9:00 AM'), findsNothing);
    expect(find.text('Morning'), findsNothing); // grouped by part of the day; this morning is over
    expect(find.text('Afternoon'), findsOneWidget);

    await tester.tap(find.text('Tomorrow'));
    await tester.pumpAndSettle();
    expect(find.text('Morning'), findsOneWidget);
    expect(find.text('9:00 AM'), findsOneWidget);
    expect(find.text('8:00 PM'), findsOneWidget);
  });

  test('without opening hours: no times in the past; two weeks of days from today', () {
    final late = DateTime(2026, 10, 18, 19, 45);
    expect(BookingSlots.on(late, now: late), isEmpty);
    expect(BookingSlots.upcomingDays(now: late).first, DateTime(2026, 10, 18));
    expect(BookingSlots.upcomingDays(now: late), hasLength(14));
    expect(BookingSlots.on(DateTime(2026, 10, 18), now: DateTime(2026, 10, 18, 14, 10)).first, DateTime(2026, 10, 18, 15));
  });

  testWidgets('a shop without hours that is past its usual last time today says to pick another day', (tester) async {
    tester.view.physicalSize = const Size(1080, 2400);
    addTearDown(tester.view.reset);
    await tester.pumpWidget(page(server(), modes: const [ServiceMode.atShop], clock: () => DateTime(2026, 10, 18, 19, 45)));
    await tester.pumpAndSettle();
    expect(find.text('No more times today — try another day'), findsOneWidget);
    await tester.tap(find.text('Tomorrow'));
    await tester.pumpAndSettle();
    expect(find.text('9:00 AM'), findsOneWidget);
  });

  testWidgets('a shop with hours offers only its free times and books exactly the time it listed', (tester) async {
    tester.view.physicalSize = const Size(1080, 2400);
    addTearDown(tester.view.reset);
    final adapter = server(
      availability: (date) => date == '2026-10-19'
          ? withHours(slots: {'10:00': '2026-10-19T04:30:00Z', '16:00': '2026-10-19T10:30:00Z'})
          : withHours(status: 'NO_MORE_TODAY'),
    );
    await tester.pumpWidget(page(adapter, modes: const [ServiceMode.atShop]));
    await tester.pumpAndSettle();
    expect(find.text('No more times today — try another day'), findsOneWidget);
    expect(find.text('2:30 PM'), findsNothing); // no made-up 9-to-8 times for a shop with hours

    await tester.tap(find.text('Tomorrow'));
    await tester.pumpAndSettle();
    expect(find.text('10:00 AM'), findsOneWidget);
    expect(find.text('4:00 PM'), findsOneWidget);
    expect(find.text('11:00 AM'), findsNothing);
    expect(find.text('Afternoon'), findsOneWidget);
    await tester.tap(find.text('4:00 PM'));
    await tester.pumpAndSettle();
    expect(find.text('Tomorrow, 4:00 PM'), findsOneWidget); // in the summary, in the shop's time
    await confirm(tester);

    final asked = adapter.requests.where((r) => r.path.endsWith('/availability')).map((r) => r.queryParameters).toList();
    expect(asked, [
      {'service_id': 's1', 'date': '2026-10-18'},
      {'service_id': 's1', 'date': '2026-10-19'},
    ]);
    final sent = adapter.requests.singleWhere((r) => r.method == 'POST').data as Map;
    expect(sent['scheduled_at'], '2026-10-19T10:30:00.000Z');
  });

  testWidgets('closed, holiday and fully booked days say so', (tester) async {
    tester.view.physicalSize = const Size(1080, 2400);
    addTearDown(tester.view.reset);
    final adapter = server(
      availability: (date) => switch (date) {
        '2026-10-18' => withHours(status: 'CLOSED'),
        '2026-10-19' => withHours(status: 'FULLY_BOOKED'),
        _ => withHours(status: 'HOLIDAY', note: 'Diwali'),
      },
    );
    await tester.pumpWidget(page(adapter, modes: const [ServiceMode.atShop]));
    await tester.pumpAndSettle();
    expect(find.text('Closed on this day'), findsOneWidget);
    await tester.tap(find.text('Tomorrow'));
    await tester.pumpAndSettle();
    expect(find.text('Fully booked — try another day'), findsOneWidget);
    await tester.tap(find.text('20 Oct'));
    await tester.pumpAndSettle();
    expect(find.text('Closed on this day (Diwali)'), findsOneWidget);
    await tester.tap(find.text('Today'));
    await tester.pumpAndSettle();
    expect(find.text('Closed on this day'), findsOneWidget);
    expect(adapter.requests.where((r) => r.path.endsWith('/availability')), hasLength(3)); // each day fetched once
  });

  testWidgets("times that couldn't be loaded can be retried", (tester) async {
    tester.view.physicalSize = const Size(1080, 2400);
    addTearDown(tester.view.reset);
    var tries = 0;
    final adapter = FakeAdapter((r) => r.path.endsWith('/availability') && ++tries == 1
        ? (status: 503, body: {'detail': 'Shop service unavailable'})
        : r.path.endsWith('/availability')
            ? (status: 200, body: noHours(''))
            : (status: 200, body: <Object>[]));
    await tester.pumpWidget(page(adapter, modes: const [ServiceMode.atShop]));
    await tester.pumpAndSettle();
    expect(find.text("Couldn't load the times for this day"), findsOneWidget);
    expect(find.text('2:30 PM'), findsNothing);
    await tester.tap(find.text('Retry'));
    await tester.pumpAndSettle();
    expect(find.text("Couldn't load the times for this day"), findsNothing);
    expect(find.text('2:30 PM'), findsOneWidget);
  });

  testWidgets('a time taken just before booking is refused, dropped and the free times shown again', (tester) async {
    tester.view.physicalSize = const Size(1080, 2400);
    addTearDown(tester.view.reset);
    var taken = false;
    final adapter = FakeAdapter((r) {
      if (r.path.endsWith('/availability')) {
        return (status: 200, body: withHours(slots: {'10:00': '2026-10-18T04:30:00Z', if (!taken) '15:00': '2026-10-18T09:30:00Z'}));
      }
      if (r.method == 'POST') {
        taken = true;
        return (status: 409, body: {'detail': 'Sun 18 Oct, 3:00 PM is fully booked; pick another time'});
      }
      return (status: 200, body: <Object>[]);
    });
    await tester.pumpWidget(page(adapter, modes: const [ServiceMode.atShop]));
    await tester.pumpAndSettle();
    await tester.tap(find.text('3:00 PM'));
    await tester.pumpAndSettle();
    await confirm(tester);

    expect(find.text('Sun 18 Oct, 3:00 PM is fully booked; pick another time'), findsOneWidget);
    expect(find.text('3:00 PM'), findsNothing);
    expect(find.text('10:00 AM'), findsOneWidget);
    expect(find.text('Choose a day and time below'), findsOneWidget);
  });

  testWidgets('booking without a time says what is missing and sends nothing', (tester) async {
    tester.view.physicalSize = const Size(1080, 2400);
    addTearDown(tester.view.reset);
    final adapter = server();
    await tester.pumpWidget(page(adapter, modes: const [ServiceMode.atShop]));
    await tester.pumpAndSettle();

    await tester.drag(find.byType(SingleChildScrollView), const Offset(0, -3000)); // down at the coupon
    await tester.pumpAndSettle();
    expect(tester.getTopLeft(find.text('When?')).dy, lessThan(0));
    await confirm(tester);
    expect(find.text('Pick a time for your booking'), findsOneWidget);
    final y = tester.getTopLeft(find.text('When?')).dy;
    expect(y, inInclusiveRange(0, 400)); // scrolled back up to what needs fixing
    expect(find.text('Pick a time'), findsOneWidget);
    expect(adapter.requests.where((r) => r.method == 'POST'), isEmpty);
  });

  testWidgets('with no saved address the customer can add one right here and book', (tester) async {
    tester.view.physicalSize = const Size(1080, 2400);
    addTearDown(tester.view.reset);
    final adapter = FakeAdapter((r) => r.path.endsWith('/availability')
        ? (status: 200, body: noHours(''))
        : r.path.endsWith('/addresses') && r.method == 'GET'
        ? (status: 200, body: <Object>[])
        : r.path.endsWith('/addresses')
            ? (status: 201, body: {'id': 'addr-9', 'label': 'Home', 'street': '4 FC Road', 'city': 'Pune', 'state': 'MH', 'postal_code': '411004', 'is_default': true})
            : (status: 201, body: {
                'id': 'b1', 'booking_number': 'BK1', 'customer_id': 'u1', 'service_id': 's1', 'status': 'PENDING',
                'scheduled_at': '2026-10-19T05:30:00Z', 'total_amount': 459900, 'service_mode': 'PICKUP_DROP',
                'created_at': '2026-10-18T00:00:00Z',
              }));
    await tester.pumpWidget(page(adapter));
    await tester.pumpAndSettle();
    await pickDateAndTime(tester);
    await tester.ensureVisible(find.text('Pickup & drop (+₹99)'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Pickup & drop (+₹99)'));
    await tester.pumpAndSettle();

    expect(find.text('You have no saved address yet.'), findsOneWidget);
    await tester.ensureVisible(find.text('Add address'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Add address'));
    await tester.pumpAndSettle();
    await tester.enterText(find.widgetWithText(TextFormField, 'Flat / house no., street, area'), '4 FC Road');
    await tester.enterText(find.widgetWithText(TextFormField, 'City'), 'Pune');
    await tester.enterText(find.widgetWithText(TextFormField, 'State'), 'MH');
    await tester.enterText(find.widgetWithText(TextFormField, 'PIN code'), '411004');
    await tester.tap(find.text('Save'));
    await tester.pumpAndSettle();

    expect(find.textContaining('Home: 4 FC Road'), findsOneWidget);
    await tester.enterText(
      find.ancestor(of: find.textContaining('Honda Activa'), matching: find.byType(TextFormField)),
      'Phone, broken charging port',
    );
    await confirm(tester);
    final sent = adapter.requests.singleWhere((r) => r.method == 'POST' && r.path.endsWith('/bookings')).data as Map;
    expect(sent['address_id'], 'addr-9');
  });

  testWidgets('a booked request says what happens next and can open My Bookings', (tester) async {
    tester.view.physicalSize = const Size(1080, 2400);
    addTearDown(tester.view.reset);
    ShellTab? opened;
    void listener() => opened = ShellNavigation.instance.requested;
    ShellNavigation.instance.addListener(listener);
    addTearDown(() => ShellNavigation.instance.removeListener(listener));

    await tester.pumpWidget(page(server(), modes: const [ServiceMode.atShop]));
    await tester.pumpAndSettle();
    await pickDateAndTime(tester);
    await confirm(tester);

    expect(find.text('Booking requested'), findsOneWidget);
    expect(find.textContaining('Booking #BK1'), findsOneWidget);
    expect(find.textContaining('pay once it'), findsOneWidget);
    await tester.tap(find.text('View my bookings'));
    await tester.pumpAndSettle();
    expect(opened, ShellTab.bookings);
  });

  testWidgets('a coupon shows its saving in the price details and can be removed', (tester) async {
    tester.view.physicalSize = const Size(1080, 2400);
    addTearDown(tester.view.reset);
    final adapter = server();
    final coupons = CouponApi(ApiClient(
      dio: fakeDio(FakeAdapter((_) => (status: 200, body: {'is_valid': true, 'discount_pct': 0.1, 'message': 'ok'}))),
      tokens: MemoryTokenStore(),
    ));
    await tester.pumpWidget(page(adapter, modes: const [ServiceMode.atShop], coupons: coupons));
    await tester.pumpAndSettle();

    await tester.enterText(find.ancestor(of: find.text('e.g. WELCOME10'), matching: find.byType(TextFormField)), 'welcome10');
    await tester.ensureVisible(find.text('Apply'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Apply'));
    await tester.pumpAndSettle();

    expect(find.textContaining('WELCOME10 applied'), findsOneWidget);
    expect(find.text('−₹450'), findsOneWidget);
    expect(find.text('₹4,050'), findsNWidgets(2));
    await tester.ensureVisible(find.text('Remove'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Remove'));
    await tester.pumpAndSettle();
    expect(find.text('₹4,500'), findsNWidgets(3));
  });

  test('mode labels and fees', () {
    expect(modeChoiceLabel(ServiceMode.atHome, 150), 'At my place (+₹150)');
    expect(modeChoiceLabel(ServiceMode.pickupDrop, 99.5), 'Pickup & drop (+₹99.50)');
    expect(modeChoiceLabel(ServiceMode.atShop, 0), 'Visit the shop');
    const service = ServiceEntity(
      id: 's', name: 'AC repair', description: '', category: '', basePrice: 799, priceUnit: 'visit',
      serviceModes: [ServiceMode.atHome], homeVisitFee: 99, pickupFee: 199,
    );
    expect([service.feeFor(ServiceMode.atHome), service.feeFor(ServiceMode.pickupDrop), service.feeFor(ServiceMode.atShop)], [99, 199, 0]);
  });
}
