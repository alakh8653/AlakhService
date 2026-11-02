import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../../core/constants/api_constants.dart';
import '../../../core/network/api_client.dart';
import '../../../core/network/api_errors.dart';

/// Ways a service reaches its customer (service_catalog's service_modes, a booking's service_mode).
const modeAtShop = 'AT_SHOP';
const modeAtHome = 'AT_HOME';
const modePickupDrop = 'PICKUP_DROP';

/// Whether this person came to the app to offer services: they set up a business on first sign-in and
/// the app opens on it. Only a preference on the device; owning a shop is what makes someone an owner.
class OwnerIntent {
  OwnerIntent._();

  static const _key = 'offers_services';

  static Future<bool> read() async {
    try {
      return (await SharedPreferences.getInstance()).getBool(_key) ?? false;
    } catch (_) {
      return false;
    }
  }

  static Future<void> save(bool offersServices) async {
    try {
      await (await SharedPreferences.getInstance()).setBool(_key, offersServices);
    } catch (_) {
      // Only a convenience: they can still start from Profile.
    }
  }
}

/// The owner's view of their shop, with what its review needs.
class OwnerShop {
  final String id;
  final String name;

  /// PENDING_REVIEW, APPROVED or REJECTED.
  final String verificationStatus;
  final String? rejectionReason;
  final DateTime? submittedAt;
  final String? legalName;
  final String? legalAddress;
  final String? gstin;

  const OwnerShop({
    required this.id,
    required this.name,
    required this.verificationStatus,
    this.rejectionReason,
    this.submittedAt,
    this.legalName,
    this.legalAddress,
    this.gstin,
  });

  bool get approved => verificationStatus == 'APPROVED';
  bool get rejected => verificationStatus == 'REJECTED';
  bool get waitingForReview => verificationStatus == 'PENDING_REVIEW' && submittedAt != null;

  factory OwnerShop.fromJson(Map<String, dynamic> j) => OwnerShop(
        id: j['id'] as String,
        name: j['name'] as String? ?? '',
        verificationStatus: j['verification_status'] as String? ?? 'PENDING_REVIEW',
        rejectionReason: j['rejection_reason'] as String?,
        submittedAt: DateTime.tryParse((j['submitted_at'] as String?) ?? ''),
        legalName: j['legal_name'] as String?,
        legalAddress: j['legal_address'] as String?,
        gstin: j['gstin'] as String?,
      );
}

class OwnerService {
  final String id;
  final String name;
  final int priceCents;
  final int? durationMinutes;
  final bool active;
  final List<String> modes;

  const OwnerService({
    required this.id,
    required this.name,
    required this.priceCents,
    this.durationMinutes,
    this.active = true,
    this.modes = const [modeAtShop],
  });

  factory OwnerService.fromJson(Map<String, dynamic> j) => OwnerService(
        id: j['id'] as String,
        name: j['name'] as String? ?? '',
        priceCents: (j['price_cents'] as num?)?.toInt() ?? 0,
        durationMinutes: (j['duration_minutes'] as num?)?.toInt(),
        active: j['is_active'] as bool? ?? true,
        modes: ((j['service_modes'] as List<dynamic>?) ?? const [modeAtShop]).cast<String>(),
      );
}

class OwnerBooking {
  final String id;
  final String number;
  final String customerName;
  final String serviceId;
  final String status;
  final DateTime scheduledAt;
  final String mode;

  /// In paise, as booking_service keeps it.
  final int totalCents;
  final String? notes;

  const OwnerBooking({
    required this.id,
    required this.number,
    required this.customerName,
    required this.serviceId,
    required this.status,
    required this.scheduledAt,
    this.mode = modeAtShop,
    this.totalCents = 0,
    this.notes,
  });

  factory OwnerBooking.fromJson(Map<String, dynamic> j) => OwnerBooking(
        id: j['id'] as String,
        number: j['booking_number'] as String? ?? '',
        customerName: j['customer_display_name'] as String? ?? '',
        serviceId: j['service_id'] as String? ?? '',
        status: j['status'] as String,
        scheduledAt: DateTime.parse(j['scheduled_at'] as String).toLocal(),
        mode: j['service_mode'] as String? ?? modeAtShop,
        totalCents: (j['total_amount'] as num?)?.toInt() ?? 0,
        notes: j['notes'] as String?,
      );
}

/// What the owner may do next with a booking.
enum OwnerAction { accept, decline, customerArrived, goMyself, onTheWay, onTheWayToCollect, pickedUp, startWork, start, sendBack, delivered, complete, cancel }

