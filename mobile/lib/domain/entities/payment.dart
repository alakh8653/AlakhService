import 'package:equatable/equatable.dart';

enum PaymentStatus { pending, processing, completed, failed, refunded }

enum PaymentMethod { card, wallet, bankTransfer, cash }

class Payment extends Equatable {
  const Payment({
    required this.id,
    required this.bookingId,
    required this.amount,
    required this.currency,
    required this.status,
    required this.method,
    this.transactionId,
    this.paidAt,
    this.createdAt,
  });

  final String id;
  final String bookingId;
  final double amount;
  final String currency;
  final PaymentStatus status;
  final PaymentMethod method;
  final String? transactionId;
  final DateTime? paidAt;
  final DateTime? createdAt;

  bool get isPaid => status == PaymentStatus.completed;

  @override
  List<Object?> get props => [
        id, bookingId, amount, currency, status,
        method, transactionId, paidAt, createdAt,
      ];
}
