import 'package:intl/intl.dart';

/// Date/time formatting helpers.
/// Named [AppDateUtils] to avoid collision with Flutter's [DateUtils].
abstract class AppDateUtils {
  // Common formatters
  static final DateFormat _displayDate = DateFormat('MMM dd, yyyy');
  static final DateFormat _displayDateTime = DateFormat('MMM dd, yyyy • hh:mm a');
  static final DateFormat _time = DateFormat('hh:mm a');
  static final DateFormat _isoDate = DateFormat('yyyy-MM-dd');
  static final DateFormat _dayMonth = DateFormat('EEE, MMM dd');

  /// `"Jan 01, 2024"`
  static String formatDate(DateTime date) => _displayDate.format(date);

  /// `"Jan 01, 2024 • 02:30 PM"`
  static String formatDateTime(DateTime dateTime) => _displayDateTime.format(dateTime);

  /// `"02:30 PM"`
  static String formatTime(DateTime dateTime) => _time.format(dateTime);

  /// `"2024-01-01"`
  static String toIso(DateTime date) => _isoDate.format(date);

  /// `"Mon, Jan 01"`
  static String formatDayMonth(DateTime date) => _dayMonth.format(date);

  /// Parse an ISO-8601 string to [DateTime]. Returns null on failure.
  static DateTime? tryParseIso(String? raw) {
    if (raw == null || raw.isEmpty) return null;
    return DateTime.tryParse(raw);
  }

  /// Returns a human-readable relative string, e.g. "2 hours ago".
  static String timeAgo(DateTime date) {
    final diff = DateTime.now().difference(date);
    if (diff.inSeconds < 60) return 'Just now';
    if (diff.inMinutes < 60) return '${diff.inMinutes} min ago';
    if (diff.inHours < 24) return '${diff.inHours} hr ago';
    if (diff.inDays < 7) return '${diff.inDays} day${diff.inDays > 1 ? 's' : ''} ago';
    return formatDate(date);
  }

  /// Check if a [DateTime] is today.
  static bool isToday(DateTime date) {
    final now = DateTime.now();
    return date.year == now.year && date.month == now.month && date.day == now.day;
  }
}