/// Where each action moves a booking; null for those with their own route (decline, cancel, goMyself).
const Map<OwnerAction, String?> ownerActionTargets = {
  OwnerAction.accept: 'CONFIRMED',
  OwnerAction.decline: null,
  OwnerAction.customerArrived: 'IN_PROGRESS',
  OwnerAction.goMyself: null,
  OwnerAction.onTheWay: 'PROVIDER_EN_ROUTE',
  OwnerAction.onTheWayToCollect: 'PROVIDER_EN_ROUTE',
  OwnerAction.pickedUp: 'PICKED_UP',
  OwnerAction.startWork: 'IN_PROGRESS',
  OwnerAction.start: 'IN_PROGRESS',
  OwnerAction.sendBack: 'OUT_FOR_DELIVERY',
  OwnerAction.delivered: 'COMPLETED',
  OwnerAction.complete: 'COMPLETED',
  OwnerAction.cancel: null,
};

/// The actions for a booking, main one first. Mirrors the shop dashboard's MODE_ACTIONS and the transitions
/// booking_service accepts for each way of delivering a service.
List<OwnerAction> ownerActions(String status, String mode) {
  if (status == 'PENDING') return const [OwnerAction.accept, OwnerAction.decline];
  if (mode == modeAtHome) {
    return switch (status) {
      'CONFIRMED' => const [OwnerAction.goMyself, OwnerAction.cancel],
      'ASSIGNED' => const [OwnerAction.onTheWay, OwnerAction.cancel],
      'PROVIDER_EN_ROUTE' => const [OwnerAction.start],
      'IN_PROGRESS' => const [OwnerAction.complete],
      _ => const [],
    };
  }
  if (mode == modePickupDrop) {
    return switch (status) {
      'CONFIRMED' => const [OwnerAction.goMyself, OwnerAction.cancel],
      'ASSIGNED' => const [OwnerAction.onTheWayToCollect, OwnerAction.pickedUp, OwnerAction.cancel],
      'PROVIDER_EN_ROUTE' => const [OwnerAction.pickedUp],
      'PICKED_UP' => const [OwnerAction.startWork],
      'IN_PROGRESS' => const [OwnerAction.sendBack],
      'OUT_FOR_DELIVERY' => const [OwnerAction.delivered],
      _ => const [],
    };
  }
  return switch (status) {
    'CONFIRMED' => const [OwnerAction.customerArrived, OwnerAction.cancel],
    'ASSIGNED' => const [OwnerAction.customerArrived, OwnerAction.cancel],
    'PROVIDER_EN_ROUTE' => const [OwnerAction.start],
    'IN_PROGRESS' => const [OwnerAction.complete],
    _ => const [],
  };
}

/// One picked document, ready to upload.
class PickedDocument {
  final Uint8List bytes;
  final String contentType;
  final String fileName;

  const PickedDocument(this.bytes, this.contentType, this.fileName);
}

/// Payout details as the server shows them: the account number is masked.
class PayoutDetails {
  final String method;
  final String? accountName;
  final String? accountNumber;
  final String? ifsc;
  final String? upiId;

  const PayoutDetails({required this.method, this.accountName, this.accountNumber, this.ifsc, this.upiId});

  factory PayoutDetails.fromJson(Map<String, dynamic> j) => PayoutDetails(
        method: j['method'] as String,
        accountName: j['account_name'] as String?,
        accountNumber: j['account_number'] as String?,
        ifsc: j['ifsc'] as String?,
        upiId: j['upi_id'] as String?,
      );
}

/// Opening hours for the week as the owner sets them on the phone: the same hours on the chosen days.
class WeekHours {
  /// 0 = Monday ... 6 = Sunday.
  final Set<int> days;

  /// Minutes after midnight.
  final int opens;
  final int closes;

  /// True when the saved week has more than this can show, such as a lunch break.
  final bool simplified;

  const WeekHours({required this.days, required this.opens, required this.closes, this.simplified = false});

  /// What a shop that has never set its hours starts from: Monday to Saturday, 10 AM to 8 PM.
  static const suggested = WeekHours(days: {0, 1, 2, 3, 4, 5}, opens: 600, closes: 1200);

  bool get valid => days.isNotEmpty && opens < closes;

  /// The nearest quarter of an hour: the only times shop_service takes, and all a customer needs.
  static int toQuarterHour(int minutes) => ((minutes + 7) ~/ 15) * 15;

  static String hhmm(int minutes) =>
      '${(minutes ~/ 60).toString().padLeft(2, '0')}:${(minutes % 60).toString().padLeft(2, '0')}';

  static int _minutes(String value) {
    final parts = value.split(':');
    return int.parse(parts[0]) * 60 + int.parse(parts[1]);
  }

  Map<String, Object> toJson() => {
        'weekly': [
          for (var day = 0; day < 7; day++)
            {
              'day': day,
              'intervals': [
                if (days.contains(day)) {'start': hhmm(opens), 'end': hhmm(closes)},
              ],
            },
        ],
      };

