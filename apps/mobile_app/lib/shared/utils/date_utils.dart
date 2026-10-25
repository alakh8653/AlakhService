import 'package:intl/intl.dart';

/// Utility methods for formatting dates and times.
class AppDateUtils {
  AppDateUtils._();

  static final DateFormat _displayDate = DateFormat('dd MMM yyyy');
  static final DateFormat _displayDateTime = DateFormat('dd MMM yyyy, hh:mm a');
  static final DateFormat _shortDate = DateFormat('dd/MM/yyyy');
  static final DateFormat _timeOnly = DateFormat('hh:mm a');
  static final DateFormat _iso = DateFormat("yyyy-MM-dd'T'HH:mm:ss");

  static String formatDate(DateTime date) => _displayDate.format(date);

  static String formatDateTime(DateTime date) => _displayDateTime.format(date);

  static String formatShortDate(DateTime date) => _shortDate.format(date);

  static String formatTime(DateTime date) => _timeOnly.format(date);

  static String toIso(DateTime date) => _iso.format(date);

  /// Returns a human-friendly relative label: "Just now", "5m ago", etc.
  static String timeAgo(DateTime date) {
    final diff = DateTime.now().difference(date);
    if (diff.inSeconds < 60) return 'Just now';
    if (diff.inMinutes < 60) return '${diff.inMinutes}m ago';
    if (diff.inHours < 24) return '${diff.inHours}h ago';
    if (diff.inDays < 7) return '${diff.inDays}d ago';
    return formatDate(date);
  }

  static bool isToday(DateTime date) {
    final now = DateTime.now();
    return date.year == now.year &&
        date.month == now.month &&
        date.day == now.day;
  }

  static bool isTomorrow(DateTime date) {
    final tomorrow = DateTime.now().add(const Duration(days: 1));
    return date.year == tomorrow.year &&
        date.month == tomorrow.month &&
        date.day == tomorrow.day;
  }

  static String smartDate(DateTime date) {
    if (isToday(date)) return 'Today, ${formatTime(date)}';
    if (isTomorrow(date)) return 'Tomorrow, ${formatTime(date)}';
    return formatDateTime(date);
  }
}
