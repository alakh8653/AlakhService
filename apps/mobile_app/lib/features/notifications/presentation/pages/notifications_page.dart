import 'package:flutter/material.dart';

import '../../../../app/shell_navigation.dart';
import '../../../../core/di/injection_container.dart';
import '../../../../shared/utils/format.dart';
import '../../../../core/network/api_errors.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_text_styles.dart';
import '../../data/notifications_api.dart';

class NotificationsPage extends StatefulWidget {
  final NotificationsApi? notificationsApi;

  const NotificationsPage({super.key, this.notificationsApi});

  @override
  State<NotificationsPage> createState() => _NotificationsPageState();
}

class _NotificationsPageState extends State<NotificationsPage> {
  late final NotificationsApi _api = widget.notificationsApi ?? sl<NotificationsApi>();
  List<AppNotification>? _items;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final items = await _api.list();
      if (mounted) {
        setState(() {
          _items = items;
          _error = null;
        });
      }
    } catch (e) {
      if (mounted) setState(() => _error = apiErrorMessage(e));
    }
  }

  void _showError(Object e) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(apiErrorMessage(e)), backgroundColor: AppColors.error),
    );
  }

  /// Booking and payment news opens My Bookings, where the customer can act on it.
  static bool _aboutBookings(AppNotification n) {
    final text = '${n.title} ${n.body}'.toLowerCase();
    return text.contains('booking') || text.contains('payment') || text.contains('refund') || text.contains('provider');
  }

  Future<void> _open(AppNotification n) async {
    await _markRead(n);
    if (mounted && _aboutBookings(n)) ShellNavigation.show(context, ShellTab.bookings);
  }

  Future<void> _markRead(AppNotification n) async {
    if (n.isRead) return;
    try {
      await _api.markRead(n.id);
      if (!mounted) return;
      setState(() => _items = [for (final i in _items!) i.id == n.id ? i.read() : i]);
    } catch (e) {
      if (mounted) _showError(e);
    }
  }

  Future<void> _markAllRead() async {
    try {
      await _api.markAllRead();
      if (!mounted) return;
      setState(() => _items = [for (final i in _items ?? <AppNotification>[]) i.read()]);
    } catch (e) {
      if (mounted) _showError(e);
    }
  }

  IconData _iconFor(AppNotification n) {
    final text = n.title.toLowerCase();
    if (text.contains('payment') || text.contains('refund')) return Icons.payment;
    if (text.contains('booking')) return Icons.calendar_today;
    if (text.contains('queue')) return Icons.people_outline;
    return Icons.notifications;
  }

  @override
  Widget build(BuildContext context) {
    final items = _items;
    final hasUnread = items?.any((n) => !n.isRead) ?? false;
    return Scaffold(
      appBar: AppBar(
        title: const Text('Notifications'),
        actions: [
          if (hasUnread)
            TextButton(onPressed: _markAllRead, child: const Text('Mark all read')),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _load,
        child: Builder(
          builder: (context) {
            if (items == null && _error == null) {
              return const Center(child: CircularProgressIndicator());
            }
            if (items == null || items.isEmpty) {
              return ListView(
                children: [
                  const SizedBox(height: 120),
                  const Icon(Icons.notifications_off_outlined, size: 64, color: AppColors.textDisabled),
                  const SizedBox(height: 16),
                  Text(
                    _error ?? 'No notifications yet',
                    textAlign: TextAlign.center,
                    style: AppTextStyles.subtitle1,
                  ),
                  const SizedBox(height: 4),
                  Text(
                    _error == null
                        ? 'Booking updates, payment receipts and queue alerts will show up here.'
                        : 'Check your connection and try again.',
                    textAlign: TextAlign.center,
                    style: AppTextStyles.body2,
                  ),
                  if (_error != null)
                    Center(child: TextButton(onPressed: _load, child: const Text('Try again'))),
                ],
              );
            }
            return ListView.separated(
              itemCount: items.length,
              separatorBuilder: (_, __) => const Divider(height: 1, indent: 72),
              itemBuilder: (context, index) {
                final n = items[index];
                return _NotificationTile(item: n, icon: _iconFor(n), onTap: () => _open(n));
              },
            );
          },
        ),
      ),
    );
  }
}

class _NotificationTile extends StatelessWidget {
  final AppNotification item;
  final IconData icon;
  final VoidCallback onTap;

  const _NotificationTile({required this.item, required this.icon, required this.onTap});

  String _formatTime(DateTime time) {
    final diff = DateTime.now().difference(time);
    if (diff.inMinutes < 1) return 'now';
    if (diff.inMinutes < 60) return '${diff.inMinutes}m ago';
    if (diff.inHours < 24) return '${diff.inHours}h ago';
    if (diff.inDays < 7) return '${diff.inDays}d ago';
    return friendlyDay(time);
  }

  @override
  Widget build(BuildContext context) {
    return ListTile(
      onTap: onTap,
      tileColor: item.isRead ? null : AppColors.primaryLight.withValues(alpha: 0.3),
      leading: Container(
        width: 44,
        height: 44,
        decoration: BoxDecoration(
          color: AppColors.primary.withValues(alpha: 0.15),
          shape: BoxShape.circle,
        ),
        child: Icon(icon, color: AppColors.primary, size: 22),
      ),
      title: Text(
        item.title,
        style: AppTextStyles.subtitle2.copyWith(
          fontWeight: item.isRead ? FontWeight.normal : FontWeight.w600,
        ),
      ),
      subtitle: Text(item.body, style: AppTextStyles.caption, maxLines: 3, overflow: TextOverflow.ellipsis),
      trailing: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Text(_formatTime(item.createdAt), style: AppTextStyles.caption),
          if (!item.isRead) ...[
            const SizedBox(height: 4),
            Container(
              width: 8,
              height: 8,
              decoration: const BoxDecoration(shape: BoxShape.circle, color: AppColors.primary),
            ),
          ],
        ],
      ),
    );
  }
}