  /// From GET /shops/{id}/hours; the suggested week until the owner has saved one.
  factory WeekHours.fromSchedule(Map<String, dynamic> j) {
    if (j['configured'] != true) return suggested;
    final open = <int, List<dynamic>>{
      for (final d in (j['weekly'] as List<dynamic>).cast<Map<String, dynamic>>())
        if ((d['intervals'] as List<dynamic>).isNotEmpty) d['day'] as int: d['intervals'] as List<dynamic>,
    };
    if (open.isEmpty) return const WeekHours(days: {}, opens: 600, closes: 1200);
    final first = open.values.first;
    final opens = _minutes((first.first as Map<String, dynamic>)['start'] as String);
    final closes = _minutes((first.last as Map<String, dynamic>)['end'] as String);
    final same = open.values.every((intervals) =>
        intervals.length == 1 &&
        _minutes((intervals.first as Map<String, dynamic>)['start'] as String) == opens &&
        _minutes((intervals.first as Map<String, dynamic>)['end'] as String) == closes);
    return WeekHours(days: open.keys.toSet(), opens: opens, closes: closes, simplified: !same);
  }
}

/// What an owner does from the phone, through the same routes as the shop dashboard.
class ShopOwnerApi {
  final ApiClient apiClient;

  ShopOwnerApi(this.apiClient);

  Future<T> _call<T>(Future<T> Function() body) async {
    try {
      return await body();
    } on DioException catch (e) {
      throw toServerException(e);
    }
  }

  static const _shops = '${ApiConstants.apiVersion}/shops';
  static const _staff = '${ApiConstants.apiVersion}/staff';

  // The business

  Future<OwnerShop> createShop({
    required String ownerId,
    required String name,
    required String category,
    required String city,
    String? address,
    String? phone,
    double? latitude,
    double? longitude,
  }) =>
      _call(() async {
        final response = await apiClient.post<Map<String, dynamic>>(_shops, data: {
          'owner_id': ownerId,
          'name': name,
          'category': category,
          'city': city,
          if (address != null && address.isNotEmpty) 'address': address,
          if (phone != null && phone.isNotEmpty) 'phone': phone,
          if (latitude != null) 'latitude': latitude,
          if (longitude != null) 'longitude': longitude,
        });
        return OwnerShop.fromJson(response.data!);
      });

  Future<OwnerShop> shop(String shopId) => _call(() async {
        return OwnerShop.fromJson((await apiClient.get<Map<String, dynamic>>(ApiConstants.shop(shopId))).data!);
      });

  /// The owner as the shop's own team member: bookings away from the shop can only go to staff, so a
  /// person working alone needs this to take their own jobs, and the live line plans around it.
  Future<void> ensureOwnerIsStaff(String shopId, String userId, String name, {String? phone}) => _call(() async {
        final staff = (await apiClient.get<List<dynamic>>(_staff, queryParameters: {'shop_id': shopId})).data!;
        if (staff.cast<Map<String, dynamic>>().any((m) => m['user_id'] == userId && m['is_active'] != false)) return;
        await apiClient.post<Map<String, dynamic>>(_staff, data: {
          'shop_id': shopId,
          'name': name,
          'role': 'owner',
          'user_id': userId,
          if (phone != null && phone.isNotEmpty) 'phone': phone,
        });
      });

  Future<void> saveHours(String shopId, WeekHours hours) => _call(() async {
        await apiClient.put<Map<String, dynamic>>(ApiConstants.shopHours(shopId), data: hours.toJson());
      });

  Future<WeekHours> hours(String shopId) => _call(() async {
        return WeekHours.fromSchedule((await apiClient.get<Map<String, dynamic>>(ApiConstants.shopHours(shopId))).data!);
      });

  // Services

  Future<List<OwnerService>> services(String shopId) => _call(() async {
        final data = (await apiClient.get<List<dynamic>>(ApiConstants.services,
                queryParameters: {'shop_id': shopId, 'include_inactive': true, 'limit': 100}))
            .data!;
        return data.map((e) => OwnerService.fromJson(e as Map<String, dynamic>)).toList();
      });

  Future<OwnerService> addService({
    required String shopId,
    required String name,
    required int priceCents,
    required int durationMinutes,
    required List<String> modes,
  }) =>
      _call(() async {
        final response = await apiClient.post<Map<String, dynamic>>(ApiConstants.services, data: {
          'shop_id': shopId,
          'name': name,
          'price_cents': priceCents,
          'duration_minutes': durationMinutes,
          'service_modes': modes,
        });
        return OwnerService.fromJson(response.data!);
      });

