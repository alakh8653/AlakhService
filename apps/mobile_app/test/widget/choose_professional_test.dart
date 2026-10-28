import 'package:alakh_service/core/network/api_client.dart';
import 'package:alakh_service/core/network/token_store.dart';
import 'package:alakh_service/features/booking/data/availability_api.dart';
import 'package:alakh_service/features/booking/data/datasources/booking_remote_datasource.dart';
import 'package:alakh_service/features/booking/data/repositories/booking_repository_impl.dart';
import 'package:alakh_service/features/booking/domain/usecases/cancel_booking_usecase.dart';
import 'package:alakh_service/features/booking/domain/usecases/create_booking_usecase.dart';
import 'package:alakh_service/features/booking/presentation/bloc/booking_bloc.dart';
import 'package:alakh_service/features/booking/presentation/pages/booking_page.dart';
import 'package:alakh_service/features/profile/data/address_api.dart';
import 'package:alakh_service/features/shops/data/team_api.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_test/flutter_test.dart';

import '../support/fake_adapter.dart';
import 'booking_page_test.dart' as booking_page show Online, now, pickDateAndTime, server;

void main() {
  testWidgets('the customer picks who does it, from those who do this service', (tester) async {
    final base = booking_page.server();
    final adapter = FakeAdapter((r) => r.path.endsWith('/team')
        ? (status: 200, body: [
            {'id': 'st-meena', 'name': 'Meena R.', 'role': 'stylist', 'service_ids': ['s1']},
            {'id': 'st-ravi', 'name': 'Ravi', 'role': 'barber', 'service_ids': ['other']},
            {'id': 'st-asha', 'name': 'Asha', 'role': 'stylist', 'service_ids': <String>[]},
          ])
        : base.handler(r));
    final client = ApiClient(dio: fakeDio(adapter), tokens: MemoryTokenStore());
    final repo = BookingRepositoryImpl(remoteDataSource: BookingRemoteDataSourceImpl(apiClient: client), networkInfo: booking_page.Online());
    await tester.pumpWidget(MaterialApp(
      home: BlocProvider(
        create: (_) => BookingBloc(
          createBookingUseCase: CreateBookingUseCase(repo),
          cancelBookingUseCase: CancelBookingUseCase(repo),
          bookingRepository: repo,
        ),
        child: BookingPage(
          serviceId: 's1',
          shopId: 'shop-1',
          serviceName: 'Haircut',
          servicePrice: 300,
          addressApi: AddressApi(client),
          availabilityApi: AvailabilityApi(client),
          teamApi: TeamApi(client),
          clock: booking_page.now,
        ),
      ),
    ));
    await tester.pumpAndSettle();

    expect(find.text('Who would you like?'), findsOneWidget);
    expect(find.text('Anyone'), findsOneWidget);
    expect(find.text('Meena R.'), findsOneWidget);
    expect(find.text('Asha'), findsOneWidget);
    expect(find.text('Ravi'), findsNothing); // does not do this service

    await tester.tap(find.text('Meena R.'));
    await tester.pumpAndSettle();
    await booking_page.pickDateAndTime(tester);
    await tester.tap(find.text('Confirm Booking'));
    await tester.pumpAndSettle();
    final sent = adapter.requests.singleWhere((r) => r.method == 'POST' && r.path.endsWith('/bookings'));
    expect((sent.data as Map)['preferred_staff_id'], 'st-meena');
  });
}
