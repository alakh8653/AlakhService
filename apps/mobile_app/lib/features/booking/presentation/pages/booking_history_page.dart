import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../../core/di/injection_container.dart';
import '../../../../core/network/api_errors.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_theme.dart';
import '../../../../core/theme/app_text_styles.dart';
import '../../../../shared/utils/format.dart';
import '../../../../shared/widgets/custom_button.dart';
import '../../../../shared/widgets/error_widget.dart';
import '../../../../shared/widgets/loading_indicator.dart';
import '../../../directions/presentation/how_to_get_there_sheet.dart';
import '../../../payment/data/payment_api.dart';
import '../../../payment/presentation/pages/payment_page.dart';
import '../../../tracking/presentation/pages/live_tracking_page.dart';
import '../../data/dispute_api.dart';
import '../../data/rating_api.dart';
import '../../domain/entities/booking.dart';
import '../bloc/booking_bloc.dart';
import '../bloc/booking_event.dart';
import '../bloc/booking_state.dart';
import '../widgets/report_problem.dart';
import '../../../../l10n/l10n.dart';

class BookingHistoryPage extends StatefulWidget {
  /// Takes the customer to the catalogue (from the empty list).
  final VoidCallback? onBrowseServices;
  final PaymentApi? paymentApi;
  final RatingApi? ratingApi;
  final DisputeApi? disputeApi;

  const BookingHistoryPage({super.key, this.onBrowseServices, this.paymentApi, this.ratingApi, this.disputeApi});

  @override
  State<BookingHistoryPage> createState() => _BookingHistoryPageState();
}

class _BookingHistoryPageState extends State<BookingHistoryPage> {
  // booking id → 'paid' or 'cash' (to pay in person), so a paid booking isn't offered for payment again.
  Map<String, String> _payments = const {};
  // Bookings rated on this screen (a booking can be rated once), with the stars given.
  final Map<String, int> _rated = {};
  // The booking being cancelled, so its button can't be tapped twice.
  String? _cancelling;

  PaymentApi get _paymentApi => widget.paymentApi ?? sl<PaymentApi>();

  @override
  void initState() {
    super.initState();
    context.read<BookingBloc>().add(const LoadUserBookings());
    _loadPayments();
  }

  Future<void> _loadPayments() async {
    try {
      final states = await _paymentApi.paymentStateByBooking();
      if (mounted) setState(() => _payments = states);
    } catch (_) {
      // Without it the Pay button stays; the server still refuses a second payment.
    }
  }

  static Color statusColor(BuildContext context, String status) => switch (status) {
        BookingStatus.confirmed || BookingStatus.assigned => context.palette.info,
        BookingStatus.enRoute || BookingStatus.pickedUp || BookingStatus.inProgress || BookingStatus.outForDelivery => context.colors.primary,
        BookingStatus.completed => context.palette.success,
        BookingStatus.pending => context.palette.warning,
        BookingStatus.cancelled || BookingStatus.disputed => context.colors.error,
        _ => context.palette.muted,
      };

  static String statusLabel(AppLocalizations l10n, String status) => switch (status) {
        BookingStatus.pending => l10n.statusPending,
        BookingStatus.confirmed => l10n.statusConfirmed,
        BookingStatus.assigned => l10n.statusAssigned,
        BookingStatus.enRoute => l10n.statusEnRoute,
        BookingStatus.pickedUp => l10n.statusPickedUp,
        BookingStatus.inProgress => l10n.statusInProgress,
        BookingStatus.outForDelivery => l10n.statusOutForDelivery,
        BookingStatus.completed => l10n.statusCompleted,
        BookingStatus.cancelled => l10n.statusCancelled,
        BookingStatus.disputed => l10n.statusDisputed,
        BookingStatus.refunded => l10n.statusRefunded,
        _ => status,
      };

