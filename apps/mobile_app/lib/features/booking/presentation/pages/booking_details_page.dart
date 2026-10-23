import 'package:flutter/material.dart';

import '../../../../core/di/injection_container.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_text_styles.dart';
import '../../../../core/theme/app_theme.dart';
import '../../../../l10n/l10n.dart';
import '../../../../shared/utils/format.dart';
import '../../../../shared/widgets/error_widget.dart';
import '../../../../shared/widgets/loading_indicator.dart';
import '../../../chat/data/chat_api.dart';
import '../../../chat/presentation/booking_chat_page.dart';
import '../../../payment/data/payment_api.dart';
import '../../../payment/presentation/pages/invoice_page.dart';
import '../../domain/entities/booking.dart';
import '../../domain/repositories/booking_repository.dart';
import '../widgets/booking_payment.dart';
import 'booking_history_page.dart' show bookingStatusLabel;

/// One booking: when and where, its payment (with the invoice), the chat with the shop, and
/// cancelling. Opened from My Bookings, an app link (/b/{id}) or a push notification.
class BookingDetailsPage extends StatefulWidget {
  final String bookingId;

  /// Shown straight away while the latest copy loads.
  final Booking? initial;
  final BookingRepository? repository;
  final PaymentApi? paymentApi;
  final ChatApi? chatApi;

  const BookingDetailsPage({
    super.key,
    required this.bookingId,
    this.initial,
    this.repository,
    this.paymentApi,
    this.chatApi,
  });

  @override
  State<BookingDetailsPage> createState() => _BookingDetailsPageState();
}

class _BookingDetailsPageState extends State<BookingDetailsPage> {
  late Booking? _booking = widget.initial;
  String? _error;
  // 'paid' or 'cash' from the payments list, and the id of a completed payment for the invoice.
  String? _payment;
  String? _paymentId;
  int _unread = 0;
  bool _cancelling = false;

