import 'package:flutter/material.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_text_styles.dart';

class NotificationsPage extends StatefulWidget {
  const NotificationsPage({super.key});

  @override
  State<NotificationsPage> createState() => _NotificationsPageState();
}

class _NotificationsPageState extends State<NotificationsPage> {
  // Simulated notifications
  final List<_NotificationItem> _notifications = [
    _NotificationItem(
      id: '1',
      title: 'Booking Confirmed',
      body: 'Your cleaning service booking has been confirmed.',
      type: 'booking',
      time: DateTime.now().subtract(const Duration(minutes: 5)),
      isRead: false,
    ),
    _NotificationItem(
      id: '2',
      title: 'Provider Assigned',
      body: 'Ramesh Kumar will be arriving at 10:00 AM.',
      type: 'tracking',
      time: DateTime.now().subtract(const Duration(hours: 1)),
      isRead: false,
    ),
    _NotificationItem(
      id: '3',
      title: 'Payment Successful',
      body: '₹499 payment received for booking #B12345.',
      type: 'payment',
      time: DateTime.now().subtract(const Duration(hours: 3)),
      isRead: true,
    ),
    _NotificationItem(
      id: '4',
      title: 'Service Completed',
      body: 'Your service has been completed. Rate your experience!',
      type: 'review',
      time: DateTime.now().subtract(const Duration(days: 1)),
      isRead: true,
    ),
  ];

  IconData _iconForType(String type) {
    return switch (type) {
      'booking' => Icons.calendar_today,
      'tracking' => Icons.location_on,
      'payment' => Icons.payment,
      'review' => Icons.star_outline,
      _ => Icons.notifications,
    };
  }

  Color _colorForType(String type) {
    return switch (type) {
      'booking' => AppColors.primary,
      'tracking' => AppColors.accent,
      'payment' => AppColors.success,
      'review' => AppColors.starFilled,
      _ => AppColors.textSecondary,
    };
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Notifications'),
        actions: [
          TextButton(
            onPressed: () => setState(() {
              for (final n in _notifications) {
                n.isRead = true;
              }
            }),
            child: const Text('Mark all read'),
          ),
        ],
      ),
      body: _notifications.isEmpty
          ? Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  const Icon(
                    Icons.notifications_off_outlined,
                    size: 64,
                    color: AppColors.textDisabled,
                  ),
                  const SizedBox(height: 16),
                  Text('No notifications', style: AppTextStyles.subtitle1),
                ],
              ),
            )
          : ListView.separated(
              itemCount: _notifications.length,
              separatorBuilder: (_, __) =>
                  const Divider(height: 1, indent: 72),
              itemBuilder: (context, index) {
                final n = _notifications[index];
                return _NotificationTile(
                  item: n,
                  icon: _iconForType(n.type),
                  iconColor: _colorForType(n.type),
                  onTap: () => setState(() => n.isRead = true),
                );
              },
            ),
    );
  }
}

class _NotificationTile extends StatelessWidget {
  final _NotificationItem item;
  final IconData icon;
  final Color iconColor;
  final VoidCallback onTap;

  const _NotificationTile({
    required this.item,
    required this.icon,
    required this.iconColor,
    required this.onTap,
  });

  String _formatTime(DateTime time) {
    final diff = DateTime.now().difference(time);
    if (diff.inMinutes < 60) return '${diff.inMinutes}m ago';
    if (diff.inHours < 24) return '${diff.inHours}h ago';
    return '${diff.inDays}d ago';
  }

  @override
  Widget build(BuildContext context) {
    return ListTile(
      onTap: onTap,
      tileColor: item.isRead ? null : AppColors.primaryLight.withOpacity(0.3),
      leading: Container(
        width: 44,
        height: 44,
        decoration: BoxDecoration(
          color: iconColor.withOpacity(0.15),
          shape: BoxShape.circle,
        ),
        child: Icon(icon, color: iconColor, size: 22),
      ),
      title: Text(
        item.title,
        style: AppTextStyles.subtitle2.copyWith(
          fontWeight: item.isRead ? FontWeight.normal : FontWeight.w600,
        ),
      ),
      subtitle: Text(item.body, style: AppTextStyles.caption, maxLines: 2),
      trailing: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Text(_formatTime(item.time), style: AppTextStyles.caption),
          if (!item.isRead) ...[
            const SizedBox(height: 4),
            Container(
              width: 8,
              height: 8,
              decoration: const BoxDecoration(
                shape: BoxShape.circle,
                color: AppColors.primary,
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class _NotificationItem {
  final String id;
  final String title;
  final String body;
  final String type;
  final DateTime time;
  bool isRead;

  _NotificationItem({
    required this.id,
    required this.title,
    required this.body,
    required this.type,
    required this.time,
    required this.isRead,
  });
}
