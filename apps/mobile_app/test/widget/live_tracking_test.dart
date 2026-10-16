import 'package:alakh_service/core/network/api_client.dart';
import 'package:alakh_service/core/network/token_store.dart';
import 'package:alakh_service/features/booking/data/models/booking_model.dart';
import 'package:alakh_service/features/booking/domain/entities/booking.dart';
import 'package:alakh_service/features/directions/data/shop_location_api.dart';
import 'package:alakh_service/features/jobs/data/location_reporter.dart';
import 'package:alakh_service/features/profile/data/address_api.dart';
import 'package:alakh_service/features/tracking/data/tracking_api.dart';
import 'package:alakh_service/features/tracking/data/tracking_destination.dart';
import 'package:alakh_service/features/tracking/domain/travel_estimate.dart';
import 'package:alakh_service/features/tracking/presentation/pages/live_tracking_page.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../support/fake_adapter.dart';

class FixedLocation implements LocationSource {
  final Fix? fix;
  int asked = 0;

  FixedLocation(this.fix);

  @override
  Future<Fix?> current() async {
    asked++;
    return fix;
  }
}

Booking booking({String status = BookingStatus.enRoute, String mode = 'AT_HOME', String? addressId = 'addr-1'}) =>
    Booking(
      id: 'b1',
      userId: 'c1',
      serviceId: 's1',
      serviceName: 'Laptop screen repair',
      providerId: 'p1',
      shopId: 'sh1',
      status: status,
      scheduledAt: DateTime(2026, 10, 20, 10),
      address: '',
      totalAmount: 4599,
      createdAt: DateTime(2026, 10, 16),
      serviceMode: mode,
      addressId: addressId,
    );

// MG Road, Pune and Koregaon Park: about 3.4 km apart in a straight line.
const mgRoad = (18.5204, 73.8567);
const koregaonPark = (18.5362, 73.8940);

TrackingDestinations destinations({List<Map<String, dynamic>> addresses = const [], FixedLocation? device}) {
  ApiClient client(Object? body) =>
      ApiClient(dio: fakeDio(FakeAdapter((_) => (status: 200, body: body))), tokens: MemoryTokenStore());
  return TrackingDestinations(
    shops: ShopLocationApi(client({'id': 'sh1', 'name': 'Demo Salon', 'address': '12 MG Road', 'city': 'Pune', 'latitude': mgRoad.$1, 'longitude': mgRoad.$2})),
    addresses: AddressApi(client(addresses)),
    device: device ?? FixedLocation(null),
  );
}

