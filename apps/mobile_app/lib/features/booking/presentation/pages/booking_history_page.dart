import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_text_styles.dart';
import '../../../../shared/widgets/loading_indicator.dart';
import '../../../../shared/widgets/error_widget.dart';
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

  Color _statusColor(String status) {
    return switch (status.toLowerCase()) {
      'confirmed' => AppColors.success,
      'pending' => AppColors.warning,
      'cancelled' => AppColors.error,
      'completed' => AppColors.info,
      _ => AppColors.textSecondary,
    };
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('My Bookings')),
      body: BlocBuilder<BookingBloc, BookingState>(
        builder: (context, state) {
          if (state is BookingLoading) {
            return const LoadingIndicator(message: 'Loading bookings...');
          }
          if (state is BookingError) {
            return AppErrorWidget(
              message: state.message,
              onRetry: () =>
                  context.read<BookingBloc>().add(const LoadUserBookings()),
            );
          }
          if (state is BookingsLoaded) {
            if (state.bookings.isEmpty) {
              return Center(
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    const Icon(
                      Icons.calendar_today_outlined,
                      size: 64,
                      color: AppColors.textDisabled,
                    ),
                    const SizedBox(height: 16),
                    Text('No bookings yet', style: AppTextStyles.subtitle1),
                    Text(
                      'Book a service to see it here',
                      style: AppTextStyles.body2,
                    ),
                  ],
                ),
              );
            }
            return RefreshIndicator(
              onRefresh: () async =>
                  context.read<BookingBloc>().add(const RefreshBookings()),
              child: ListView.separated(
                padding: const EdgeInsets.all(16),
                itemCount: state.bookings.length,
                separatorBuilder: (_, __) => const SizedBox(height: 12),
                itemBuilder: (context, index) {
                  final b = state.bookings[index];
                  return _BookingCard(
                    booking: b,
                    statusColor: _statusColor(b.status),
                    onCancel: b.status == 'pending'
                        ? () => context
                            .read<BookingBloc>()
                            .add(CancelBookingRequested(b.id))
                        : null,
                  );
                },
              ),
            );
          }
          return const SizedBox.shrink();
        },
      ),
    );
  }
}

class _BookingCard extends StatelessWidget {
  final Booking booking;
  final Color statusColor;
  final VoidCallback? onCancel;

  const _BookingCard({
    required this.booking,
    required this.statusColor,
    this.onCancel,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(booking.serviceName, style: AppTextStyles.subtitle1),
                ),
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(
                    color: statusColor.withOpacity(0.15),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Text(
                    booking.status.toUpperCase(),
                    style: AppTextStyles.overline.copyWith(color: statusColor),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Row(
              children: [
                const Icon(Icons.calendar_today,
                    size: 14, color: AppColors.textSecondary),
                const SizedBox(width: 4),
                Text(
                  '${booking.scheduledAt.day}/${booking.scheduledAt.month}/${booking.scheduledAt.year}',
                  style: AppTextStyles.caption,
                ),
                const SizedBox(width: 12),
                const Icon(Icons.location_on,
                    size: 14, color: AppColors.textSecondary),
                const SizedBox(width: 4),
                Expanded(
                  child: Text(
                    booking.address,
                    style: AppTextStyles.caption,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Text(
              '₹${booking.totalAmount.toStringAsFixed(0)}',
              style: AppTextStyles.subtitle1
                  .copyWith(color: AppColors.primary),
            ),
            if (onCancel != null) ...[
              const SizedBox(height: 8),
              TextButton(
                onPressed: onCancel,
                style: TextButton.styleFrom(
                  foregroundColor: AppColors.error,
                ),
                child: const Text('Cancel Booking'),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