  Future<void> _confirmCancel(Booking booking) async {
    final l10n = context.l10n;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: Text(l10n.cancelBookingQuestion),
        content: Text(l10n.cancelBookingBody(booking.serviceName, friendlyDateTime(booking.scheduledAt, l10n: l10n))),
        actions: [
          TextButton(onPressed: () => Navigator.pop(dialogContext, false), child: Text(l10n.keepBooking)),
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, true),
            style: TextButton.styleFrom(foregroundColor: context.colors.error),
            child: Text(l10n.yesCancel),
          ),
        ],
      ),
    );
    if (confirmed == true && mounted) {
      setState(() => _cancelling = booking.id);
      context.read<BookingBloc>().add(CancelBookingRequested(booking.id));
    }
  }

  Future<void> _rate(Booking booking) async {
    final result = await showDialog<(int, String?)>(context: context, builder: (_) => const _RatingDialog());
    if (result == null || !mounted) return;
    final (stars, comment) = result;
    final messenger = ScaffoldMessenger.of(context);
    final l10n = context.l10n;
    try {
      await (widget.ratingApi ?? sl<RatingApi>()).rate(
        shopId: booking.shopId!,
        bookingId: booking.id,
        rating: stars.toDouble(),
        comment: comment,
      );
      if (mounted) setState(() => _rated[booking.id] = stars);
      messenger.showSnackBar(SnackBar(
        content: Text(comment == null ? l10n.thanksRating : l10n.thanksReview),
        backgroundColor: AppColors.success,
      ));
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text(apiErrorMessage(e)), backgroundColor: AppColors.error));
    }
  }

  Future<void> _report(Booking booking) async {
    final bloc = context.read<BookingBloc>();
    if (await reportBookingProblem(context, booking, api: widget.disputeApi)) bloc.add(const RefreshBookings());
  }

  void _open(Widget page) => Navigator.push(context, MaterialPageRoute(builder: (_) => page)).then((_) {
        if (!mounted) return;
        context.read<BookingBloc>().add(const RefreshBookings());
        _loadPayments();
      });

  /// Pull-to-refresh: keeps the spinner up until the list has actually reloaded.
  Future<void> _refresh() async {
    final bloc = context.read<BookingBloc>();
    final done = bloc.stream.firstWhere((s) => s is BookingsLoaded || s is BookingError);
    bloc.add(const RefreshBookings());
    await Future.wait([done, _loadPayments()]);
  }

  Widget _card(Booking b) => _BookingCard(
        booking: b,
        statusColor: statusColor(context, b.status),
        statusLabel: statusLabel(context.l10n, b.status),
        cancelling: _cancelling == b.id,
        onCancel: b.canCancel && _cancelling != b.id ? () => _confirmCancel(b) : null,
        onTrack: b.canTrack ? () => _open(LiveTrackingPage(booking: b)) : null,
        onPay: b.canPay && _payments[b.id] != 'paid'
            ? () => _open(PaymentPage(
                  bookingId: b.id,
                  amount: b.totalAmount,
                  bookingNumber: b.bookingNumber,
                  serviceName: b.serviceName,
                  paymentApi: widget.paymentApi,
                ))
            : null,
        payment: _payments[b.id],
        ratedStars: _rated[b.id],
        onRate: b.canRate && !_rated.containsKey(b.id) ? () => _rate(b) : null,
        onReport: b.canDispute ? () => _report(b) : null,
        onDirections: b.canGetDirections ? () => showHowToGetThere(context, shopId: b.shopId!) : null,
      );

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    return Scaffold(
      appBar: AppBar(title: Text(l10n.myBookings)),
      body: BlocConsumer<BookingBloc, BookingState>(
        listener: (context, state) {
          if (state is BookingCancelled) {
            setState(() => _cancelling = null);
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(content: Text(l10n.bookingCancelled), backgroundColor: AppColors.success),
            );
          } else if (state is BookingActionFailed) {
            setState(() => _cancelling = null);
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(content: Text(state.message), backgroundColor: AppColors.error),
            );
          }
        },
        // A cancel or refresh outcome is a message on top of the list, not a new screen.
        buildWhen: (previous, current) => current is! BookingCancelled && current is! BookingActionFailed,
        builder: (context, state) {
          if (state is BookingLoading || state is BookingInitial) {
            return LoadingIndicator(message: l10n.loadingBookings);
          }
          if (state is BookingError) {
            return AppErrorWidget(
              message: state.message,
              onRetry: () => context.read<BookingBloc>().add(const LoadUserBookings()),
            );
          }
          final bookings = state is BookingsLoaded ? state.bookings : const <Booking>[];
          if (bookings.isEmpty) {
            return RefreshIndicator(
              onRefresh: _refresh,
              child: ListView(
                padding: const EdgeInsets.all(32),
                children: [
                  const SizedBox(height: 80),
                  const Icon(Icons.calendar_today_outlined, size: 64, color: AppColors.textDisabled),
                  const SizedBox(height: 16),
                  Text(l10n.noBookings, style: AppTextStyles.subtitle1, textAlign: TextAlign.center),
                  const SizedBox(height: 4),
                  Text(
                    l10n.noBookingsBody,
                    style: AppTextStyles.body2.themed(context),
                    textAlign: TextAlign.center,
                  ),
                  if (widget.onBrowseServices != null) ...[
                    const SizedBox(height: 24),
                    Center(
                      child: CustomButton(
                        label: l10n.browseServices,
                        width: 220,
                        leadingIcon: Icons.search,
                        onPressed: widget.onBrowseServices,
                      ),
                    ),
                  ],
                ],
              ),
            );
          }
          final (upcoming, past) = splitBookings(bookings);
          return RefreshIndicator(
            onRefresh: _refresh,
            child: ListView(
              padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
              children: [
                if (upcoming.isNotEmpty) ...[
                  _SectionHeader(l10n.upcomingActive, count: upcoming.length),
                  for (final b in upcoming) Padding(padding: const EdgeInsets.only(bottom: 12), child: _card(b)),
                ],
                if (past.isNotEmpty) ...[
                  _SectionHeader(l10n.pastBookings, count: past.length),
                  for (final b in past) Padding(padding: const EdgeInsets.only(bottom: 12), child: _card(b)),
                ],
              ],
            ),
          );
        },
      ),
    );
  }
}

