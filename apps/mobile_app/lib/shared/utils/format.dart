import 'package:intl/intl.dart';

import '../../l10n/l10n.dart';

/// How the app writes money and times for Indian customers.

final NumberFormat _rupeesWhole = NumberFormat.currency(locale: 'en_IN', symbol: '₹', decimalDigits: 0);
final NumberFormat _rupeesPaise = NumberFormat.currency(locale: 'en_IN', symbol: '₹', decimalDigits: 2);

/// "₹1,20,000", or "₹1,499.50" when there are paise. Indian digit grouping (lakhs, crores), in every
/// language the app speaks.
String rupees(num amount) => (amount % 1 == 0 ? _rupeesWhole : _rupeesPaise).format(amount);

final DateFormat _time = DateFormat('h:mm a');

/// "3:30 PM": the 12-hour clock Indian customers expect (also in Hindi, where it is read the same).
String clockTime(DateTime time) => _time.format(time);

/// "Today", "Tomorrow", "Yesterday", "Mon, 20 Oct" or, outside this year, "20 Oct 2027"; in the language
/// of [l10n] (English without it).
String friendlyDay(DateTime day, {DateTime? now, AppLocalizations? l10n}) {
  final strings = l10n ?? englishL10n;
  final today = _dateOnly(now ?? DateTime.now());
  final difference = (_dateOnly(day).difference(today).inHours / 24).round(); // DST-safe
  if (difference == 0) return strings.today;
  if (difference == 1) return strings.tomorrow;
  if (difference == -1) return strings.yesterday;
  return DateFormat(day.year == today.year ? 'EEE, d MMM' : 'd MMM yyyy', _locale(strings)).format(day);
}

/// "Today, 3:30 PM" or "Mon, 20 Oct, 11:00 AM".
String friendlyDateTime(DateTime time, {DateTime? now, AppLocalizations? l10n}) =>
    '${friendlyDay(time, now: now, l10n: l10n)}, ${clockTime(time)}';

/// "Mon" and "20 Oct" for a day, in the language of [l10n].
String shortWeekday(DateTime day, AppLocalizations l10n) => DateFormat.E(_locale(l10n)).format(day);
String dayAndMonth(DateTime day, AppLocalizations l10n) => DateFormat('d MMM', _locale(l10n)).format(day);

/// Hindi dates need intl's Hindi data, which the app's localization delegates load; English uses the
/// built-in data, so it also works where they are not loaded (tests).
String? _locale(AppLocalizations l10n) => l10n.localeName == 'en' ? null : l10n.localeName;

DateTime _dateOnly(DateTime d) => DateTime(d.year, d.month, d.day);

/// "+91 98765 43210" for an Indian E.164 number; anything else as given.
String displayPhone(String phone) {
  final m = RegExp(r'^\+91(\d{5})(\d{5})$').firstMatch(phone.replaceAll(' ', ''));
  return m == null ? phone : '+91 ${m[1]} ${m[2]}';
}
