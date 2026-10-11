import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../../core/di/injection_container.dart';
import '../../../../core/network/api_errors.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_text_styles.dart';
import '../../../../shared/widgets/error_widget.dart';
import '../../../../shared/widgets/loading_indicator.dart';
import '../../../payment/presentation/pages/payment_page.dart';
import '../../../tracking/presentation/pages/live_tracking_page.dart';
import '../../data/dispute_api.dart';
import '../../data/rating_api.dart';
import '../../domain/entities/booking.dart';
import '../bloc/booking_bloc.dart';
import '../bloc/booking_event.dart';
import '../bloc/booking_state.dart';

class BookingHistoryPage extends StatefulWidget {
  const BookingHistoryPage({super.key});

  @override
  State<BookingHistoryPage> createState() => _BookingHistoryPageState();
}

class _BookingHistoryPageState extends State<BookingHistoryPage> {
  @override
  void initState() {
    super.initState();
    context.read<BookingBloc>().add(const LoadUserBookings());
  }

  static Color statusColor(String status) => switch (status) {
        BookingStatus.confirmed || BookingStatus.assigned => AppColors.info,
        BookingStatus.enRoute || BookingStatus.inProgress => AppColors.primary,
        BookingStatus.completed => AppColors.success,
        BookingStatus.pending => AppColors.warning,
        BookingStatus.cancelled || BookingStatus.disputed => AppColors.error,
        _ => AppColors.textSecondary,
      };

  static String statusLabel(String status) => switch (status) {
        BookingStatus.pending => 'Awaiting confirmation',
        BookingStatus.confirmed => 'Confirmed',
        BookingStatus.assigned => 'Provider assigned',
        BookingStatus.enRoute => 'Provider on the way',
        BookingStatus.inProgress => 'In progress',
        BookingStatus.completed => 'Completed',
        BookingStatus.cancelled => 'Cancelled',
        BookingStatus.disputed => 'Disputed',
        BookingStatus.refunded => 'Refunded',
        _ => status,
      };

  Future<void> _confirmCancel(Booking booking) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Cancel booking?'),
        content: Text('${booking.serviceName} on ${_date(booking.scheduledAt)} will be cancelled.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(dialogContext, false), child: const Text('Keep it')),
          TextButton(onPressed: () => Navigator.pop(dialogContext, true), child: const Text('Cancel booking')),
        ],
      ),
    );
    if (confirmed == true && mounted) {
      context.read<BookingBloc>().add(CancelBookingRequested(booking.id));
    }
  }

  Future<void> _rate(Booking booking) async {
    final rating = await showDialog<double>(context: context, builder: (_) => const _RatingDialog());
    if (rating == null || !mounted) return;
    final messenger = ScaffoldMessenger.of(context);
    try {
      await sl<RatingApi>().rate(shopId: booking.shopId!, bookingId: booking.id, rating: rating);
      messenger.showSnackBar(const SnackBar(content: Text('Thanks for rating!'), backgroundColor: AppColors.success));
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text(apiErrorMessage(e)), backgroundColor: AppColors.error));
    }
  }

  Future<void> _report(Booking booking) async {
    final report = await showDialog<(String, String)>(context: context, builder: (_) => const _ReportDialog());
    if (report == null || !mounted) return;
    final messenger = ScaffoldMessenger.of(context);
    final bloc = context.read<BookingBloc>();
    try {
      await sl<DisputeApi>().report(bookingId: booking.id, type: report.$1, description: report.$2);
      messenger.showSnackBar(const SnackBar(content: Text('Thanks. Our support team will look into it and get back to you.')));
      bloc.add(const LoadUserBookings());
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text(apiErrorMessage(e)), backgroundColor: AppColors.error));
    }
  }

  void _open(Widget page) => Navigator.push(context, MaterialPageRoute(builder: (_) => page))
      .then((_) => mounted ? context.read<BookingBloc>().add(const LoadUserBookings()) : null);

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('My Bookings')),
      body: BlocConsumer<BookingBloc, BookingState>(
        listener: (context, state) {
          if (state is BookingCancelled) {
            ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Booking cancelled')));
          }
        },
        builder: (context, state) {
          if (state is BookingLoading || state is BookingInitial || state is BookingCancelled) {
            return const LoadingIndicator(message: 'Loading bookings...');
          }
          if (state is BookingError) {
            return AppErrorWidget(
              message: state.message,
              onRetry: () => context.read<BookingBloc>().add(const LoadUserBookings()),
            );
          }
          final bookings = state is BookingsLoaded ? state.bookings : const <Booking>[];
          if (bookings.isEmpty) {
            return const Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(Icons.calendar_today_outlined, size: 64, color: AppColors.textDisabled),
                  SizedBox(height: 16),
                  Text('No bookings yet', style: AppTextStyles.subtitle1),
                  Text('Book a service to see it here', style: AppTextStyles.body2),
                ],
              ),
            );
          }
          return RefreshIndicator(
            onRefresh: () async => context.read<BookingBloc>().add(const RefreshBookings()),
            child: ListView.separated(
              padding: const EdgeInsets.all(16),
              itemCount: bookings.length,
              separatorBuilder: (_, __) => const SizedBox(height: 12),
              itemBuilder: (context, index) {
                final b = bookings[index];
                return _BookingCard(
                  booking: b,
                  statusColor: statusColor(b.status),
                  statusLabel: statusLabel(b.status),
                  onCancel: b.canCancel ? () => _confirmCancel(b) : null,
                  onTrack: b.canTrack ? () => _open(LiveTrackingPage(booking: b)) : null,
                  onPay: b.canPay ? () => _open(PaymentPage(bookingId: b.id, amount: b.totalAmount)) : null,
                  onRate: b.canRate ? () => _rate(b) : null,
                  onReport: b.canDispute ? () => _report(b) : null,
                );
              },
            ),
          );
        },
      ),
    );
  }
}

