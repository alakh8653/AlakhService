// The app's own API code against a running backend (not mocks): every request it sends and every response it
// parses. Skipped unless LIVE_API is set, e.g.
//   LIVE_API=http://127.0.0.1:3000 LIVE_AUTH_LOG=<auth_service log, for one-time codes>
//   LIVE_MAKE_ADMIN="python stack.py make-admin {}" flutter test test/live_backend_test.dart
import 'dart:io';
import 'dart:math';
import 'dart:typed_data';

import 'package:alakh_service/core/network/api_client.dart';
import 'package:alakh_service/core/network/idempotency.dart';
import 'package:alakh_service/core/network/token_store.dart';
import 'package:alakh_service/features/auth/data/datasources/auth_remote_datasource.dart';
import 'package:alakh_service/features/booking/data/availability_api.dart';
import 'package:alakh_service/features/booking/data/booking_queue_api.dart';
import 'package:alakh_service/features/booking/data/coupon_api.dart';
import 'package:alakh_service/features/booking/data/datasources/booking_remote_datasource.dart';
import 'package:alakh_service/features/booking/data/dispute_api.dart';
import 'package:alakh_service/features/booking/data/rating_api.dart';
import 'package:alakh_service/features/booking/data/trust_api.dart';
import 'package:alakh_service/features/chat/data/chat_api.dart';
import 'package:alakh_service/features/legal/data/legal_api.dart';
import 'package:alakh_service/features/loyalty/data/loyalty_api.dart';
import 'package:alakh_service/features/notifications/data/notifications_api.dart';
import 'package:alakh_service/features/packages/data/packages_api.dart';
import 'package:alakh_service/features/payment/data/payment_api.dart';
import 'package:alakh_service/features/profile/data/address_api.dart';
import 'package:alakh_service/features/profile/data/data_export_api.dart';
import 'package:alakh_service/features/profile/data/profile_api.dart';
import 'package:alakh_service/features/reviews/data/reviews_api.dart';
import 'package:alakh_service/features/services/data/datasources/service_remote_datasource.dart';
import 'package:alakh_service/features/shop_line/data/shop_line_api.dart';
import 'package:alakh_service/features/shop_owner/data/shop_owner_api.dart';
import 'package:alakh_service/features/shops/data/saved_shops_api.dart';
import 'package:alakh_service/offline/offline_queue.dart';
import 'package:alakh_service/offline/sync_manager.dart';
import 'package:dio/dio.dart';
import 'package:dio/io.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

final _env = Platform.environment;
final _base = _env['LIVE_API'];
const _password = 'Live-Passw0rd!';

/// The real network, which a test can cut ([up] = false) to be offline.
class Cuttable implements HttpClientAdapter {
  final _real = IOHttpClientAdapter();
  bool up = true;

  @override
  Future<ResponseBody> fetch(RequestOptions options, Stream<Uint8List>? requestStream, Future<void>? cancelFuture) {
    if (!up) throw DioException.connectionError(requestOptions: options, reason: 'offline');
    return _real.fetch(options, requestStream, cancelFuture);
  }

  @override
  void close({bool force = false}) => _real.close(force: force);
}

ApiClient client(MemoryTokenStore tokens, [HttpClientAdapter? adapter]) => ApiClient(
      dio: Dio(BaseOptions(baseUrl: _base!, headers: {'Content-Type': 'application/json', 'Accept': 'application/json'}))
        ..httpClientAdapter = adapter ?? IOHttpClientAdapter(),
      tokens: tokens,
    );

String phone() => '9${List.generate(9, (_) => Random().nextInt(10)).join()}';

/// The newest one-time code auth_service logged (LOG_OTP_CODES, local stacks only).
Future<String> latestCode(int linesBefore) async {
  for (var i = 0; i < 50; i++) {
    final lines = File(_env['LIVE_AUTH_LOG']!).readAsLinesSync();
    final found = lines.skip(linesBefore).where((l) => l.contains('otp_code_for_local_testing')).toList();
    if (found.isNotEmpty) return RegExp(r'code=(\d+)').firstMatch(found.last)!.group(1)!;
    await Future<void>.delayed(const Duration(milliseconds: 200));
  }
  throw StateError('no one-time code was logged');
}

int logLines() => File(_env['LIVE_AUTH_LOG']!).readAsLinesSync().length;

/// Signs up by phone exactly as the app does (register, code by SMS, verify) and keeps the session.
Future<({AuthRemoteDataSourceImpl auth, MemoryTokenStore tokens, String id, String phone})> signUp(String name, String terms) async {
  final tokens = MemoryTokenStore();
  final auth = AuthRemoteDataSourceImpl(apiClient: client(tokens));
  final number = phone();
  final before = logLines();
  await auth.register(name: name, phone: number, password: _password, acceptedTermsVersion: terms);
  await auth.sendCode(identifier: number, purpose: 'registration');
  final session = await auth.verifyCode(identifier: number, code: await latestCode(before), purpose: 'registration');
  await tokens.save(accessToken: session['access_token'] as String, refreshToken: session['refresh_token'] as String);
  final me = await auth.currentUser();
  return (auth: auth, tokens: tokens, id: me.id, phone: number);
}

