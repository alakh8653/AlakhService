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

  /// Days after completion in which a customer may ask for a free fix (0 to 90).
  final int guaranteeDays;

  static const defaultGuaranteeDays = 7;

  const OwnerShop({
    required this.id,
    required this.name,
    required this.verificationStatus,
    this.rejectionReason,
    this.submittedAt,
    this.legalName,
    this.legalAddress,
    this.gstin,
    this.guaranteeDays = defaultGuaranteeDays,
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
        guaranteeDays: (j['guarantee_days'] as num?)?.toInt() ?? defaultGuaranteeDays,
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

  /// UNPAID, PAID, REFUNDED or PARTIALLY_REFUNDED.
  final String paymentStatus;

  /// An extra charge waiting for the customer's answer.
  final String? pendingExtraId;
  final int? pendingExtraCents;
  final String? pendingExtraReason;

  /// Of [totalCents], what the customer agreed to on top.
  final int extraCents;

  /// Who does the job, and the booking this one fixes for free.
  final String? providerId;
  final String? reworkOf;

  bool get isFreeFix => reworkOf != null;

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
    this.paymentStatus = 'UNPAID',
    this.pendingExtraId,
    this.pendingExtraCents,
    this.pendingExtraReason,
    this.extraCents = 0,
    this.providerId,
    this.reworkOf,
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
        paymentStatus: j['payment_status'] as String? ?? 'UNPAID',
        pendingExtraId: j['pending_extra_id'] as String?,
        pendingExtraCents: (j['pending_extra_amount'] as num?)?.toInt(),
        pendingExtraReason: j['pending_extra_reason'] as String?,
        extraCents: (j['extra_amount'] as num?)?.toInt() ?? 0,
        providerId: j['provider_id']?.toString(),
        reworkOf: (j['rework_of'] ?? (j['metadata'] is Map ? (j['metadata'] as Map)['rework_of'] : null))?.toString(),
      );
}

/// Statuses in which booking_service takes an extra charge: from when a provider can have seen the job until it
/// is finished.
const extraChargeStatuses = {'CONFIRMED', 'ASSIGNED', 'PROVIDER_EN_ROUTE', 'PICKED_UP', 'IN_PROGRESS', 'OUT_FOR_DELIVERY'};

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
/// A document this type of work asks for (shop_service's verification checklist).
class ChecklistItem {
  final String type;
  final String label;
  final bool required;
  final bool done;

  const ChecklistItem({required this.type, required this.label, required this.required, required this.done});

  factory ChecklistItem.fromJson(Map<String, dynamic> j) => ChecklistItem(
        type: j['type'] as String,
        label: j['label'] as String,
        required: j['required'] as bool? ?? false,
        done: j['done'] as bool? ?? false,
      );
}

/// Someone served by this business, by display name only.
class ShopCustomer {
  final String name;
  final int visits;
  final double spent;
  final DateTime lastVisit;

  const ShopCustomer({required this.name, required this.visits, required this.spent, required this.lastVisit});

  factory ShopCustomer.fromJson(Map<String, dynamic> j) => ShopCustomer(
        name: j['name'] as String,
        visits: (j['visits'] as num).toInt(),
        spent: (j['spent'] as num).toDouble(),
        lastVisit: DateTime.parse(j['last_visit'] as String).toLocal(),
      );
}

/// One day's, or for a year one month's, figures in a report.
class ReportLine {
  final String label;
  final double profit;

  const ReportLine(this.label, this.profit);
}

/// A day's, week's, month's or financial year's profit and loss (payment_service), in rupees.
class ShopReport {
  final String label;
  final String from;
  final String to;
  final int bookings;
  final double gross;
  final double cash;
  final double online;
  final double commission;
  final double gst;
  final double earned;
  final double otherIncome;
  final double expenses;
  final double profit;
  final double tips;
  final double? profitChangePercent;
  final List<ReportLine> breakdown;

  const ShopReport({
    required this.label,
    required this.from,
    required this.to,
    required this.bookings,
    required this.gross,
    required this.cash,
    required this.online,
    required this.commission,
    required this.gst,
    required this.earned,
    required this.otherIncome,
    required this.expenses,
    required this.profit,
    required this.tips,
    this.profitChangePercent,
    this.breakdown = const [],
  });

  factory ShopReport.fromJson(Map<String, dynamic> j) {
    double n(String key) => (j[key] as num?)?.toDouble() ?? 0;
    return ShopReport(
      label: j['label'] as String,
      from: j['from'] as String,
      to: j['to'] as String,
      bookings: (j['bookings'] as num?)?.toInt() ?? 0,
      gross: n('gross'),
      cash: n('cash'),
      online: n('online'),
      commission: n('commission'),
      gst: n('gst'),
      earned: n('earned'),
      otherIncome: n('other_income'),
      expenses: n('expenses'),
      profit: n('profit'),
      tips: n('tips'),
      profitChangePercent: (j['profit_change_percent'] as num?)?.toDouble(),
      breakdown: ((j['breakdown'] as List<dynamic>?) ?? const [])
          .cast<Map<String, dynamic>>()
          .map((b) => ReportLine(b['label'] as String, (b['profit'] as num).toDouble()))
          .toList(),
    );
  }
}

