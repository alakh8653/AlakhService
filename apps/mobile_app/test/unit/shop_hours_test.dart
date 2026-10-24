import 'package:alakh_service/core/network/api_client.dart';
import 'package:alakh_service/core/network/token_store.dart';
import 'package:alakh_service/features/booking/data/availability_api.dart';
import 'package:alakh_service/features/shops/data/shop_hours_api.dart';
import 'package:flutter_test/flutter_test.dart';

import '../support/fake_adapter.dart';

Map<String, Object> interval(String start, String end) => {'start': start, 'end': end};

/// Monday to Friday 10-2 and 4-8, Saturday 10-6, closed on Sunday; Diwali (Mon 9 Nov 2026) off.
final hours = ShopHours.fromJson({
  'configured': true,
  'weekly': [
    for (var d = 0; d < 5; d++) {'day': d, 'intervals': [interval('16:00', '20:00'), interval('10:00', '14:00')]},
    {'day': 5, 'intervals': [interval('10:00', '18:00')]},
    {'day': 6, 'intervals': <Object>[]},
  ],
  'holidays': [
    {'date': '2026-11-09', 'note': 'Diwali'},
  ],
});

/// [hhmm] India time on [day] (UTC+5:30), as the instant the phone's clock reads.
DateTime ist(DateTime day, String hhmm) {
  final [h, m] = hhmm.split(':').map(int.parse).toList();
  return DateTime.utc(day.year, day.month, day.day, h, m).subtract(const Duration(hours: 5, minutes: 30));
}

void main() {
  final monday = DateTime(2026, 10, 19), saturday = DateTime(2026, 10, 24), sunday = DateTime(2026, 10, 25);

  test('open now says when it closes', () {
    expect(openingSummary(hours, ist(monday, '10:00'))?.text, 'Open now · closes 2 PM');
    expect(openingSummary(hours, ist(monday, '19:59'))?.open, isTrue);
    expect(openingSummary(hours, ist(monday, '19:59'))?.text, 'Open now · closes 8 PM');
  });

  test('closed says when it opens next: later today, tomorrow, or on a weekday', () {
    expect(openingSummary(hours, ist(monday, '08:30'))?.text, 'Closed · opens 10 AM');
    expect(openingSummary(hours, ist(monday, '14:00'))?.text, 'Closed · opens 4 PM'); // lunch break
    expect(openingSummary(hours, ist(monday, '20:00'))?.text, 'Closed · opens tomorrow 10 AM');
    expect(openingSummary(hours, ist(saturday, '18:30'))?.text, 'Closed · opens Mon 10 AM');
    expect(openingSummary(hours, ist(sunday, '12:00'))?.open, isFalse);
  });

  test('a holiday is closed, and the day is the day in India', () {
    // Diwali Monday: closed all day, so after Sunday comes Tuesday.
    expect(openingSummary(hours, ist(DateTime(2026, 11, 8), '12:00'))?.text, 'Closed · opens Tue 10 AM');
    expect(openingSummary(hours, ist(DateTime(2026, 11, 9), '11:00'))?.text, 'Closed · opens tomorrow 10 AM');
    // 00:15 on Tuesday in India is still Monday evening in UTC.
    expect(openingSummary(hours, DateTime.utc(2026, 10, 19, 18, 45))?.text, 'Closed · opens 10 AM');
  });

  test('open till midnight and no hours at all', () {
    final lateNight = ShopHours.fromJson({
      'configured': true,
      'weekly': [for (var d = 0; d < 7; d++) {'day': d, 'intervals': [interval('18:30', '24:00')]}],
    });
    expect(openingSummary(lateNight, ist(monday, '23:00'))?.text, 'Open now · closes midnight');
    expect(openingSummary(lateNight, ist(monday, '12:00'))?.text, 'Closed · opens 6:30 PM');
    expect(openingSummary(const ShopHours(configured: false, weekly: []), DateTime.now()), isNull);
    final never = ShopHours.fromJson({'configured': true, 'weekly': <Object>[]});
    expect(openingSummary(never, DateTime.now())?.text, 'Closed');
  });

  test('availability: slots keep the instant to book and the shop-local time to show', () async {
    final adapter = FakeAdapter((r) => (status: 200, body: {
          'hours_configured': true,
          'status': 'AVAILABLE',
          'slots': [
            {'start': '2026-10-19T04:30:00Z', 'time': '10:00', 'remaining': 2},
          ],
        }));
    final api = AvailabilityApi(ApiClient(dio: fakeDio(adapter), tokens: MemoryTokenStore()));
    final day = await api.forDay('svc 1', DateTime(2026, 10, 9));
    expect(adapter.requests.single.uri.toString(), 'http://api.test/api/v1/availability?service_id=svc+1&date=2026-10-09');
    expect(day.hoursConfigured, isTrue);
    expect(day.slots.single.at, DateTime.utc(2026, 10, 19, 4, 30));
    expect((day.slots.single.hour, day.slots.single.minute), (10, 0));
  });

  test('shop hours are fetched with the id kept to one path segment', () async {
    final adapter = FakeAdapter((r) => (status: 200, body: {'configured': false, 'weekly': <Object>[]}));
    final api = ShopHoursApi(ApiClient(dio: fakeDio(adapter), tokens: MemoryTokenStore()));
    expect((await api.forShop('a/b')).configured, isFalse);
    expect(adapter.requests.single.uri.path, '/api/v1/shops/a%2Fb/hours');
  });
}
