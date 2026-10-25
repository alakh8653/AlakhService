import 'package:alakh_service/features/directions/data/travel_options.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  const pinned = Destination(name: 'Demo Salon', address: '12 MG Road, Pune', latitude: 18.5204, longitude: 73.8567);
  const addressOnly = Destination(name: 'Demo Salon', address: '12 MG Road, Pune');

  test('Google Maps directions go to the exact point, by car, public transport or on foot', () {
    final options = {for (final o in travelOptions(pinned)) o.mode: o.uri};
    expect(options[TravelMode.drive].toString(), 'https://www.google.com/maps/dir/?api=1&destination=18.5204%2C73.8567&travelmode=driving');
    expect(options[TravelMode.transit]!.queryParameters['travelmode'], 'transit');
    expect(options[TravelMode.walk]!.queryParameters['travelmode'], 'walking');
  });

  test('without coordinates, maps search for the shop by name and address', () {
    final drive = travelOptions(addressOnly).first.uri;
    expect(drive.queryParameters['destination'], 'Demo Salon, 12 MG Road, Pune');
  });

  test('Uber opens with the shop as the drop-off, and only when its position is known', () {
    final uber = travelOptions(pinned).singleWhere((o) => o.mode == TravelMode.uber).uri;
    expect(uber.host, 'm.uber.com');
    expect(uber.queryParameters, {
      'action': 'setPickup',
      'pickup': 'my_location',
      'dropoff[latitude]': '18.5204',
      'dropoff[longitude]': '73.8567',
      'dropoff[nickname]': 'Demo Salon',
      'dropoff[formatted_address]': '12 MG Road, Pune',
    });
    expect(travelOptions(addressOnly).map((o) => o.mode), isNot(contains(TravelMode.uber)));
  });

  test('own vehicle comes first, then public transport', () {
    expect(travelOptions(pinned).map((o) => o.mode).toList(), [TravelMode.drive, TravelMode.transit, TravelMode.walk, TravelMode.uber]);
    expect(pinned.copyText, 'Demo Salon, 12 MG Road, Pune');
  });
}
