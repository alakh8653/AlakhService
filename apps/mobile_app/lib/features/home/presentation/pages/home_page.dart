import 'package:flutter/material.dart';

import '../../../../core/di/injection_container.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_text_styles.dart';
import '../../../../shared/utils/format.dart';
import '../../../../shared/widgets/service_card.dart';
import '../../../auth/domain/entities/user.dart';
import '../../../booking/domain/entities/booking.dart';
import '../../../booking/domain/repositories/booking_repository.dart';
import '../../../booking/presentation/pages/booking_history_page.dart';
import '../../../notifications/data/notifications_api.dart';
import '../../../services/domain/entities/service_entity.dart';
import '../../../services/domain/repositories/service_repository.dart';
import '../../../services/presentation/pages/service_detail_page.dart';
import 'home_widgets.dart';

class HomePage extends StatefulWidget {
  final User user;
  final ValueChanged<String> onSearch;

  /// Opens the notifications; the unread badge is refreshed when it completes.
  final Future<void> Function() onOpenNotifications;
  final VoidCallback onOpenBookings;
  final ServiceRepository? serviceRepository;
  final BookingRepository? bookingRepository;
  final NotificationsApi? notificationsApi;

  const HomePage({
    super.key,
    required this.user,
    required this.onSearch,
    required this.onOpenNotifications,
    required this.onOpenBookings,
    this.serviceRepository,
    this.bookingRepository,
    this.notificationsApi,
  });

  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  // Everyday needs: visits (salon, parlour, doctor, offices), repairs with pickup & drop, and home services.
  static const List<_ServiceCategory> _categories = [
    _ServiceCategory(icon: Icons.content_cut, label: 'Haircut'),
    _ServiceCategory(icon: Icons.face_retouching_natural, label: 'Beauty Parlour', query: 'Beauty'),
    _ServiceCategory(icon: Icons.medical_services, label: 'Doctor'),
    _ServiceCategory(icon: Icons.event_available, label: 'Appointments', query: 'Appointment'),
    _ServiceCategory(icon: Icons.car_repair, label: 'Car Repair', query: 'Car'),
    _ServiceCategory(icon: Icons.two_wheeler, label: 'Bike Repair', query: 'Bike'),
    _ServiceCategory(icon: Icons.devices, label: 'Laptop & Phone', query: 'Repair'),
    _ServiceCategory(icon: Icons.ac_unit, label: 'AC Repair', query: 'AC'),
    _ServiceCategory(icon: Icons.cleaning_services, label: 'Cleaning'),
    _ServiceCategory(icon: Icons.plumbing, label: 'Plumbing'),
    _ServiceCategory(icon: Icons.electrical_services, label: 'Electrical'),
    _ServiceCategory(icon: Icons.carpenter, label: 'Carpentry'),
    _ServiceCategory(icon: Icons.pest_control, label: 'Pest Control'),
    _ServiceCategory(icon: Icons.handyman, label: 'Handyman'),
  ];

  late Future<List<ServiceEntity>> _popular;
  // The customer's soonest booking that is still ahead or under way, if any.
  Booking? _next;
  int _unread = 0;

  NotificationsApi get _notifications => widget.notificationsApi ?? sl<NotificationsApi>();

  @override
  void initState() {
    super.initState();
    _popular = _loadPopular();
    _loadNext();
    _loadUnread();
  }

  Future<void> _loadUnread() async {
    try {
      final n = await _notifications.unreadCount();
      if (mounted) setState(() => _unread = n);
    } catch (_) {
      // The badge is a hint; the notifications screen shows the real list.
    }
  }

  Future<void> _loadNext() async {
    final result = await (widget.bookingRepository ?? sl<BookingRepository>()).getUserBookings();
    final now = DateTime.now();
    // Skip ones whose time went by unconfirmed: "Your next booking: Yesterday" would mislead.
    final upcoming = result
        .fold((_) => const <Booking>[], (bookings) => splitBookings(bookings).$1)
        .where((b) => !b.isOverdue(now))
        .toList();
    if (mounted) setState(() => _next = upcoming.isEmpty ? null : upcoming.first);
  }

  Future<List<ServiceEntity>> _loadPopular() async {
    final result = await (widget.serviceRepository ?? sl<ServiceRepository>()).getServices(limit: 5);
    return result.fold((failure) => throw failure.message, (services) => services);
  }

