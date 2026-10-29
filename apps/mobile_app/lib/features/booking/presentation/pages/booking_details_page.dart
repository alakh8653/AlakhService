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
import '../../../payment/data/razorpay_checkout.dart';
import '../../../payment/presentation/tip_sheet.dart';
import '../../../payment/presentation/pages/invoice_page.dart';
import '../../../services/domain/repositories/service_repository.dart';
import '../../../services/presentation/pages/service_detail_page.dart';
import '../../data/availability_api.dart';
import '../../data/booking_queue_api.dart';
import '../../domain/entities/booking.dart';
import '../../domain/repositories/booking_repository.dart';
import '../widgets/booking_payment.dart';
import '../widgets/live_queue_card.dart';
import 'booking_history_page.dart' show bookingStatusLabel;
import 'reschedule_page.dart';

/// One booking: when and where, its payment (with the invoice), the chat with the shop, moving it to
/// another time, cancelling, and booking the same service again once it is over. Opened from My Bookings, an app link (/b/{id}) or a push notification.
class BookingDetailsPage extends StatefulWidget {
  final String bookingId;

  /// Shown straight away while the latest copy loads.
  final Booking? initial;
  final BookingRepository? repository;
  final PaymentApi? paymentApi;
  final ChatApi? chatApi;
  final AvailabilityApi? availabilityApi;
  final ServiceRepository? serviceRepository;
  final CheckoutLauncher? checkoutLauncher;
  final BookingQueueApi? queueApi;

  /// The current time (replaceable in tests).
  final DateTime Function() clock;

  /// Shows the invoice's HTML (a web view by default).
  final HtmlViewBuilder? invoiceViewer;

  const BookingDetailsPage({
    super.key,
    required this.bookingId,
    this.initial,
    this.repository,
    this.paymentApi,
    this.chatApi,
    this.availabilityApi,
    this.serviceRepository,
    this.checkoutLauncher,
    this.queueApi,
    this.clock = DateTime.now,
    this.invoiceViewer,
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
  bool _openingService = false;
  // The tip paid for a completed booking (rupees); null when none, or not known yet.
  double? _tip;

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
    _loadTip();
  }

  Future<void> _loadTip() async {
    if (_booking?.status != BookingStatus.completed) return;
    try {
      final tip = await _paymentApi.tipPaid(widget.bookingId);
      if (mounted) setState(() => _tip = tip);
    } catch (_) {
      // Without it the Add a tip button shows; payment_service refuses a second tip anyway.
    }
  }

  Future<void> _addTip(Booking booking) async {
    final paid = await showTipSheet(
      context,
      bookingId: booking.id,
      bookingNumber: booking.bookingNumber,
      paymentApi: widget.paymentApi,
      checkoutLauncher: widget.checkoutLauncher,
    );
    if (paid != null && mounted) setState(() => _tip = paid);
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

  Future<void> _reschedule(Booking booking) async {
    final moved = await Navigator.push<Booking>(
      context,
      MaterialPageRoute(
        builder: (_) => ReschedulePage(
          booking: booking,
          repository: widget.repository,
          availabilityApi: widget.availabilityApi,
          clock: widget.clock,
        ),
      ),
    );
    if (moved != null && mounted) _load();
  }

  /// Opens the service as it is offered now (price, shop, reviews), to book it again.
  Future<void> _bookAgain(Booking booking) async {
    final messenger = ScaffoldMessenger.of(context);
    setState(() => _openingService = true);
    final result = await (widget.serviceRepository ?? sl<ServiceRepository>()).getServiceById(booking.serviceId);
    if (!mounted) return;
    setState(() => _openingService = false);
    result.fold(
      (failure) => messenger.showSnackBar(SnackBar(content: Text(failure.message), backgroundColor: AppColors.error)),
      (service) => Navigator.push<void>(context, MaterialPageRoute(builder: (_) => ServiceDetailPage(service: service))),
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
        // Today, at the shop: place in line and the expected wait (shows nothing otherwise).
        if (booking.serviceMode == 'AT_SHOP' &&
            const {BookingStatus.pending, BookingStatus.confirmed, BookingStatus.assigned, BookingStatus.inProgress}
                .contains(booking.status))
          LiveQueueCard(key: ValueKey('queue-${booking.id}-${booking.status}'), bookingId: booking.id, api: widget.queueApi),
        const Divider(height: 24),
        _row(context, Icons.calendar_today, friendlyDateTime(booking.scheduledAt, l10n: l10n)),
        if (booking.serviceMode != 'AT_SHOP')
          _row(context, pickup ? Icons.local_shipping_outlined : Icons.home_outlined,
              [pickup ? l10n.modePickupDrop : l10n.modeHomeVisit, if (booking.itemDescription != null) booking.itemDescription!].join(' · ')),
        if (booking.address.isNotEmpty) _row(context, Icons.location_on, booking.address),
        _row(context, Icons.currency_rupee, rupees(booking.totalAmount)),
        if (booking.preferredStaffName != null) _row(context, Icons.person_outline, l10n.askedFor(booking.preferredStaffName!)),
        if (booking.pointsDiscount > 0) _row(context, Icons.card_giftcard, l10n.pointsUsed(rupees(booking.pointsDiscount))),
        if (shown != null)
          _row(context, Icons.receipt_long_outlined, paymentShownLabel(l10n, shown), color: paymentShownColor(context, shown)),
        if (_paymentId != null)
          Align(
            alignment: Alignment.centerLeft,
            child: TextButton.icon(
              onPressed: () => Navigator.push<void>(
                context,
                MaterialPageRoute(builder: (_) => InvoicePage(paymentId: _paymentId!, paymentApi: widget.paymentApi, viewer: widget.invoiceViewer)),
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
        if (booking.canReschedule(widget.clock())) ...[
          const SizedBox(height: 8),
          SizedBox(
            width: double.infinity,
            child: OutlinedButton.icon(
              onPressed: () => _reschedule(booking),
              icon: const Icon(Icons.edit_calendar_outlined),
              label: Text(l10n.rescheduleBooking),
            ),
          ),
        ],
        if (booking.status == BookingStatus.completed && booking.shopId != null) ...[
          const SizedBox(height: 8),
          if (_tip != null)
            _row(context, Icons.volunteer_activism, l10n.tipThanks(rupees(_tip!)), color: context.palette.success)
          else
            SizedBox(
              width: double.infinity,
              child: OutlinedButton.icon(
                onPressed: () => _addTip(booking),
                icon: const Icon(Icons.volunteer_activism_outlined),
                label: Text(l10n.tipAdd),
              ),
            ),
        ],
        if (booking.canBookAgain) ...[
          const SizedBox(height: 8),
          SizedBox(
            width: double.infinity,
            child: FilledButton.icon(
              onPressed: _openingService ? null : () => _bookAgain(booking),
              icon: const Icon(Icons.replay),
              label: Text(l10n.bookAgain),
            ),
          ),
        ],
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
