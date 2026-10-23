import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../../../core/di/injection_container.dart';
import '../../../core/network/api_errors.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/theme/app_text_styles.dart';
import '../../booking/domain/entities/booking.dart';
import '../../tracking/data/tracking_api.dart';
import '../data/jobs_api.dart';
import '../../../shared/widgets/location_rationale.dart';
import '../data/location_reporter.dart';

/// A provider's assigned jobs: move each one along, and share location while one is under way.
class JobsPage extends StatefulWidget {
  final String providerId;
  final JobsApi? jobsApi;
  final LocationReporter? reporter;

  const JobsPage({super.key, required this.providerId, this.jobsApi, this.reporter});

  @override
  State<JobsPage> createState() => _JobsPageState();
}

class _JobsPageState extends State<JobsPage> {
  late final JobsApi _api = widget.jobsApi ?? sl<JobsApi>();
  late final LocationReporter _reporter = widget.reporter ??
      LocationReporter(
        tracking: sl<TrackingApi>(),
        source: DeviceLocationSource(purpose: LocationPurpose.sharing),
        providerId: widget.providerId,
        onState: _onSharing,
      );
  List<Booking>? _jobs;
  String? _error;
  String? _busyId;
  SharingState _sharing = SharingState.off;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _reporter.stop();
    super.dispose();
  }

  void _onSharing(SharingState state) {
    if (mounted) setState(() => _sharing = state);
  }

  void _updateSharing() {
    final underWay = _jobs?.any((j) => JobsApi.sharingStatuses.contains(j.status)) ?? false;
    if (underWay && !_reporter.isRunning) _reporter.start();
    if (!underWay && _reporter.isRunning) _reporter.stop();
  }

  Future<void> _load() async {
    try {
      final jobs = await _api.list();
      jobs.sort((a, b) => a.scheduledAt.compareTo(b.scheduledAt));
      if (!mounted) return;
      setState(() {
        _jobs = jobs;
        _error = null;
      });
      _updateSharing();
    } catch (e) {
      if (mounted) setState(() => _error = apiErrorMessage(e));
    }
  }

  Future<void> _advance(Booking job, JobStep step) async {
    setState(() => _busyId = job.id);
    try {
      final updated = await _api.moveTo(job.id, step.status);
      if (!mounted) return;
      setState(() => _jobs = [for (final j in _jobs!) j.id == job.id ? updated : j]);
      _updateSharing();
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(apiErrorMessage(e)), backgroundColor: AppColors.error),
        );
      }
    } finally {
      if (mounted) setState(() => _busyId = null);
    }
  }

  @override
  Widget build(BuildContext context) {
    final jobs = _jobs;
    final active = jobs?.where((j) => JobStep.after(j.status) != null).toList() ?? [];
    final earlier = jobs?.where((j) => JobStep.after(j.status) == null).toList().reversed.toList() ?? [];
    return Scaffold(
      appBar: AppBar(title: const Text('My Jobs')),
      body: RefreshIndicator(
        onRefresh: _load,
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            if (_reporter.isRunning) _SharingBanner(state: _sharing),
            if (jobs == null && _error == null) const Padding(
              padding: EdgeInsets.only(top: 120),
              child: Center(child: CircularProgressIndicator()),
            ),
            if (_error != null) Padding(
              padding: const EdgeInsets.only(top: 80),
              child: Text(_error!, textAlign: TextAlign.center, style: AppTextStyles.subtitle1),
            ),
            if (jobs != null && jobs.isEmpty) const Padding(
              padding: EdgeInsets.only(top: 120),
              child: Text('No jobs assigned to you yet.', textAlign: TextAlign.center, style: AppTextStyles.subtitle1),
            ),
            if (active.isNotEmpty) ...[
              const Text('Current', style: AppTextStyles.subtitle1),
              const SizedBox(height: 8),
              for (final job in active)
                _JobCard(job: job, busy: _busyId == job.id, onAdvance: (step) => _advance(job, step)),
            ],
            if (earlier.isNotEmpty) ...[
              const SizedBox(height: 16),
              const Text('Earlier', style: AppTextStyles.subtitle1),
              const SizedBox(height: 8),
              for (final job in earlier) _JobCard(job: job, busy: false, onAdvance: (_) {}),
            ],
          ],
        ),
      ),
    );
  }
}

class _SharingBanner extends StatelessWidget {
  final SharingState state;

  const _SharingBanner({required this.state});

  @override
  Widget build(BuildContext context) {
    final (text, color) = switch (state) {
      SharingState.noPermission => ('Allow location access so your customer can see you are on the way.', context.colors.error),
      SharingState.failing => ('Could not share your location. Retrying…', context.colors.error),
      _ => ('Sharing your location with your customer while this job is under way.', context.colors.primary),
    };
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(color: color.withValues(alpha: 0.1), borderRadius: BorderRadius.circular(12)),
      child: Row(children: [
        Icon(Icons.my_location, color: color, size: 20),
        const SizedBox(width: 8),
        Expanded(child: Text(text, style: AppTextStyles.caption.copyWith(color: color))),
      ]),
    );
  }
}

class _JobCard extends StatelessWidget {
  final Booking job;
  final bool busy;
  final ValueChanged<JobStep> onAdvance;

  const _JobCard({required this.job, required this.busy, required this.onAdvance});

  static const _labels = {
    BookingStatus.pending: 'Awaiting confirmation',
    BookingStatus.confirmed: 'Confirmed',
    BookingStatus.assigned: 'Assigned to you',
    BookingStatus.enRoute: 'On the way',
    BookingStatus.inProgress: 'In progress',
    BookingStatus.completed: 'Completed',
    BookingStatus.cancelled: 'Cancelled',
    BookingStatus.disputed: 'Disputed',
    BookingStatus.refunded: 'Refunded',
  };

  @override
  Widget build(BuildContext context) {
    final step = JobStep.after(job.status);
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(children: [
              Expanded(child: Text(job.serviceName, style: AppTextStyles.subtitle1)),
              Text(_labels[job.status] ?? job.status, style: AppTextStyles.caption.themed(context)),
            ]),
            const SizedBox(height: 4),
            Text(
              '${DateFormat('EEE d MMM, h:mm a').format(job.scheduledAt)}'
              '${job.bookingNumber.isEmpty ? '' : ' · ${job.bookingNumber}'}',
              style: AppTextStyles.body2.themed(context),
            ),
            if (job.address.isNotEmpty) ...[
              const SizedBox(height: 4),
              Row(children: [
                Icon(Icons.place_outlined, size: 16, color: context.palette.muted),
                const SizedBox(width: 4),
                Expanded(child: Text(job.address, style: AppTextStyles.body2.themed(context))),
              ]),
            ],
            if (job.notes != null) ...[
              const SizedBox(height: 4),
              Text(job.notes!, style: AppTextStyles.caption.themed(context)),
            ],
            if (step != null) ...[
              const SizedBox(height: 12),
              SizedBox(
                width: double.infinity,
                child: FilledButton(
                  onPressed: busy ? null : () => onAdvance(step),
                  child: busy
                      ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2))
                      : Text(step.label),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
