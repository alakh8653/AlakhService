import 'package:dio/dio.dart';

import '../../../core/constants/api_constants.dart';
import '../../../core/network/api_client.dart';
import '../../../core/network/api_errors.dart';

/// One message in a booking's chat, as booking_service shows it to this side: never the other
/// side's number or address.
class ChatMessage {
  final String id;
  final String bookingId;

  /// customer, shop or provider.
  final String senderRole;

  /// The customer's display name, or "Shop" / "Provider".
  final String senderName;
  final bool isMine;
  final String body;

  /// Contact details were hidden from this message by the server.
  final bool flagged;
  final DateTime createdAt;

  /// When the other side read it; null while unread.
  final DateTime? readAt;

  const ChatMessage({
    required this.id,
    required this.bookingId,
    required this.senderRole,
    required this.senderName,
    required this.isMine,
    required this.body,
    this.flagged = false,
    required this.createdAt,
    this.readAt,
  });

  bool get isRead => readAt != null;

  factory ChatMessage.fromJson(Map<String, dynamic> json) => ChatMessage(
        id: json['id'] as String,
        bookingId: (json['booking_id'] as String?) ?? '',
        senderRole: (json['sender_role'] as String?) ?? 'shop',
        senderName: (json['sender_name'] as String?) ?? '',
        isMine: (json['is_mine'] as bool?) ?? false,
        body: hidePhoneNumbers((json['body'] as String?) ?? ''),
        flagged: (json['flagged'] as bool?) ?? false,
        createdAt: DateTime.tryParse((json['created_at'] as String?) ?? '')?.toLocal() ?? DateTime.now(),
        readAt: DateTime.tryParse((json['read_at'] as String?) ?? '')?.toLocal(),
      );
}

/// A page of a booking's chat. Page 1 holds the newest messages; [items] are oldest first.
class ChatThread {
  final List<ChatMessage> items;
  final int total;
  final int page;
  final int perPage;

  /// Messages from the other side not yet marked read.
  final int unread;

  /// False once the chat is read-only.
  final bool canSend;

  /// When a closed booking's chat turns (or turned) read-only; null while the booking is open.
  final DateTime? openUntil;

  /// Whether the platform can place a masked call on this booking.
  final bool callingEnabled;

  const ChatThread({
    required this.items,
    required this.total,
    required this.page,
    required this.perPage,
    this.unread = 0,
    this.canSend = true,
    this.openUntil,
    this.callingEnabled = false,
  });

  /// Older messages remain on later pages.
  bool get hasOlder => page * perPage < total;

  factory ChatThread.fromJson(Map<String, dynamic> json) => ChatThread(
        items: ((json['items'] as List<dynamic>?) ?? const [])
            .map((e) => ChatMessage.fromJson(e as Map<String, dynamic>))
            .toList(),
        total: (json['total'] as num?)?.toInt() ?? 0,
        page: (json['page'] as num?)?.toInt() ?? 1,
        perPage: (json['per_page'] as num?)?.toInt() ?? 30,
        unread: (json['unread'] as num?)?.toInt() ?? 0,
        canSend: (json['can_send'] as bool?) ?? false,
        openUntil: DateTime.tryParse((json['open_until'] as String?) ?? '')?.toLocal(),
        callingEnabled: (json['calling_enabled'] as bool?) ?? false,
      );
}

// Ten or more digits in a row (a mobile or landline number), allowing the spaces, dots, dashes and brackets people type in numbers.
final RegExp _phoneLike = RegExp(r'\+?\d(?:[\s\-.()]*\d){9,}');

/// The server already hides contact details; this is a second guard so a number never shows in the
/// app, even from an older server.
String hidePhoneNumbers(String text) => text.replaceAll(_phoneLike, '•••');

/// A booking's chat with the shop, and the masked call (booking_service).
class ChatApi {
  final ApiClient apiClient;

  ChatApi(this.apiClient);

  static const int pageSize = 30;

  Future<T> _call<T>(Future<T> Function() request) async {
    try {
      return await request();
    } on DioException catch (e) {
      throw toServerException(e);
    }
  }

  Future<ChatThread> messages(String bookingId, {int page = 1, int perPage = pageSize}) => _call(() async {
        final response = await apiClient.get<Map<String, dynamic>>(
          ApiConstants.bookingMessages(bookingId),
          queryParameters: {'page': page, 'per_page': perPage},
        );
        return ChatThread.fromJson(response.data!);
      });

  /// Unread messages from the shop on this booking (for a badge).
  Future<int> unread(String bookingId) async => (await messages(bookingId, perPage: 1)).unread;

  Future<ChatMessage> send(String bookingId, String body) => _call(() async {
        final response = await apiClient.post<Map<String, dynamic>>(
          ApiConstants.bookingMessages(bookingId),
          data: {'body': body},
        );
        return ChatMessage.fromJson(response.data!);
      });

  Future<void> markRead(String bookingId) =>
      _call(() => apiClient.post<dynamic>(ApiConstants.bookingMessagesRead(bookingId)));

  /// Asks the platform to ring this phone and connect it to the shop without either side seeing
  /// the other's number. Returns the server's message to show.
  Future<String> callShop(String bookingId) => _call(() async {
        final response = await apiClient.post<Map<String, dynamic>>(ApiConstants.bookingCall(bookingId));
        return (response.data?['message'] as String?) ?? '';
      });
}