  BookingRepository get _repository => widget.repository ?? sl<BookingRepository>();
  PaymentApi get _paymentApi => widget.paymentApi ?? sl<PaymentApi>();
  ChatApi get _chatApi => widget.chatApi ?? sl<ChatApi>();

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _error = null);
    final result = await _repository.getBookingById(widget.bookingId);
    if (!mounted) return;
    result.fold(
      (failure) => setState(() => _error = failure.message),
      (booking) => setState(() => _booking = booking),
    );
    _loadPayment();
    _loadUnread();
  }

  Future<void> _loadPayment() async {
    try {
      final states = await _paymentApi.paymentStateByBooking();
      final id = states[widget.bookingId] == 'paid' || (_booking?.isPaid ?? false)
          ? await _paymentApi.settledPaymentId(widget.bookingId)
          : null;
      if (mounted) {
        setState(() {
          _payment = states[widget.bookingId];
          _paymentId = id;
        });
      }
    } catch (_) {
      // Without it the payment line falls back to the booking's own status, and there is no invoice link.
    }
  }

  Future<void> _loadUnread() async {
    try {
      final unread = await _chatApi.unread(widget.bookingId);
      if (mounted) setState(() => _unread = unread);
    } catch (_) {}
  }

  Future<void> _openChat(Booking booking) async {
    await Navigator.push<void>(
      context,
      MaterialPageRoute(
        builder: (_) => BookingChatPage(bookingId: booking.id, subtitle: booking.serviceName, chatApi: widget.chatApi),
      ),
    );
    if (mounted) setState(() => _unread = 0);
  }

  Future<void> _cancel(Booking booking) async {
    if (!await confirmCancelBooking(context, booking) || !mounted) return;
    final messenger = ScaffoldMessenger.of(context);
    final l10n = context.l10n;
    setState(() => _cancelling = true);
    final result = await _repository.cancelBooking(booking.id);
    if (!mounted) return;
    setState(() => _cancelling = false);
    result.fold(
      (failure) => messenger.showSnackBar(SnackBar(content: Text(failure.message), backgroundColor: AppColors.error)),
      (_) {
        messenger.showSnackBar(SnackBar(content: Text(l10n.bookingCancelled), backgroundColor: AppColors.success));
        _load();
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final booking = _booking;
    return Scaffold(
      appBar: AppBar(title: Text(l10n.bookingDetailsTitle)),
      body: booking == null
          ? (_error != null ? AppErrorWidget(message: _error!, onRetry: _load) : LoadingIndicator(message: l10n.loadingBookings))
          : RefreshIndicator(onRefresh: _load, child: _details(context, l10n, booking)),
    );
  }

  Widget _row(BuildContext context, IconData icon, String text, {Color? color}) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 6),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(icon, size: 20, color: color ?? context.palette.muted),
            const SizedBox(width: 12),
            Expanded(child: Text(text, style: AppTextStyles.body2.copyWith(color: color ?? context.colors.onSurface))),
          ],
        ),
      );

  Widget _details(BuildContext context, AppLocalizations l10n, Booking booking) {
    final shown = paymentShown(booking, _payment);
    final pickup = booking.serviceMode == 'PICKUP_DROP';
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Text(booking.serviceName, style: AppTextStyles.heading3),
        if (booking.bookingNumber.isNotEmpty)
          Text(l10n.bookingNumber(booking.bookingNumber), style: AppTextStyles.caption.themed(context)),
        const SizedBox(height: 8),
        Text(
          bookingStatusLabel(l10n, booking.status),
          style: AppTextStyles.subtitle2.copyWith(color: context.colors.primary),
        ),
        const Divider(height: 24),
        _row(context, Icons.calendar_today, friendlyDateTime(booking.scheduledAt, l10n: l10n)),
        if (booking.serviceMode != 'AT_SHOP')
          _row(context, pickup ? Icons.local_shipping_outlined : Icons.home_outlined,
              [pickup ? l10n.modePickupDrop : l10n.modeHomeVisit, if (booking.itemDescription != null) booking.itemDescription!].join(' · ')),
        if (booking.address.isNotEmpty) _row(context, Icons.location_on, booking.address),
        _row(context, Icons.currency_rupee, rupees(booking.totalAmount)),
        if (shown != null)
          _row(context, Icons.receipt_long_outlined, paymentShownLabel(l10n, shown), color: paymentShownColor(context, shown)),
        if (_paymentId != null)
          Align(
            alignment: Alignment.centerLeft,
            child: TextButton.icon(
              onPressed: () => Navigator.push<void>(
                context,
                MaterialPageRoute(builder: (_) => InvoicePage(paymentId: _paymentId!, paymentApi: widget.paymentApi)),
              ),
              icon: const Icon(Icons.description_outlined, size: 18),
              label: Text(l10n.viewInvoice),
            ),
          ),
        const Divider(height: 24),
        Badge(
          isLabelVisible: _unread > 0,
          label: Text('$_unread'),
          alignment: AlignmentDirectional.topEnd,
          child: SizedBox(
            width: double.infinity,
            child: OutlinedButton.icon(
              onPressed: () => _openChat(booking),
              icon: const Icon(Icons.chat_bubble_outline),
              label: Text(_unread > 0 ? l10n.chatUnread(_unread) : l10n.chatTitle),
            ),
          ),
        ),
        if (booking.canCancel) ...[
          const SizedBox(height: 8),
          Text(l10n.cancelPolicy, style: AppTextStyles.caption.copyWith(color: context.palette.muted)),
          TextButton(
            onPressed: _cancelling ? null : () => _cancel(booking),
            style: TextButton.styleFrom(foregroundColor: context.colors.error),
            child: Text(_cancelling ? l10n.cancelling : l10n.cancelBooking),
          ),
        ],
        if (_error != null) ...[
          const SizedBox(height: 8),
          Text(_error!, style: AppTextStyles.caption.copyWith(color: context.colors.error)),
        ],
      ],
    );
  }
}
