import 'package:alakh_service/core/constants/api_constants.dart';
import 'package:alakh_service/core/network/api_client.dart';
import 'package:alakh_service/core/network/token_store.dart';
import 'package:alakh_service/features/booking/domain/entities/booking.dart';
import 'package:alakh_service/features/jobs/data/jobs_api.dart';
import 'package:alakh_service/features/jobs/data/location_reporter.dart';
import 'package:alakh_service/features/tracking/data/tracking_api.dart';
import 'package:flutter_test/flutter_test.dart';

import '../support/fake_adapter.dart';

Map<String, dynamic> job(String id, String status) => {
      'id': id,
      'booking_number': 'BK-$id',
      'customer_id': 'c1',
      'provider_id': 'p1',
      'service_id': 's1',
      'shop_id': 'shop1',
      'status': status,
      'scheduled_at': '2026-10-12T05:30:00Z',
      'duration_minutes': 45,
      'total_amount': 49900,
      'notes': 'Address: 12 MG Road',
      'created_at': '2026-10-11T05:30:00Z',
    };

class FakeSource implements LocationSource {
  Fix? fix;
  FakeSource(this.fix);

  @override
  Future<Fix?> current() async => fix;
}

void main() {
  test('each job status has one next step for the provider', () {
    expect(JobStep.after(BookingStatus.assigned)!.status, BookingStatus.enRoute);
    expect(JobStep.after(BookingStatus.enRoute)!.status, BookingStatus.inProgress);
    expect(JobStep.after(BookingStatus.inProgress)!.label, 'Complete job');
    expect(JobStep.after(BookingStatus.completed), isNull);
    expect(JobStep.after(BookingStatus.confirmed), isNull);
  });

  test('jobs come from the assigned list and move via the status endpoint', () async {
    final adapter = FakeAdapter((r) => r.method == 'PUT'
        ? (status: 200, body: job('1', r.data['status'] as String))
        : (status: 200, body: {'items': [job('1', 'ASSIGNED')], 'total': 1}));
    final api = JobsApi(ApiClient(dio: fakeDio(adapter), tokens: MemoryTokenStore()));

    final jobs = await api.list();
    expect(adapter.requests.first.path, ApiConstants.assignedBookings);
    expect((jobs.single.status, jobs.single.address), ('ASSIGNED', '12 MG Road'));
    expect(await api.hasJobs(), isTrue);

    final moved = await api.moveTo('1', BookingStatus.enRoute);
    expect(adapter.requests.last.path, '/api/v1/bookings/1/status');
    expect(moved.status, BookingStatus.enRoute);
  });

  test('a provider without jobs, or offline, gets no Jobs tab', () async {
    final none = JobsApi(ApiClient(
      dio: fakeDio(FakeAdapter((_) => (status: 200, body: {'items': [], 'total': 0}))),
      tokens: MemoryTokenStore(),
    ));
    expect(await none.hasJobs(), isFalse);
    final down = JobsApi(ApiClient(dio: fakeDio(FakeAdapter((_) => (status: 503, body: {}))), tokens: MemoryTokenStore()));
    expect(await down.hasJobs(), isFalse);
  });

  test('the reporter sends the device position as the provider, and says when it cannot', () async {
    final adapter = FakeAdapter((_) => (status: 201, body: {}));
    final states = <SharingState>[];
    final source = FakeSource(const Fix(18.52, 73.85, accuracy: 8, speed: 4.2));
    final reporter = LocationReporter(
      tracking: TrackingApi(ApiClient(dio: fakeDio(adapter), tokens: MemoryTokenStore())),
      source: source,
      providerId: 'p1',
      onState: states.add,
    );

    await reporter.reportNow();
    expect(adapter.requests.single.path, ApiConstants.locations);
    expect(adapter.requests.single.data, {'provider_id': 'p1', 'latitude': 18.52, 'longitude': 73.85, 'accuracy': 8.0, 'speed': 4.2});

    source.fix = null;
    await reporter.reportNow();
    expect(adapter.requests, hasLength(1));
    expect(states, [SharingState.sharing, SharingState.noPermission]);
  });
}
