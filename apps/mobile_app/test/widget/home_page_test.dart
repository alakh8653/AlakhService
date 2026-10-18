import 'package:alakh_service/core/network/api_client.dart';
import 'package:alakh_service/core/network/network_info.dart';
import 'package:alakh_service/core/network/token_store.dart';
import 'package:alakh_service/features/auth/domain/entities/user.dart';
import 'package:alakh_service/features/booking/data/datasources/booking_remote_datasource.dart';
import 'package:alakh_service/features/booking/data/repositories/booking_repository_impl.dart';
import 'package:alakh_service/features/home/presentation/pages/home_page.dart';
import 'package:alakh_service/features/notifications/data/notifications_api.dart';
import 'package:alakh_service/features/services/data/datasources/service_remote_datasource.dart';
import 'package:alakh_service/features/services/data/repositories/service_repository_impl.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../support/fake_adapter.dart';

class Online implements NetworkInfo {
  @override
  Future<bool> get isConnected async => true;
}

void main() {
  testWidgets('home shows the next booking and refreshes the unread badge after reading notifications', (tester) async {
    tester.view.physicalSize = const Size(1080, 2400);
    addTearDown(tester.view.reset);
    var unread = 3;
    final soon = DateTime.now().add(const Duration(days: 2)).toUtc().toIso8601String();
    final adapter = FakeAdapter((r) {
      if (r.path.endsWith('/count/unread')) return (status: 200, body: {'unread_count': unread});
      if (r.path.endsWith('/bookings')) {
        return (status: 200, body: {
          'items': [
            {'id': 'b1', 'customer_id': 'u1', 'service_id': 's1', 'status': 'CONFIRMED', 'scheduled_at': soon, 'total_amount': 30000, 'created_at': soon},
          ],
        });
      }
      return (status: 200, body: <Object>[]);
    });
    final client = ApiClient(dio: fakeDio(adapter), tokens: MemoryTokenStore());
    var opened = 0;
    var bookingsOpened = false;
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: HomePage(
          user: User(id: 'u1', name: 'Demo Customer', phone: '', role: 'customer', isVerified: true, createdAt: DateTime(2026)),
          onSearch: (_) {},
          onOpenNotifications: () async {
            opened++;
            unread = 0; // read them all
          },
          onOpenBookings: () => bookingsOpened = true,
          serviceRepository: ServiceRepositoryImpl(remoteDataSource: ServiceRemoteDataSourceImpl(apiClient: client), networkInfo: Online()),
          bookingRepository: BookingRepositoryImpl(remoteDataSource: BookingRemoteDataSourceImpl(apiClient: client), networkInfo: Online()),
          notificationsApi: NotificationsApi(client),
        ),
      ),
    ));
    await tester.pumpAndSettle();

    expect(find.text('Your next booking'), findsOneWidget);
    expect(find.text('Confirmed'), findsOneWidget);
    expect(find.byTooltip('Notifications, 3 unread'), findsOneWidget);

    await tester.tap(find.byTooltip('Notifications, 3 unread'));
    await tester.pumpAndSettle();
    expect(opened, 1);
    expect(find.byTooltip('Notifications'), findsOneWidget);

    await tester.tap(find.text('Your next booking'));
    expect(bookingsOpened, isTrue);
  });
}