/// An expense or outside income the owner wrote down.
class CashEntry {
  final String id;
  final String kind;
  final String category;
  final double amount;
  final String onDate;
  final String? note;

  const CashEntry({
    required this.id,
    required this.kind,
    required this.category,
    required this.amount,
    required this.onDate,
    this.note,
  });

  factory CashEntry.fromJson(Map<String, dynamic> j) => CashEntry(
        id: j['id'] as String,
        kind: j['kind'] as String,
        category: j['category'] as String,
        amount: (j['amount'] as num).toDouble(),
        onDate: j['on_date'] as String,
        note: j['note'] as String?,
      );
}

/// Which reports reach the owner, and where.
class ReportSettings {
  final bool daily, weekly, monthly, yearly, email, whatsapp;

  const ReportSettings({
    required this.daily,
    required this.weekly,
    required this.monthly,
    required this.yearly,
    required this.email,
    required this.whatsapp,
  });

  factory ReportSettings.fromJson(Map<String, dynamic> j) => ReportSettings(
        daily: j['daily'] as bool,
        weekly: j['weekly'] as bool,
        monthly: j['monthly'] as bool,
        yearly: j['yearly'] as bool,
        email: j['email'] as bool,
        whatsapp: j['whatsapp'] as bool,
      );

  Map<String, Object> toJson() => {
        'daily': daily,
        'weekly': weekly,
        'monthly': monthly,
        'yearly': yearly,
        'email': email,
        'whatsapp': whatsapp,
      };

  ReportSettings copyWith({bool? daily, bool? weekly, bool? monthly, bool? yearly, bool? email, bool? whatsapp}) =>
      ReportSettings(
        daily: daily ?? this.daily,
        weekly: weekly ?? this.weekly,
        monthly: monthly ?? this.monthly,
        yearly: yearly ?? this.yearly,
        email: email ?? this.email,
        whatsapp: whatsapp ?? this.whatsapp,
      );
}

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

/// How many customers a time can take, and whether bookings confirm themselves while a place is free.
class BookingLimits {
  /// Null means one customer per active team member.
  final int? capacityOverride;
  final int capacity;
  final int activeStaff;
  final bool autoConfirm;

  const BookingLimits({
    required this.capacityOverride,
    required this.capacity,
    required this.activeStaff,
    required this.autoConfirm,
  });