void main() {
  group('travel estimate', () {
    test('measures the straight line and allows for roads', () {
      final km = straightLineKm(mgRoad.$1, mgRoad.$2, koregaonPark.$1, koregaonPark.$2);
      expect(km, closeTo(4.3, 0.1));
      final estimate = estimateTravel(
        fromLatitude: mgRoad.$1,
        fromLongitude: mgRoad.$2,
        toLatitude: koregaonPark.$1,
        toLongitude: koregaonPark.$2,
      );
      expect(estimate.kilometres, closeTo(km * roadFactor, 1e-9));
      // At the city average of 22 km/h.
      expect(estimate.minutes, 16);
      expect(estimate.label, 'About 16 min away · 5.6 km');
    });

    test("uses the provider's own speed when they are moving at a road speed", () {
      double minutesAt(double? mps) => estimateTravel(
            fromLatitude: mgRoad.$1,
            fromLongitude: mgRoad.$2,
            toLatitude: koregaonPark.$1,
            toLongitude: koregaonPark.$2,
            speedMps: mps,
          ).minutes.toDouble();
      expect(minutesAt(11.1), 9); // 40 km/h
      expect(minutesAt(0.5), 16); // stopped at a signal: the city average
      expect(minutesAt(50), 6); // GPS glitch: capped at 60 km/h
    });

    test('says arriving when close, and short distances in metres', () {
      const near = TravelEstimate(kilometres: 0.15, minutes: 1);
      expect((near.arriving, near.label), (true, 'Arriving now'));
      const close = TravelEstimate(kilometres: 0.62, minutes: 2);
      expect(close.label, 'About 2 min away · 600 m');
    });
  });

  group('where the provider is heading', () {
    test('a home visit goes to the saved address when it has a map position', () async {
      final device = FixedLocation(const Fix(1, 2));
      final target = await destinations(
        addresses: [
          {'id': 'addr-0', 'label': 'Office', 'street': 'x', 'city': 'Pune', 'latitude': 1.0, 'longitude': 1.0},
          {'id': 'addr-1', 'label': 'Home', 'street': 'y', 'city': 'Pune', 'latitude': koregaonPark.$1, 'longitude': koregaonPark.$2},
        ],
        device: device,
      ).forBooking(booking());
      expect((target!.label, target.latitude, target.longitude), ('Home', koregaonPark.$1, koregaonPark.$2));
      expect(device.asked, 0);
    });

    test("without one it uses the customer's phone, who is usually waiting there", () async {
      final device = FixedLocation(Fix(koregaonPark.$1, koregaonPark.$2));
      final target = await destinations(
        addresses: [
          {'id': 'addr-1', 'label': 'Home', 'street': 'y', 'city': 'Pune'},
        ],
        device: device,
      ).forBooking(booking());
      expect(target!.label, 'You');
      expect(await destinations(device: FixedLocation(null)).forBooking(booking()), isNull);
    });

    test('a picked-up item goes to the shop, and comes back to the customer', () async {
      final toShop = await destinations().forBooking(booking(status: BookingStatus.pickedUp, mode: 'PICKUP_DROP'));
      expect((toShop!.label, toShop.latitude), ('Demo Salon', mgRoad.$1));

      final back = await destinations(device: FixedLocation(const Fix(1, 2)))
          .forBooking(booking(status: BookingStatus.outForDelivery, mode: 'PICKUP_DROP'));
      expect(back!.label, 'You');
    });

    test('nobody is travelling while the work is under way or for a shop visit', () async {
      final device = FixedLocation(const Fix(1, 2));
      final d = destinations(device: device);
      expect(await d.forBooking(booking(status: BookingStatus.inProgress)), isNull);
      expect(await d.forBooking(booking(mode: 'AT_SHOP', addressId: null)), isNull);
      expect(device.asked, 0);
    });
  });

  group('tracking card', () {
    Future<void> pump(WidgetTester tester, Booking b, {ProviderLocation? at, TrackingTarget? to}) => tester.pumpWidget(
          MaterialApp(
            home: Scaffold(
              body: TrackingStatusCard(booking: b, location: at, target: to, loading: false, error: null),
            ),
          ),
        );

    final atMgRoad = ProviderLocation(latitude: mgRoad.$1, longitude: mgRoad.$2, recordedAt: DateTime.now());
    final home = TrackingTarget('Home', koregaonPark.$1, koregaonPark.$2);

    testWidgets('shows how far away the provider is', (tester) async {
      await pump(tester, booking(), at: atMgRoad, to: home);
      expect(find.text('About 16 min away · 5.6 km'), findsOneWidget);
      expect(find.text('On the way · updated just now'), findsOneWidget);
    });

    testWidgets('follows a pickup through its steps', (tester) async {
      await pump(tester, booking(status: BookingStatus.pickedUp, mode: 'PICKUP_DROP'),
          at: atMgRoad, to: TrackingTarget('Demo Salon', koregaonPark.$1, koregaonPark.$2));
      expect(find.text('About 16 min away · 5.6 km from Demo Salon'), findsOneWidget);
      expect(find.text('Taking your item to the shop · updated just now'), findsOneWidget);

      await pump(tester, booking(status: BookingStatus.outForDelivery, mode: 'PICKUP_DROP'),
          at: ProviderLocation(latitude: koregaonPark.$1, longitude: koregaonPark.$2, recordedAt: DateTime.now()), to: home);
      expect(find.text('Arriving now'), findsOneWidget);
      expect(find.text('Bringing your item back · updated just now'), findsOneWidget);
    });

    testWidgets('has no estimate until both ends are known', (tester) async {
      await pump(tester, booking(status: BookingStatus.inProgress, mode: 'PICKUP_DROP'), at: atMgRoad);
      expect(find.textContaining('min away'), findsNothing);
      expect(find.text('Your item is being worked on · updated just now'), findsOneWidget);
    });
  });

  test('bookings carry their address and the promised return time', () {
    final json = {
      'id': 'b1',
      'customer_id': 'c1',
      'service_id': 's1',
      'status': 'IN_PROGRESS',
      'scheduled_at': '2026-10-20T04:30:00Z',
      'created_at': '2026-10-16T00:00:00Z',
      'service_mode': 'PICKUP_DROP',
      'address_id': 'addr-1',
      'ready_by': '2026-10-22T11:30:00Z',
    };
    final b = BookingModel.fromJson(json);
    expect(b.addressId, 'addr-1');
    expect(b.readyBy, DateTime.utc(2026, 10, 22, 11, 30).toLocal());
    expect(b.showsReadyBy, isTrue);
    expect(BookingModel.fromJson({...json, 'status': 'COMPLETED'}).showsReadyBy, isFalse);
    expect(BookingModel.fromJson({...json, 'ready_by': null}).showsReadyBy, isFalse);
  });

  test('provider locations carry their speed', () {
    final at = ProviderLocation.fromJson({'latitude': 1, 'longitude': 2, 'timestamp': '2026-10-16T10:00:00Z', 'speed': 8.5});
    expect(at.speed, 8.5);
  });
}