  Future<void> setServiceActive(String serviceId, bool active) => _call(() async {
        await apiClient.put<Map<String, dynamic>>('${ApiConstants.services}/$serviceId', data: {'is_active': active});
      });

  // Verification

  Future<void> saveLegalDetails(String shopId, {required String legalName, String? legalAddress, String? gstin}) =>
      _call(() async {
        await apiClient.put<Map<String, dynamic>>(ApiConstants.shop(shopId), data: {
          'legal_name': legalName,
          'legal_address': legalAddress ?? '',
          'gstin': (gstin == null || gstin.isEmpty) ? null : gstin,
        });
      });

  /// The types of document already uploaded (PAN, GST, AADHAAR, UDYAM, BANK_PROOF or SHOP_PHOTO).
  Future<Set<String>> documentTypes(String shopId) => _call(() async {
        final data = (await apiClient.get<List<dynamic>>('${ApiConstants.shop(shopId)}/documents')).data!;
        return data.cast<Map<String, dynamic>>().map((d) => d['type'] as String).toSet();
      });

  /// The raw file is the request body, as shop_service expects.
  Future<void> uploadDocument(String shopId, String type, PickedDocument file) => _call(() async {
        await apiClient.post<Map<String, dynamic>>(
          '${ApiConstants.shop(shopId)}/documents/upload',
          queryParameters: {'type': type, 'file_name': file.fileName},
          data: Stream<List<int>>.fromIterable([file.bytes]),
          options: Options(
            contentType: file.contentType,
            headers: {Headers.contentLengthHeader: file.bytes.length},
            sendTimeout: const Duration(minutes: 2),
          ),
        );
      });

  Future<PayoutDetails?> payoutDetails(String shopId) async {
    try {
      final response = await apiClient.get<Map<String, dynamic>>('${ApiConstants.shop(shopId)}/payout-details');
      return PayoutDetails.fromJson(response.data!);
    } on DioException catch (e) {
      if (e.response?.statusCode == 404) return null;
      throw toServerException(e);
    }
  }

  Future<void> savePayoutDetails(
    String shopId, {
    required String method,
    String? accountName,
    String? accountNumber,
    String? ifsc,
    String? upiId,
  }) =>
      _call(() async {
        await apiClient.put<Map<String, dynamic>>('${ApiConstants.shop(shopId)}/payout-details', data: {
          'method': method,
          if (accountName != null && accountName.isNotEmpty) 'account_name': accountName,
          if (accountNumber != null && accountNumber.isNotEmpty) 'account_number': accountNumber,
          if (ifsc != null && ifsc.isNotEmpty) 'ifsc': ifsc,
          if (upiId != null && upiId.isNotEmpty) 'upi_id': upiId,
        });
      });

  Future<OwnerShop> submitForReview(String shopId) => _call(() async {
        final response =
            await apiClient.post<Map<String, dynamic>>('${ApiConstants.shop(shopId)}/submit-for-review');
        return OwnerShop.fromJson(response.data!);
      });

  // Bookings

  /// Bookings from yesterday on, soonest first: new requests and the day's work.
  Future<List<OwnerBooking>> bookings(String shopId, {DateTime? now}) => _call(() async {
        final yesterday = (now ?? DateTime.now()).toUtc().subtract(const Duration(days: 1));
        final day = '${yesterday.year.toString().padLeft(4, '0')}-'
            '${yesterday.month.toString().padLeft(2, '0')}-${yesterday.day.toString().padLeft(2, '0')}';
        final data = (await apiClient.get<Map<String, dynamic>>('${ApiConstants.bookings}/shop/$shopId',
                queryParameters: {'per_page': 100, 'date_from': day}))
            .data!;
        final items = (data['items'] as List<dynamic>)
            .map((e) => OwnerBooking.fromJson(e as Map<String, dynamic>))
            .toList();
        items.sort((a, b) => a.scheduledAt.compareTo(b.scheduledAt));
        return items;
      });

  Future<void> setStatus(String bookingId, String status) => _call(() async {
        await apiClient.put<Map<String, dynamic>>('${ApiConstants.bookings}/$bookingId/status', data: {'status': status});
      });

  /// Refunded in full, as a cancellation by the shop.
  Future<void> cancel(String bookingId, String reason) => _call(() async {
        await apiClient.post<Map<String, dynamic>>('${ApiConstants.bookings}/$bookingId/cancel', data: {'reason': reason});
      });

  /// The owner takes a home visit or pickup themselves.
  Future<void> assignToMe(String bookingId, String shopId, String userId, String name) async {
    await ensureOwnerIsStaff(shopId, userId, name);
    await _call(() async {
      await apiClient.post<Map<String, dynamic>>('${ApiConstants.bookings}/$bookingId/assign', data: {'provider_id': userId});
    });
  }
}