/// What a booking's status means to the customer, e.g. "Awaiting confirmation".
String bookingStatusLabel(AppLocalizations l10n, String status) => _BookingHistoryPageState.statusLabel(l10n, status);

/// Bookings still ahead or under way (soonest first), and finished ones (latest first).
(List<Booking>, List<Booking>) splitBookings(List<Booking> bookings) {
  const finished = {BookingStatus.completed, BookingStatus.cancelled, BookingStatus.refunded};
  final upcoming = bookings.where((b) => !finished.contains(b.status)).toList()
    ..sort((a, b) => a.scheduledAt.compareTo(b.scheduledAt));
  final past = bookings.where((b) => finished.contains(b.status)).toList()
    ..sort((a, b) => b.scheduledAt.compareTo(a.scheduledAt));
  return (upcoming, past);
}

class _SectionHeader extends StatelessWidget {
  final String title;
  final int count;

  const _SectionHeader(this.title, {required this.count});

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.fromLTRB(4, 12, 4, 8),
        child: Semantics(
          header: true,
          child: Text('$title ($count)', style: AppTextStyles.subtitle2.copyWith(color: context.colors.onSurface)),
        ),
      );
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
  final VoidCallback? onDirections;
  final String? payment;
  final int? ratedStars;
  final bool cancelling;

  const _BookingCard({
    required this.booking,
    required this.statusColor,
    required this.statusLabel,
    this.onCancel,
    this.onTrack,
    this.onPay,
    this.onRate,
    this.onReport,
    this.onDirections,
    this.payment,
    this.ratedStars,
    this.cancelling = false,
  });

  Widget _detail(BuildContext context, IconData icon, String text, {Color? color, int maxLines = 2}) => Padding(
        padding: const EdgeInsets.only(top: 4),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Padding(padding: const EdgeInsets.only(top: 2), child: Icon(icon, size: 14, color: color ?? context.palette.muted)),
            const SizedBox(width: 6),
            Expanded(
              child: Text(
                text,
                style: AppTextStyles.caption.copyWith(color: color ?? context.palette.muted),
                maxLines: maxLines,
                overflow: TextOverflow.ellipsis,
              ),
            ),
          ],
        ),
      );

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final actions = <Widget>[
      if (onDirections != null)
        TextButton.icon(onPressed: onDirections, icon: const Icon(Icons.directions, size: 18), label: Text(l10n.howToGetThere)),
      if (onTrack != null)
        TextButton.icon(onPressed: onTrack, icon: const Icon(Icons.location_on_outlined, size: 18), label: Text(l10n.track)),
      if (onPay != null)
        TextButton.icon(
          onPressed: onPay,
          icon: const Icon(Icons.payment, size: 18),
          label: Text(payment == 'cash' ? l10n.payOnlineInstead : l10n.payAmount(rupees(booking.totalAmount))),
        ),
      if (onRate != null)
        TextButton.icon(onPressed: onRate, icon: const Icon(Icons.star_outline, size: 18), label: Text(l10n.rate)),
      if (onReport != null)
        TextButton.icon(onPressed: onReport, icon: const Icon(Icons.report_outlined, size: 18), label: Text(l10n.reportProblem)),
      if (onCancel != null || cancelling)
        TextButton(
          onPressed: onCancel,
          style: TextButton.styleFrom(foregroundColor: context.colors.error),
          child: Text(cancelling ? l10n.cancelling : l10n.cancelBooking),
        ),
    ];
    final pickup = booking.serviceMode == 'PICKUP_DROP';
    return Card(
      margin: EdgeInsets.zero,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(child: Text(booking.serviceName, style: AppTextStyles.subtitle1)),
                const SizedBox(width: 8),
                // Up to about half the card: a long status (or large text) wraps instead of pushing
                // the card wider than the screen.
                ConstrainedBox(
                  constraints: BoxConstraints(maxWidth: MediaQuery.sizeOf(context).width * 0.45),
                  child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(
                    color: statusColor.withValues(alpha: 0.12),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Text(
                    statusLabel,
                    textAlign: TextAlign.center,
                    style: AppTextStyles.caption.copyWith(color: statusColor, fontWeight: FontWeight.w600),
                  ),
                ),
                ),
              ],
            ),
            if (booking.bookingNumber.isNotEmpty) Text(l10n.bookingNumber(booking.bookingNumber), style: AppTextStyles.caption.themed(context)),
            const SizedBox(height: 4),
            _detail(context, Icons.calendar_today, friendlyDateTime(booking.scheduledAt, l10n: l10n)),
            if (booking.isOverdue(DateTime.now()))
              _detail(
                context,
                Icons.info_outline,
                booking.status == BookingStatus.pending
                    ? l10n.overduePending
                    : l10n.overdueConfirmed,
                color: context.palette.warning,
                maxLines: 3,
              ),
            if (booking.serviceMode != 'AT_SHOP' || booking.itemDescription != null)
              _detail(
                context,
                pickup ? Icons.local_shipping_outlined : Icons.home_outlined,
                [
                  pickup ? l10n.modePickupDrop : l10n.modeHomeVisit,
                  if (booking.itemDescription != null) booking.itemDescription!,
                ].join(' · '),
              ),
            if (booking.showsReadyBy)
              _detail(context, Icons.event_available, l10n.expectedBackBy(friendlyDateTime(booking.readyBy!, l10n: l10n)), color: context.colors.primary),
            if (booking.address.isNotEmpty) _detail(context, Icons.location_on, booking.address),
            const SizedBox(height: 8),
            Wrap(
              crossAxisAlignment: WrapCrossAlignment.center,
              spacing: 8,
              children: [
                Text(rupees(booking.totalAmount), style: AppTextStyles.subtitle1.copyWith(color: context.colors.primary)),
                if (payment != null)
                  Text(
                    payment == 'paid' ? l10n.paid : l10n.payingCash,
                    style: AppTextStyles.caption.copyWith(color: payment == 'paid' ? context.palette.success : context.palette.warning),
                  ),
                if (ratedStars != null)
                  Text(l10n.youRated(ratedStars!), style: AppTextStyles.caption.copyWith(color: context.palette.success)),
              ],
            ),
            if (actions.isNotEmpty) ...[
              const Divider(height: 16),
              Wrap(alignment: WrapAlignment.end, spacing: 4, children: actions),
            ],
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

