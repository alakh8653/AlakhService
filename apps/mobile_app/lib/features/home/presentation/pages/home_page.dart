import 'package:flutter/material.dart';

import '../../../../core/di/injection_container.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_text_styles.dart';
import '../../../../shared/widgets/service_card.dart';
import '../../../auth/domain/entities/user.dart';
import '../../../notifications/data/notifications_api.dart';
import '../../../services/domain/entities/service_entity.dart';
import '../../../services/domain/repositories/service_repository.dart';
import '../../../services/presentation/pages/service_detail_page.dart';
import 'home_widgets.dart';

class HomePage extends StatefulWidget {
  final User user;
  final ValueChanged<String> onSearch;
  final VoidCallback onOpenNotifications;
  final VoidCallback onOpenBookings;

  const HomePage({
    super.key,
    required this.user,
    required this.onSearch,
    required this.onOpenNotifications,
    required this.onOpenBookings,
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
  int _unread = 0;

  @override
  void initState() {
    super.initState();
    _popular = _loadPopular();
    sl<NotificationsApi>().unreadCount().then((n) {
      if (mounted) setState(() => _unread = n);
    }).catchError((_) {});
  }

  Future<List<ServiceEntity>> _loadPopular() async {
    final result = await sl<ServiceRepository>().getServices(limit: 5);
    return result.fold((failure) => throw failure.message, (services) => services);
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
        onRefresh: () async => setState(() => _popular = _loadPopular()),
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
                child: SearchBarWidget(onSubmitted: widget.onSearch),
              ),
              const SizedBox(height: 20),
              BannerWidget(onTap: widget.onOpenBookings),
              const SizedBox(height: 24),
              const Padding(
                padding: EdgeInsets.symmetric(horizontal: 16),
                child: Text('Our Services', style: AppTextStyles.heading3),
              ),
              const SizedBox(height: 16),
              _buildCategoriesGrid(),
              const SizedBox(height: 24),
              const Padding(
                padding: EdgeInsets.symmetric(horizontal: 16),
                child: Text('Popular Services', style: AppTextStyles.heading3),
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
            tooltip: 'Notifications',
            onPressed: () {
              widget.onOpenNotifications();
              setState(() => _unread = 0);
            },
            icon: Badge(
              isLabelVisible: _unread > 0,
              label: Text('$_unread'),
              child: const Icon(Icons.notifications_outlined, color: AppColors.textPrimary),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildCategoriesGrid() {
    return GridView.builder(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
        crossAxisCount: 4,
        mainAxisSpacing: 16,
        crossAxisSpacing: 16,
        childAspectRatio: 0.85,
      ),
      itemCount: _categories.length,
      itemBuilder: (context, index) {
        final cat = _categories[index];
        return ServiceCategoryCard(icon: cat.icon, label: cat.label, onTap: () => widget.onSearch(cat.query ?? cat.label));
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
            child: Text(
              snapshot.hasError ? 'Could not load services. Pull to retry.' : 'No services listed yet.',
              style: AppTextStyles.body2,
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
