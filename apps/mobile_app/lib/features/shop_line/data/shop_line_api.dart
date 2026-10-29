import 'package:dio/dio.dart';

import '../../../core/constants/api_constants.dart';
import '../../../core/network/api_client.dart';
import '../../../core/network/api_errors.dart';

/// One customer in the shop's line today.
class LineEntry {
  final String bookingId;
  final String name;

  /// WAITING, YOUR_TURN, IN_PROGRESS, UNSERVABLE or CHECK_IN_NEEDED.
  final String state;
  final int? position;
  final DateTime? estimatedStart;
  final DateTime? estimatedEnd;
  final String? serviceId;
  final String? staffId;
  final String? staffName;
  final bool walkIn;
  final bool vip;
  final bool checkedIn;
  final bool canMarkNoShow;
  final int runningLateMinutes;

  const LineEntry({
    required this.bookingId,
    required this.name,
    required this.state,
    this.position,
    this.estimatedStart,
    this.estimatedEnd,
    this.serviceId,
    this.staffId,
    this.staffName,
    this.walkIn = false,
    this.vip = false,
    this.checkedIn = false,
    this.canMarkNoShow = false,
    this.runningLateMinutes = 0,
  });

  bool get waiting => state == 'WAITING' || state == 'YOUR_TURN';

  static DateTime? _time(Object? v) => DateTime.tryParse((v as String?) ?? '')?.toLocal();

  factory LineEntry.fromJson(Map<String, dynamic> j) => LineEntry(
        bookingId: j['booking_id'] as String,
        name: j['customer_display_name'] as String? ?? 'Customer',
        state: j['state'] as String,
        position: (j['position'] as num?)?.toInt(),
        estimatedStart: _time(j['estimated_start']),
        estimatedEnd: _time(j['estimated_end']),
        serviceId: j['service_id'] as String?,
        staffId: j['staff_id'] as String?,
        staffName: j['staff_name'] as String?,
        walkIn: j['source'] == 'WALK_IN',
        vip: j['priority'] == 'VIP',
        checkedIn: j['checked_in'] as bool? ?? false,
        canMarkNoShow: j['can_mark_no_show'] as bool? ?? false,
        runningLateMinutes: (j['running_late_minutes'] as num?)?.toInt() ?? 0,
      );
}

/// A team member today.
class TeamMember {
  final String staffId;
  final String name;

  /// AVAILABLE, BREAK or OFF.
  final String status;
  final DateTime? until;
  final String? servingBookingId;
  final String? servingName;
  final int waiting;

  const TeamMember({
    required this.staffId,
    required this.name,
    required this.status,
    this.until,
    this.servingBookingId,
    this.servingName,
    this.waiting = 0,
  });

  factory TeamMember.fromJson(Map<String, dynamic> j) => TeamMember(
        staffId: j['staff_id'] as String,
        name: j['name'] as String? ?? 'Team member',
        status: j['status'] as String,
        until: DateTime.tryParse((j['until'] as String?) ?? '')?.toLocal(),
        servingBookingId: j['serving_booking_id'] as String?,
        servingName: j['serving_name'] as String?,
        waiting: (j['waiting'] as num?)?.toInt() ?? 0,
      );
}

/// A shop the signed-in user owns, and its services (for adding walk-ins).
class OwnedShop {
  final String id;
  final String name;
  final Map<String, String> services;

  const OwnedShop(this.id, this.name, this.services);
}

/// Runs the owner's shop line from the phone (booking_service's live queue): any kind of shop.
class ShopLineApi {
  final ApiClient apiClient;

  ShopLineApi(this.apiClient);

  Future<T> _call<T>(Future<T> Function() body) async {
    try {
      return await body();
    } on DioException catch (e) {
      throw toServerException(e);
    }
  }

  /// The first shop [userId] owns, or null when they own none.
  Future<OwnedShop?> ownedShop(String userId) => _call(() async {
        final shops = (await apiClient.get<List<dynamic>>(ApiConstants.shopsList, queryParameters: {'owner_id': userId})).data!;
        if (shops.isEmpty) return null;
        final shop = shops.first as Map<String, dynamic>;
        final id = shop['id'] as String;
        final services = (await apiClient.get<List<dynamic>>(ApiConstants.services, queryParameters: {'shop_id': id})).data!;
        return OwnedShop(id, shop['name'] as String? ?? '', {
          for (final s in services.cast<Map<String, dynamic>>())
            if (s['is_active'] != false) s['id'] as String: s['name'] as String? ?? '',
        });
      });

  Future<List<LineEntry>> line(String shopId) => _call(() async {
        final data = (await apiClient.get<List<dynamic>>(ApiConstants.shopLine(shopId))).data!;
        return data.map((e) => LineEntry.fromJson(e as Map<String, dynamic>)).toList();
      });

  Future<List<TeamMember>> team(String shopId) => _call(() async {
        final data = (await apiClient.get<List<dynamic>>('${ApiConstants.shopLine(shopId)}/team')).data!;
        return data.map((e) => TeamMember.fromJson(e as Map<String, dynamic>)).toList();
      });

  Future<void> setStatus(String shopId, String staffId, String status, {int? minutes}) => _call(() async {
        await apiClient.put('${ApiConstants.shopLine(shopId)}/team/$staffId', data: {
          'status': status,
          if (minutes != null) 'minutes': minutes,
        });
      });

  Future<LineEntry> callNext(String shopId, {String? staffId}) => _call(() async {
        final data = (await apiClient.post<Map<String, dynamic>>('${ApiConstants.shopLine(shopId)}/call-next', data: {'staff_id': staffId})).data!;
        return LineEntry.fromJson(data);
      });

  Future<LineEntry> addWalkIn(String shopId, String serviceId, String name) => _call(() async {
        final data = (await apiClient.post<Map<String, dynamic>>(ApiConstants.shopWalkIns(shopId), data: {'service_id': serviceId, 'name': name})).data!;
        return LineEntry.fromJson(data);
      });

  Future<void> start(String bookingId) => _call(() => apiClient.put(ApiConstants.bookingStatus(bookingId), data: {'status': 'IN_PROGRESS'}));

  Future<void> finish(String bookingId) => _call(() => apiClient.put(ApiConstants.bookingStatus(bookingId), data: {'status': 'COMPLETED'}));

  Future<void> noShow(String bookingId) => _call(() => apiClient.post(ApiConstants.bookingNoShow(bookingId)));

  Future<void> checkIn(String bookingId) => _call(() => apiClient.post(ApiConstants.bookingCheckIn(bookingId)));
}
