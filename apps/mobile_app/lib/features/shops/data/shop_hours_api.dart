import 'package:dio/dio.dart';

import '../../../core/constants/api_constants.dart';
import '../../../core/network/api_client.dart';
import '../../../core/network/api_errors.dart';
import '../../../shared/utils/format.dart';
import '../../../l10n/l10n.dart';

/// A shop's published opening hours (shop_service), in India time.
class ShopHours {
  /// False until the owner publishes hours; such a shop shows no "open now".
  final bool configured;

  /// Seven days, Monday first: each open interval as minutes after midnight (end 1440 = midnight).
  final List<List<(int, int)>> weekly;

  /// Closure dates, "YYYY-MM-DD".
  final Set<String> holidays;

  const ShopHours({required this.configured, required this.weekly, this.holidays = const {}});

  factory ShopHours.fromJson(Map<String, dynamic> json) {
    final weekly = List<List<(int, int)>>.generate(7, (_) => []);
    for (final d in (json['weekly'] as List? ?? const []).cast<Map<String, dynamic>>()) {
      weekly[d['day'] as int] = [
        for (final i in (d['intervals'] as List? ?? const []).cast<Map<String, dynamic>>())
          (_minutes(i['start'] as String), _minutes(i['end'] as String)),
      ]..sort((a, b) => a.$1.compareTo(b.$1));
    }
    return ShopHours(
      configured: json['configured'] as bool? ?? false,
      weekly: weekly,
      holidays: {for (final h in (json['holidays'] as List? ?? const []).cast<Map<String, dynamic>>()) h['date'] as String},
    );
  }

  static int _minutes(String hhmm) {
    final parts = hhmm.split(':');
    return int.parse(parts[0]) * 60 + int.parse(parts[1]);
  }
}

/// Whether the shop is open at [now] and when that changes: "Open now · closes 8 PM", "Closed · opens 4 PM",
/// "Closed · opens tomorrow 10 AM" or "Closed · opens Mon 10 AM", in the language of [l10n] (English
/// without it). Null for a shop without published hours.
({bool open, String text})? openingSummary(ShopHours hours, DateTime now, {AppLocalizations? l10n}) {
  if (!hours.configured) return null;
  final l = l10n ?? englishL10n;
  String clock(int minutes) => _clock(minutes, l);
  // The shop's wall clock: India is UTC+5:30 all year.
  final local = now.toUtc().add(const Duration(hours: 5, minutes: 30));
  final today = DateTime.utc(local.year, local.month, local.day);
  final minute = local.hour * 60 + local.minute;
  List<(int, int)> on(DateTime day) => hours.holidays.contains(_date(day)) ? const [] : hours.weekly[day.weekday - 1];

  for (final (start, end) in on(today)) {
    if (start <= minute && minute < end) return (open: true, text: l.hoursOpenCloses(clock(end)));
  }
  for (final (start, _) in on(today)) {
    if (start > minute) return (open: false, text: l.hoursClosedOpens(clock(start)));
  }
  for (var ahead = 1; ahead <= 7; ahead++) {
    final day = today.add(Duration(days: ahead));
    final intervals = on(day);
    if (intervals.isNotEmpty) {
      final at = clock(intervals.first.$1);
      return (
        open: false,
        text: ahead == 1 ? l.hoursClosedOpensTomorrow(at) : l.hoursClosedOpensDay(shortWeekday(day, l), at),
      );
    }
  }
  return (open: false, text: l.hoursClosed);
}

String _date(DateTime d) =>
    '${d.year.toString().padLeft(4, '0')}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';

/// "8 PM", "8:30 PM", "midnight".
String _clock(int minutes, AppLocalizations l10n) {
  if (minutes % (24 * 60) == 0) return l10n.midnight;
  final h = minutes ~/ 60, m = minutes % 60;
  final hour12 = h % 12 == 0 ? 12 : h % 12;
  return '$hour12${m == 0 ? '' : ':${m.toString().padLeft(2, '0')}'} ${h < 12 ? 'AM' : 'PM'}';
}

/// Opening hours of a shop, for the "Open now" line on a service.
class ShopHoursApi {
  final ApiClient apiClient;

  ShopHoursApi(this.apiClient);

  Future<ShopHours> forShop(String shopId) async {
    try {
      final response = await apiClient.get<Map<String, dynamic>>(ApiConstants.shopHours(shopId));
      return ShopHours.fromJson(response.data!);
    } on DioException catch (e) {
      throw toServerException(e);
    }
  }
}
