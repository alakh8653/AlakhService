import 'package:alakh_service/core/network/api_client.dart';
import 'package:alakh_service/core/network/token_store.dart';
import 'package:alakh_service/features/booking/data/availability_api.dart';
import 'package:alakh_service/features/booking/data/datasources/booking_remote_datasource.dart';
import 'package:alakh_service/features/booking/data/repositories/booking_repository_impl.dart';
import 'package:alakh_service/features/booking/data/waitlist_api.dart';
import 'package:alakh_service/features/booking/domain/usecases/cancel_booking_usecase.dart';
import 'package:alakh_service/features/booking/domain/usecases/create_booking_usecase.dart';
import 'package:alakh_service/features/booking/presentation/bloc/booking_bloc.dart';
import 'package:alakh_service/features/booking/presentation/pages/booking_page.dart';
import 'package:alakh_service/features/profile/data/address_api.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_test/flutter_test.dart';

import '../support/fake_adapter.dart';
import 'booking_page_test.dart' as booking_page show Online, now, server, withHours;

void main() {
  testWidgets('a fully booked day offers the waitlist, and says so once joined', (tester) async {
    // Today has times; tomorrow (19 Oct) is fully booked.
    final base = booking_page.server(
      availability: (date) => date == '2026-10-19'
          ? booking_page.withHours(status: 'FULLY_BOOKED')
          : booking_page.withHours(slots: {'15:00': '2026-10-18T09:30:00Z'}),
    );
    final adapter = FakeAdapter((r) => r.path.endsWith('/waitlist') ? (status: 201, body: {'id': 'w1'}) : base.handler(r));
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
          serviceName: 'Haircut',
          servicePrice: 300,
          addressApi: AddressApi(client),
          availabilityApi: AvailabilityApi(client),
          waitlistApi: WaitlistApi(client),
          clock: booking_page.now,
        ),
      ),
    ));
    await tester.pumpAndSettle();
    expect(find.text('Tell me if a time opens'), findsNothing); // today has times

    await tester.ensureVisible(find.text('Tomorrow'));
    await tester.tap(find.text('Tomorrow'));
    await tester.pumpAndSettle();
    await tester.ensureVisible(find.text('Tell me if a time opens'));
    await tester.tap(find.text('Tell me if a time opens'));
    await tester.pumpAndSettle();

    final sent = adapter.requests.singleWhere((r) => r.path.endsWith('/waitlist'));
    expect(sent.data, {'service_id': 's1', 'date': '2026-10-19'});
    expect(find.text("We'll tell you if a time opens up on this day."), findsOneWidget);
    expect(find.text('Tell me if a time opens'), findsNothing);
  });
}