String _date(DateTime d) {
  final hour = d.hour % 12 == 0 ? 12 : d.hour % 12;
  final minute = d.minute.toString().padLeft(2, '0');
  return '${d.day}/${d.month}/${d.year} $hour:$minute ${d.hour < 12 ? 'AM' : 'PM'}';
}

class _BookingCard extends StatelessWidget {
  final Booking booking;
  final Color statusColor;
  final String statusLabel;
  final VoidCallback? onCancel;
  final VoidCallback? onTrack;
  final VoidCallback? onPay;
  final VoidCallback? onRate;
  final VoidCallback? onReport;

  const _BookingCard({
    required this.booking,
    required this.statusColor,
    required this.statusLabel,
    this.onCancel,
    this.onTrack,
    this.onPay,
    this.onRate,
    this.onReport,
  });

  @override
  Widget build(BuildContext context) {
    final actions = <Widget>[
      if (onTrack != null)
        TextButton.icon(onPressed: onTrack, icon: const Icon(Icons.location_on_outlined, size: 18), label: const Text('Track')),
      if (onPay != null)
        TextButton.icon(onPressed: onPay, icon: const Icon(Icons.payment, size: 18), label: const Text('Pay')),
      if (onRate != null)
        TextButton.icon(onPressed: onRate, icon: const Icon(Icons.star_outline, size: 18), label: const Text('Rate')),
      if (onReport != null)
        TextButton.icon(onPressed: onReport, icon: const Icon(Icons.report_outlined, size: 18), label: const Text('Report a problem')),
      if (onCancel != null)
        TextButton(
          onPressed: onCancel,
          style: TextButton.styleFrom(foregroundColor: AppColors.error),
          child: const Text('Cancel'),
        ),
    ];
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(child: Text(booking.serviceName, style: AppTextStyles.subtitle1)),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(
                    color: statusColor.withValues(alpha: 0.15),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Text(statusLabel, style: AppTextStyles.overline.copyWith(color: statusColor)),
                ),
              ],
            ),
            if (booking.bookingNumber.isNotEmpty) ...[
              const SizedBox(height: 2),
              Text('#${booking.bookingNumber}', style: AppTextStyles.caption),
            ],
            const SizedBox(height: 8),
            Row(
              children: [
                const Icon(Icons.calendar_today, size: 14, color: AppColors.textSecondary),
                const SizedBox(width: 4),
                Text(_date(booking.scheduledAt), style: AppTextStyles.caption),
              ],
            ),
            if (booking.address.isNotEmpty) ...[
              const SizedBox(height: 4),
              Row(
                children: [
                  const Icon(Icons.location_on, size: 14, color: AppColors.textSecondary),
                  const SizedBox(width: 4),
                  Expanded(
                    child: Text(booking.address, style: AppTextStyles.caption, maxLines: 1, overflow: TextOverflow.ellipsis),
                  ),
                ],
              ),
            ],
            const SizedBox(height: 8),
            Row(
              children: [
                Text(
                  '₹${booking.totalAmount.toStringAsFixed(booking.totalAmount % 1 == 0 ? 0 : 2)}',
                  style: AppTextStyles.subtitle1.copyWith(color: AppColors.primary),
                ),
                const Spacer(),
              ],
            ),
            if (actions.isNotEmpty) Wrap(alignment: WrapAlignment.end, spacing: 4, children: actions),
          ],
        ),
      ),
    );
  }
}

class _RatingDialog extends StatefulWidget {
  const _RatingDialog();

  @override
  State<_RatingDialog> createState() => _RatingDialogState();
}

class _RatingDialogState extends State<_RatingDialog> {
  int _stars = 5;

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Rate this service'),
      content: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: List.generate(
          5,
          (i) => IconButton(
            tooltip: '${i + 1} star${i == 0 ? '' : 's'}',
            onPressed: () => setState(() => _stars = i + 1),
            icon: Icon(i < _stars ? Icons.star : Icons.star_border, color: AppColors.starFilled),
          ),
        ),
      ),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context), child: const Text('Not now')),
        TextButton(onPressed: () => Navigator.pop(context, _stars.toDouble()), child: const Text('Submit')),
      ],
    );
  }
}


/// Asks what went wrong; pops with (type, description).
class _ReportDialog extends StatefulWidget {
  const _ReportDialog();

  @override
  State<_ReportDialog> createState() => _ReportDialogState();
}

class _ReportDialogState extends State<_ReportDialog> {
  String _type = disputeTypes.keys.first;
  final _description = TextEditingController();

  @override
  void dispose() {
    _description.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final valid = _description.text.trim().length >= 3;
    return AlertDialog(
      title: const Text('Report a problem'),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          DropdownButtonFormField<String>(
            initialValue: _type,
            items: [
              for (final e in disputeTypes.entries) DropdownMenuItem(value: e.key, child: Text(e.value)),
            ],
            onChanged: (v) => setState(() => _type = v ?? _type),
            decoration: const InputDecoration(labelText: 'What went wrong?'),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _description,
            maxLines: 4,
            maxLength: 2000,
            onChanged: (_) => setState(() {}),
            decoration: const InputDecoration(labelText: 'Tell us what happened', alignLabelWithHint: true),
          ),
        ],
      ),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
        TextButton(
          onPressed: valid ? () => Navigator.pop(context, (_type, _description.text.trim())) : null,
          child: const Text('Send'),
        ),
      ],
    );
  }
}
