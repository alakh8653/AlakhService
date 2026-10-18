import 'package:alakh_service/shared/utils/format.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('rupees use Indian grouping and drop zero paise', () {
    expect(rupees(4500), '₹4,500');
    expect(rupees(120000), '₹1,20,000');
    expect(rupees(12345678), '₹1,23,45,678');
    expect(rupees(1499.5), '₹1,499.50');
    expect(rupees(0), '₹0');
  });

  test('Indian phone numbers are grouped for reading', () {
    expect(displayPhone('+919876543210'), '+91 98765 43210');
    expect(displayPhone('+14155550100'), '+14155550100');
    expect(displayPhone(''), '');
  });

  test('days read as Today / Tomorrow / a short date, times on the 12-hour clock', () {
    final now = DateTime(2026, 10, 18, 14);
    expect(friendlyDateTime(DateTime(2026, 10, 18, 15, 30), now: now), 'Today, 3:30 PM');
    expect(friendlyDateTime(DateTime(2026, 10, 19, 9), now: now), 'Tomorrow, 9:00 AM');
    expect(friendlyDay(DateTime(2026, 10, 17), now: now), 'Yesterday');
    expect(friendlyDateTime(DateTime(2026, 10, 20, 0, 5), now: now), 'Tue, 20 Oct, 12:05 AM');
    expect(friendlyDay(DateTime(2027, 1, 2), now: now), '2 Jan 2027');
  });
}
