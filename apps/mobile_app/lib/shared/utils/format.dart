import 'package:intl/intl.dart';

/// How the app writes money and times for Indian customers.

final NumberFormat _rupeesWhole = NumberFormat.currency(locale: 'en_IN', symbol: '₹', decimalDigits: 0);
final NumberFormat _rupeesPaise = NumberFormat.currency(locale: 'en_IN', symbol: '₹', decimalDigits: 2);

/// "₹1,20,000", or "₹1,499.50" when there are paise. Indian digit grouping (lakhs, crores).
String rupees(num amount) => (amount % 1 == 0 ? _rupeesWhole : _rupeesPaise).format(amount);

final DateFormat _time = DateFormat('h:mm a');
final DateFormat _dayThisYear = DateFormat('EEE, d MMM');
final DateFormat _dayOtherYear = DateFormat('d MMM yyyy');

/// "3:30 PM": the 12-hour clock Indian customers expect.
String clockTime(DateTime time) => _time.format(time);

/// "Today", "Tomorrow", "Yesterday", "Mon, 20 Oct" or, outside this year, "20 Oct 2027".
String friendlyDay(DateTime day, {DateTime? now}) {
  final today = _dateOnly(now ?? DateTime.now());
  final difference = (_dateOnly(day).difference(today).inHours / 24).round(); // DST-safe
  if (difference == 0) return 'Today';
  if (difference == 1) return 'Tomorrow';
  if (difference == -1) return 'Yesterday';
  return day.year == today.year ? _dayThisYear.format(day) : _dayOtherYear.format(day);
}

/// "Today, 3:30 PM" or "Mon, 20 Oct, 11:00 AM".
String friendlyDateTime(DateTime time, {DateTime? now}) => '${friendlyDay(time, now: now)}, ${clockTime(time)}';

DateTime _dateOnly(DateTime d) => DateTime(d.year, d.month, d.day);