  factory BookingLimits.fromSchedule(Map<String, dynamic> j) => BookingLimits(
        capacityOverride: j['capacity_override'] as int?,
        capacity: j['capacity'] as int? ?? 1,
        activeStaff: j['active_staff'] as int? ?? 0,
        autoConfirm: j['auto_confirm'] as bool? ?? false,
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

  Future<BookingLimits> bookingLimits(String shopId) => _call(() async {
        return BookingLimits.fromSchedule((await apiClient.get<Map<String, dynamic>>(ApiConstants.shopHours(shopId))).data!);
      });

  /// Null goes back to one customer per active team member.
  Future<void> saveCapacity(String shopId, int? capacity) => _call(() async {
        await apiClient.put<Map<String, dynamic>>('${ApiConstants.shop(shopId)}/capacity', data: {'capacity': capacity});
      });

  Future<void> saveAutoConfirm(String shopId, bool autoConfirm) => _call(() async {
        await apiClient.put<Map<String, dynamic>>('${ApiConstants.shop(shopId)}/auto-confirm', data: {'auto_confirm': autoConfirm});
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

  /// The free-fix guarantee in days (0 to 90), public on the shop.
  Future<void> saveGuaranteeDays(String shopId, int days) => _call(() async {
        await apiClient.put<Map<String, dynamic>>(ApiConstants.shop(shopId), data: {'guarantee_days': days});
      });

  /// The types of document already uploaded (PAN, GST, AADHAAR, UDYAM, BANK_PROOF or SHOP_PHOTO).
  Future<Set<String>> documentTypes(String shopId) => _call(() async {
        final data = (await apiClient.get<List<dynamic>>('${ApiConstants.shop(shopId)}/documents')).data!;
        return data.cast<Map<String, dynamic>>().map((d) => d['type'] as String).toSet();
      });

  /// The documents this shop's type of work asks for, beyond the PAN everyone gives.
  Future<List<ChecklistItem>> checklist(String shopId) => _call(() async {
        final data = (await apiClient.get<List<dynamic>>('${ApiConstants.shop(shopId)}/verification-checklist')).data!;
        return data.cast<Map<String, dynamic>>().map(ChecklistItem.fromJson).toList();
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

  // What customers see before booking

  Future<void> saveProfile(String shopId, {required String about, int? yearsExperience, required List<String> languages}) =>
      _call(() async {
        await apiClient.put<Map<String, dynamic>>(ApiConstants.shop(shopId), data: {
          'description': about,
          'years_experience': yearsExperience,
          'languages': languages,
        });
      });

  /// The raw image is the request body, as shop_service expects.
  Future<void> addWorkPhoto(String shopId, PickedDocument file) => _call(() async {
        await apiClient.post<Map<String, dynamic>>(
          '${ApiConstants.shop(shopId)}/photos',
          data: Stream<List<int>>.fromIterable([file.bytes]),
          options: Options(
            contentType: file.contentType,
            headers: {Headers.contentLengthHeader: file.bytes.length},
            sendTimeout: const Duration(minutes: 2),
          ),
        );
      });

  Future<void> deleteWorkPhoto(String shopId, String photoId) => _call(() async {
        await apiClient.delete<void>('${ApiConstants.shop(shopId)}/photos/$photoId');
      });

  // Days off, reviews and customers

  Future<List<DateTime>> daysOff(String shopId) => _call(() async {
        final data = (await apiClient.get<Map<String, dynamic>>(ApiConstants.shopHours(shopId))).data!;
        return ((data['holidays'] as List<dynamic>?) ?? const [])
            .cast<Map<String, dynamic>>()
            .map((h) => DateTime.parse(h['date'] as String))
            .toList()
          ..sort();
      });

  Future<void> addDayOff(String shopId, String day) => _call(() async {
        await apiClient.post<Map<String, dynamic>>('${ApiConstants.shop(shopId)}/holidays', data: {'date': day});
      });

  Future<void> removeDayOff(String shopId, String day) => _call(() async {
        await apiClient.delete<void>('${ApiConstants.shop(shopId)}/holidays/$day');
      });

  Future<void> replyToReview(String shopId, String reviewId, String text) => _call(() async {
        await apiClient.put<Map<String, dynamic>>('${ApiConstants.shop(shopId)}/reviews/$reviewId/reply', data: {'text': text});
      });

  Future<List<ShopCustomer>> customers(String shopId) => _call(() async {
        final data = (await apiClient.get<List<dynamic>>('${ApiConstants.bookings}/shop/$shopId/customers')).data!;
        return data.cast<Map<String, dynamic>>().map(ShopCustomer.fromJson).toList();
      });

  // Reports

  static String _money(String shopId) => '${ApiConstants.apiVersion}/payments/shops/$shopId';

  Future<ShopReport> report(String shopId, String period) => _call(() async {
        final data = (await apiClient.get<Map<String, dynamic>>('${_money(shopId)}/report',
                queryParameters: {'period': period}))
            .data!;
        return ShopReport.fromJson(data);
      });

  Future<List<CashEntry>> cashEntries(String shopId, String from, String to) => _call(() async {
        final data = (await apiClient.get<List<dynamic>>('${_money(shopId)}/cash-entries',
                queryParameters: {'from': from, 'to': to}))
            .data!;
        return data.cast<Map<String, dynamic>>().map(CashEntry.fromJson).toList();
      });

  Future<void> addCashEntry(String shopId, String kind, String category, double amount, {String? note}) =>
      _call(() async {
        await apiClient.post<Map<String, dynamic>>('${_money(shopId)}/cash-entries', data: {
          'kind': kind,
          'category': category,
          'amount': amount,
          if (note != null && note.isNotEmpty) 'note': note,
        });
      });

  Future<void> deleteCashEntry(String shopId, String entryId) => _call(() async {
        await apiClient.delete<void>('${_money(shopId)}/cash-entries/$entryId');
      });

  /// Where it went: 'app', and 'email' or 'whatsapp' when those really sent.
  Future<List<String>> sendReport(String shopId, String period) => _call(() async {
        final data = (await apiClient.post<Map<String, dynamic>>('${_money(shopId)}/report/send',
                queryParameters: {'period': period}))
            .data!;
        return (data['sent_to'] as List<dynamic>).cast<String>();
      });

  Future<ReportSettings> reportSettings(String shopId) => _call(() async {
        return ReportSettings.fromJson(
            (await apiClient.get<Map<String, dynamic>>('${_money(shopId)}/report-settings')).data!);
      });

  Future<void> saveReportSettings(String shopId, ReportSettings settings) => _call(() async {
        await apiClient.put<Map<String, dynamic>>('${_money(shopId)}/report-settings', data: settings.toJson());
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

  /// Starting work at the customer's takes their 4-digit [startCode].
  Future<void> setStatus(String bookingId, String status, {String? startCode}) => _call(() async {
        await apiClient.put<Map<String, dynamic>>(
          '${ApiConstants.bookings}/$bookingId/status',
          data: {'status': status, if (startCode != null) 'start_code': startCode},
        );
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