/// Stars and an optional written review; pops with (stars, review or null).
class _RatingDialogState extends State<_RatingDialog> {
  int _stars = 5;
  final _review = TextEditingController();


  @override
  void dispose() {
    _review.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final words = [l10n.ratingPoor, l10n.ratingBelowAverage, l10n.ratingOkay, l10n.ratingGood, l10n.ratingExcellent];
    return AlertDialog(
      title: Text(l10n.howWasIt),
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            FittedBox(
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: List.generate(
                  5,
                  (i) => IconButton(
                    tooltip: l10n.starsCount(i + 1),
                    isSelected: i < _stars,
                    onPressed: () => setState(() => _stars = i + 1),
                    icon: Icon(i < _stars ? Icons.star : Icons.star_border, color: AppColors.starFilled, size: 32),
                  ),
                ),
              ),
            ),
            Text(words[_stars - 1], style: AppTextStyles.subtitle2.themed(context)),
            const SizedBox(height: 12),
            TextField(
              controller: _review,
              maxLines: 4,
              minLines: 2,
              maxLength: 1000,
              textCapitalization: TextCapitalization.sentences,
              decoration: InputDecoration(
                labelText: l10n.writeReview,
                hintText: l10n.reviewHint,
                helperText: l10n.reviewHelper,
                helperMaxLines: 2,
                alignLabelWithHint: true,
              ),
            ),
          ],
        ),
      ),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context), child: Text(l10n.notNow)),
        TextButton(
          onPressed: () {
            final review = _review.text.trim();
            Navigator.pop(context, (_stars, review.isEmpty ? null : review));
          },
          child: Text(l10n.submit),
        ),
      ],
    );
  }
}
