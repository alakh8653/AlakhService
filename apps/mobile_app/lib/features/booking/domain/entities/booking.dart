import 'package:equatable/equatable.dart';

/// Booking statuses, as booking_service's state machine names them.
class BookingStatus {
  BookingStatus._();

  static const pending = 'PENDING';
  static const confirmed = 'CONFIRMED';
  static const assigned = 'ASSIGNED';
  static const enRoute = 'PROVIDER_EN_ROUTE';
  static const pickedUp = 'PICKED_UP';
  static const inProgress = 'IN_PROGRESS';
  static const outForDelivery = 'OUT_FOR_DELIVERY';
  static const completed = 'COMPLETED';
  static const cancelled = 'CANCELLED';
  static const disputed = 'DISPUTED';
  static const refunded = 'REFUNDED';

  /// Customers may move a booking to another time until a provider has it (booking_service).
  static const reschedulable = {pending, confirmed};

  /// Over: the customer can book the same service again.
  static const finished = {completed, cancelled, refunded};

  /// Customers may cancel until a provider is on the way.
  static const cancellable = {pending, confirmed, assigned};

  /// The provider is working on it: their live location is shared with the customer.
  static const trackable = {assigned, enRoute, pickedUp, inProgress, outForDelivery};

  /// payment_service accepts payment from confirmation until completion.
  static const payable = {confirmed, assigned, enRoute, pickedUp, inProgress, outForDelivery, completed};
}

/// A booking's payment, as booking_service reports it (payment_status).
class PaymentStatus {
  PaymentStatus._();

  static const unpaid = 'UNPAID';
  static const paid = 'PAID';
  static const refunded = 'REFUNDED';
  static const partiallyRefunded = 'PARTIALLY_REFUNDED';

  /// Money was taken (and maybe given back): there is an invoice and nothing more to pay.
  static const settled = {paid, refunded, partiallyRefunded};
}

/// How a booking is delivered and where: see ServiceMode. [addressId] is a saved address, needed
/// for a home visit or a pickup; [itemDescription] says what to collect for a pickup.
class BookingDelivery extends Equatable {
  final String mode;
  final String? addressId;
  final String? itemDescription;

  const BookingDelivery({this.mode = 'AT_SHOP', this.addressId, this.itemDescription});

  static const atShop = BookingDelivery();

  @override
  List<Object?> get props => [mode, addressId, itemDescription];
}

class Booking extends Equatable {
  final String id;
  final String bookingNumber;
  final String userId;
  final String serviceId;
  final String serviceName;
  final String? providerId;
  final String? shopId;
  final String status;
  final DateTime scheduledAt;
  final int durationMinutes;
  final String address;
  final double totalAmount;

  /// The catalogue price before a coupon, and the coupon used (if any).
  final double? listPrice;
  final String? couponCode;
  final String? notes;
  final DateTime createdAt;

  /// AT_SHOP, AT_HOME or PICKUP_DROP, and what is being collected for a pickup.
  final String serviceMode;
  final String? itemDescription;

  /// The saved address a home visit or pickup goes to.
  final String? addressId;

  /// Pickup & drop: when the shop expects the item to be back with the customer.
  final DateTime? readyBy;

  /// What booking_service knows of its payment: one of [PaymentStatus]; null from servers that
  /// don't report it (the app then works it out from the payments list).
  final String? paymentStatus;

  /// How many times the customer has moved it to another time.
  final int rescheduleCount;

  const Booking({
    required this.id,
    this.bookingNumber = '',
    required this.userId,
    required this.serviceId,
    required this.serviceName,
    this.providerId,
    this.shopId,
    required this.status,
    required this.scheduledAt,
    this.durationMinutes = 0,
    required this.address,
    required this.totalAmount,
    this.listPrice,
    this.couponCode,
    this.notes,
    required this.createdAt,
    this.serviceMode = 'AT_SHOP',
    this.itemDescription,
    this.addressId,
    this.readyBy,
    this.paymentStatus,
    this.rescheduleCount = 0,
  });

  bool get canCancel => BookingStatus.cancellable.contains(status);

  /// The customer can still move it: not yet with a provider, more than [freeCancellationBefore]
  /// ahead, and moved fewer than [maxReschedules] times (booking_service enforces the same).
  bool canReschedule(DateTime now) =>
      BookingStatus.reschedulable.contains(status) &&
      !inCancellationFeeWindow(now) &&
      rescheduleCount < maxReschedules;

  /// A customer may move a booking this many times.
  static const maxReschedules = 2;

  bool get canBookAgain => BookingStatus.finished.contains(status);
  bool get canTrack => providerId != null && BookingStatus.trackable.contains(status);
  bool get canPay => BookingStatus.payable.contains(status);
  bool get canRate => status == BookingStatus.completed && shopId != null;
  /// The customer goes to the shop for it, and it is still ahead of them (or under way).
  bool get canGetDirections =>
      serviceMode == 'AT_SHOP' &&
      shopId != null &&
      const {BookingStatus.pending, BookingStatus.confirmed, BookingStatus.assigned, BookingStatus.inProgress}.contains(status);
  /// The shop has said when a picked-up item will be back, and it is not back yet.
  bool get showsReadyBy =>
      readyBy != null &&
      serviceMode == 'PICKUP_DROP' &&
      !const {BookingStatus.completed, BookingStatus.cancelled, BookingStatus.refunded}.contains(status);
  /// Its time has gone by while it still waits on the shop (unconfirmed, or confirmed but not started).
  bool isOverdue(DateTime now) =>
      const {BookingStatus.pending, BookingStatus.confirmed}.contains(status) &&
      scheduledAt.isBefore(now.subtract(const Duration(minutes: 30)));
  /// booking_service says it has been paid (refunds included): no Pay button, and an invoice.
  bool get isPaid => PaymentStatus.settled.contains(paymentStatus);

  /// Inside the last two hours before its time, when cancelling may cost a fee.
  bool inCancellationFeeWindow(DateTime now) => now.isAfter(scheduledAt.subtract(freeCancellationBefore));

  /// Cancelling is free until this long before the booking's time.
  static const freeCancellationBefore = Duration(hours: 2);

  bool get canDispute => status == BookingStatus.inProgress || status == BookingStatus.completed;

  @override
  List<Object?> get props => [id, userId, serviceId, status, scheduledAt, providerId, paymentStatus, rescheduleCount];
}