void main() {
  test('the app, end to end against the live backend', () async {
    SharedPreferences.setMockInitialValues({});
    final noAuth = client(MemoryTokenStore());
    final legal = await LegalApi(noAuth).current();
    expect(legal.termsVersion, isNotEmpty);

    // A shop owner signs up in the app and opens a shop with a service.
    final owner = await signUp('Live Owner', legal.termsVersion);
    final ownerApi = ShopOwnerApi(client(owner.tokens));
    final shop = await ownerApi.createShop(
        ownerId: owner.id, name: 'Live Salon', category: 'salon', city: 'Pune', address: '7 MG Road', latitude: 18.52, longitude: 73.85);
    final service = await ownerApi.addService(shopId: shop.id, name: 'Haircut', priceCents: 30000, durationMinutes: 30, modes: ['AT_SHOP']);
    await ownerApi.ensureOwnerIsStaff(shop.id, owner.id, 'Live Owner', phone: owner.phone);
    // Open every day, 8 AM to 10 PM, so the times below are bookable whatever day this runs.
    await ownerApi.saveHours(shop.id, const WeekHours(days: {0, 1, 2, 3, 4, 5, 6}, opens: 480, closes: 1320));
    expect((await ownerApi.hours(shop.id)).opens, 480);

    // An admin approves it (make-admin is a command line step).
    final adminEmail = 'live-admin-${newIdempotencyKey(length: 8)}@example.com';
    await noAuth.post<dynamic>('/api/v1/auth/register',
        data: {'email': adminEmail, 'password': _password, 'full_name': 'Live Admin', 'accepted_terms_version': legal.termsVersion});
    final cmd = _env['LIVE_MAKE_ADMIN']!.replaceAll('{}', adminEmail).split(' ');
    expect((await Process.run(cmd.first, cmd.skip(1).toList())).exitCode, 0);
    final adminTokens = MemoryTokenStore();
    final adminLogin = await AuthRemoteDataSourceImpl(apiClient: client(adminTokens)).login(identifier: adminEmail, password: _password);
    await adminTokens.save(accessToken: adminLogin.accessToken, refreshToken: adminLogin.refreshToken);
    final admin = client(adminTokens);
    await admin.post<dynamic>('/api/v1/admin/shops/${shop.id}/approve');
    final coupon = 'LIVE${newIdempotencyKey(length: 6).toUpperCase()}';
    await admin.post<dynamic>('/api/v1/coupons', data: {'code': coupon, 'discount_pct': 0.1, 'max_uses': 10});

    // A customer signs up in the app and finds the service.
    final me = await signUp('Live Customer', legal.termsVersion);
    final api = client(me.tokens);
    final reviews = ReviewsApi(api);
    final catalogue = ServiceRemoteDataSourceImpl(apiClient: api, ratings: reviews);
    // An approved shop's services become searchable a moment later (shop_service tells the catalogue).
    var found = await catalogue.searchServices(query: 'Haircut');
    for (var i = 0; i < 20 && !found.any((s) => s.id == service.id); i++) {
      await Future<void>.delayed(const Duration(milliseconds: 500));
      found = await catalogue.searchServices(query: 'Haircut');
    }
    expect(found.map((s) => s.id), contains(service.id));
    final listed = await catalogue.getServiceById(service.id);
    expect((listed.name, listed.shopId), ('Haircut', shop.id));

    // Picks a time the shop has free and books it, as the booking screen does.
    final day = DateTime.now().add(const Duration(days: 2));
    final free = await AvailabilityApi(api).forDay(service.id, day);
    expect(free.slots, isNotEmpty, reason: 'the shop has free times on ${day.toIso8601String()}');
    final bookings = BookingRemoteDataSourceImpl(apiClient: api, services: catalogue);
    final key = newIdempotencyKey();
    final booking = await bookings.createBooking(
        serviceId: service.id, scheduledAt: free.slots.first.at, address: '', idempotencyKey: key, couponCode: coupon);
    final again = await bookings.createBooking(
        serviceId: service.id, scheduledAt: free.slots.first.at, address: '', idempotencyKey: key, couponCode: coupon);
    expect(again.id, booking.id, reason: 'a retried booking is not booked twice');
    expect(booking.totalAmount, lessThan(300), reason: 'the 10% coupon applied (₹${booking.totalAmount})');
    expect((await bookings.getUserBookings()).map((b) => b.id), contains(booking.id));
    expect((await CouponApi(api).check(coupon)).isValid, isTrue);

    // The shop confirms; the customer pays cash.
    final line = ShopLineApi(client(owner.tokens));
    await client(owner.tokens).put<dynamic>('/api/v1/bookings/${booking.id}/status', data: {'status': 'CONFIRMED'});
    final payment = await PaymentApi(api).payForBooking(bookingId: booking.id, method: 'cash', idempotencyKey: PaymentApi.newIdempotencyKey());

    // Chat with the offline queue: one message online, then the phone loses its connection.
    final net = Cuttable();
    final offlineApi = client(me.tokens, net);
    final sync = SyncManager(queue: OfflineQueue(await SharedPreferences.getInstance()), dio: offlineApi.dio);
    final chat = ChatApi(offlineApi, offline: sync);
    expect((await chat.send(booking.id, 'Hi, is parking free?'))?.id, isNotNull);
    net.up = false;
    expect(await chat.send(booking.id, 'Running 5 min late'), isNull, reason: 'kept for later');
    expect(chat.pending(booking.id), hasLength(1));
    net.up = true;
    await sync.sync();
    expect(chat.pending(booking.id), isEmpty);
    final thread = await ChatApi(client(owner.tokens)).messages(booking.id);
    expect(thread.items.map((m) => m.body), ['Hi, is parking free?', 'Running 5 min late'],
        reason: 'the shop sees both, once each, in order');

    // Saved shops and read marks, made offline and sent later.
    final saved = SavedShopsApi(offlineApi, offline: sync);
    net.up = false;
    await saved.save(shop.id);
    net.up = true;
    await sync.sync();
    expect((await SavedShopsApi(api).list()).map((s) => s.id), contains(shop.id));
    final notifications = NotificationsApi(offlineApi, offline: sync);
    expect(await notifications.list(), isNotEmpty, reason: 'told of the confirmed booking');
    await notifications.markAllRead();
    expect(await notifications.unreadCount(), 0);
    await sync.dispose();

    // The visit: started and finished by the shop, then rated and paid.
    await line.start(booking.id);
    await line.finish(booking.id);
    expect((await bookings.getBookingById(booking.id)).status.toUpperCase(), 'COMPLETED');
    await client(owner.tokens).post<dynamic>('/api/v1/payments/${payment.id}/cash-received');
    expect(await PaymentApi(api).invoiceHtml(payment.id), contains('Live Salon'));
    await RatingApi(api).rate(shopId: shop.id, bookingId: booking.id, rating: 5, comment: 'Great cut');
    final summary = await reviews.summary(shop.id);
    expect((summary.count, summary.average), (1, 5.0));
    expect((await reviews.reviews(shop.id)).items.single.comment, 'Great cut');
    expect((await TrustApi(api).share(booking.id)).url, startsWith('http'));
    expect((await LoyaltyApi(api).summary()).points, greaterThan(0), reason: 'points for a completed booking');

    // Joining the line on the day, and the shop calling them in.
    final wait = await BookingQueueApi(api).waitNow(service.id);
    expect(wait, isNotNull);
    final walkIn = await BookingQueueApi(api).joinLine(service.id);
    expect(walkIn.bookingId, isNotEmpty);
    expect((await line.line(shop.id)).map((e) => e.bookingId), contains(walkIn.bookingId));
    expect((await line.callNext(shop.id)).bookingId, walkIn.bookingId);

    // A booking moved, then cancelled; another one disputed.
    final later = await AvailabilityApi(api).forDay(service.id, day.add(const Duration(days: 1)));
    final second = await bookings.createBooking(serviceId: service.id, scheduledAt: later.slots.first.at, address: '');
    final moved = await bookings.rescheduleBooking(second.id, later.slots.last.at);
    expect(moved.scheduledAt.toUtc(), later.slots.last.at.toUtc());
    expect(await bookings.cancelBooking(second.id), isTrue);
    await DisputeApi(api).report(bookingId: booking.id, type: 'service_quality', description: 'Uneven at the back');
    expect((await bookings.getBookingById(booking.id)).status.toUpperCase(), 'DISPUTED');

    // The customer's own details.
    final profile = ProfileApi(api);
    expect(await profile.get(), isNull, reason: 'nothing saved yet');
    expect((await profile.update(fullName: 'Asha Live', bio: 'Regular')).fullName, 'Asha Live');
    final addresses = AddressApi(api);
    final home = await addresses.add(label: 'Home', street: '4 Lane', city: 'Pune', state: 'MH', postalCode: '411001');
    await addresses.makeDefault(home.id);
    expect((await addresses.list()).single.isDefault, isTrue);
    expect((await DataExportApi(api).request(me.id)).status, isNotEmpty);
    expect(await PackagesApi(api).mine(), isEmpty);

    // Signing out ends the session for good.
    final refresh = await me.tokens.refreshToken();
    await me.auth.logout(refresh!);
    await expectLater(bookings.getUserBookings(), throwsA(anything));
  }, skip: _base == null ? 'set LIVE_API to run against a live backend' : false, timeout: const Timeout(Duration(minutes: 3)));
}