  Future<void> _refresh() async {
    final popular = _loadPopular();
    setState(() => _popular = popular);
    await Future.wait<void>([popular.then((_) {}, onError: (_) {}), _loadNext(), _loadUnread()]);
  }

  Future<void> _openNotifications() async {
    await widget.onOpenNotifications();
    await _loadUnread();
  }

  String get _greeting {
    final hour = DateTime.now().hour;
    if (hour < 12) return 'Good morning';
    if (hour < 17) return 'Good afternoon';
    return 'Good evening';
  }

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: RefreshIndicator(
        onRefresh: _refresh,
        child: SingleChildScrollView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.symmetric(vertical: 16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _buildHeader(),
              const SizedBox(height: 16),
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16),
                child: SearchBarWidget(onSubmitted: widget.onSearch, hint: 'Search haircut, AC repair, doctor…'),
              ),
              const SizedBox(height: 20),
              if (_next != null)
                NextBookingCard(
                  serviceName: _next!.serviceName,
                  when: friendlyDateTime(_next!.scheduledAt),
                  status: bookingStatusLabel(_next!.status),
                  onTap: widget.onOpenBookings,
                )
              else
                BannerWidget(onTap: widget.onOpenBookings),
              const SizedBox(height: 24),
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16),
                child: Semantics(header: true, child: const Text('Our Services', style: AppTextStyles.heading3)),
              ),
              const SizedBox(height: 16),
              _buildCategoriesGrid(),
              const SizedBox(height: 24),
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16),
                child: Semantics(header: true, child: const Text('Popular Services', style: AppTextStyles.heading3)),
              ),
              const SizedBox(height: 12),
              _buildPopular(),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildHeader() {
    final firstName = widget.user.name.split(' ').first;
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('$_greeting${firstName.isEmpty ? '' : ', $firstName'} 👋', style: AppTextStyles.body2),
                const Text('Find a Service', style: AppTextStyles.heading2),
              ],
            ),
          ),
          IconButton(
            tooltip: _unread > 0 ? 'Notifications, $_unread unread' : 'Notifications',
            onPressed: _openNotifications,
            icon: Badge(
              isLabelVisible: _unread > 0,
              label: Text(_unread > 99 ? '99+' : '$_unread'),
              child: const Icon(Icons.notifications_outlined, color: AppColors.textPrimary),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildCategoriesGrid() {
    return LayoutBuilder(
      builder: (context, constraints) {
        // Four across on phones; large system text gets three so labels stay readable.
        final scale = MediaQuery.textScalerOf(context).scale(1);
        final columns = scale > 1.15 ? 3 : 4;
        return GridView.builder(
          padding: const EdgeInsets.symmetric(horizontal: 16),
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
            crossAxisCount: columns,
            mainAxisSpacing: 12,
            crossAxisSpacing: 8,
            mainAxisExtent: 88 + 18 * scale,
          ),
          itemCount: _categories.length,
          itemBuilder: (context, index) {
            final cat = _categories[index];
            return ServiceCategoryCard(icon: cat.icon, label: cat.label, onTap: () => widget.onSearch(cat.query ?? cat.label));
          },
        );
      },
    );
  }

  Widget _buildPopular() {
    return FutureBuilder<List<ServiceEntity>>(
      future: _popular,
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done) {
          return const Padding(
            padding: EdgeInsets.all(24),
            child: Center(child: CircularProgressIndicator()),
          );
        }
        final services = snapshot.data ?? const [];
        if (snapshot.hasError || services.isEmpty) {
          return Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: Row(
              children: [
                Expanded(
                  child: Text(
                    snapshot.hasError ? 'Could not load services.' : 'No services listed yet.',
                    style: AppTextStyles.body2,
                  ),
                ),
                if (snapshot.hasError) TextButton(onPressed: _refresh, child: const Text('Try again')),
              ],
            ),
          );
        }
        return ListView.separated(
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          padding: const EdgeInsets.symmetric(horizontal: 16),
          itemCount: services.length,
          separatorBuilder: (_, __) => const SizedBox(height: 12),
          itemBuilder: (context, i) => ServiceCard(
            service: services[i],
            onTap: () => Navigator.push(
              context,
              MaterialPageRoute(builder: (_) => ServiceDetailPage(service: services[i])),
            ),
          ),
        );
      },
    );
  }
}

class _ServiceCategory {
  final IconData icon;
  final String label;

  /// What tapping it searches for (defaults to the label).
  final String? query;

  const _ServiceCategory({required this.icon, required this.label, this.query});
}
