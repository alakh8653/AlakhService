import 'package:flutter/material.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_text_styles.dart';
import '../../../../shared/widgets/bottom_nav_bar.dart';
import 'home_widgets.dart';

class HomePage extends StatefulWidget {
  const HomePage({super.key});

  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  int _currentIndex = 0;

  static const List<_ServiceCategory> _categories = [
    _ServiceCategory(icon: Icons.cleaning_services, label: 'Cleaning'),
    _ServiceCategory(icon: Icons.plumbing, label: 'Plumbing'),
    _ServiceCategory(icon: Icons.electrical_services, label: 'Electrical'),
    _ServiceCategory(icon: Icons.carpenter, label: 'Carpentry'),
    _ServiceCategory(icon: Icons.ac_unit, label: 'AC Service'),
    _ServiceCategory(icon: Icons.local_laundry_service, label: 'Laundry'),
    _ServiceCategory(icon: Icons.pest_control, label: 'Pest Control'),
    _ServiceCategory(icon: Icons.handyman, label: 'Handyman'),
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.symmetric(vertical: 16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _buildHeader(),
              const SizedBox(height: 20),
              const BannerWidget(),
              const SizedBox(height: 24),
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16),
                child: Text('Our Services', style: AppTextStyles.heading3),
              ),
              const SizedBox(height: 16),
              _buildCategoriesGrid(),
              const SizedBox(height: 24),
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16),
                child: Text('Popular Near You', style: AppTextStyles.heading3),
              ),
              const SizedBox(height: 12),
              _buildFeaturedProviders(),
            ],
          ),
        ),
      ),
      bottomNavigationBar: AppBottomNavBar(
        currentIndex: _currentIndex,
        onTap: (i) => setState(() => _currentIndex = i),
      ),
    );
  }

  Widget _buildHeader() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: Row(
        children: [
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('Good Morning 👋', style: AppTextStyles.body2),
              Text('Find a Service', style: AppTextStyles.heading2),
            ],
          ),
          const Spacer(),
          CircleAvatar(
            radius: 22,
            backgroundColor: AppColors.primaryLight,
            child: const Icon(Icons.person, color: AppColors.primary),
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
        return ServiceCategoryCard(icon: cat.icon, label: cat.label);
      },
    );
  }

  Widget _buildFeaturedProviders() {
    return SizedBox(
      height: 180,
      child: ListView.separated(
        padding: const EdgeInsets.symmetric(horizontal: 16),
        scrollDirection: Axis.horizontal,
        itemCount: 5,
        separatorBuilder: (_, __) => const SizedBox(width: 12),
        itemBuilder: (context, index) => const FeaturedProviderCard(),
      ),
    );
  }
}

class _ServiceCategory {
  final IconData icon;
  final String label;

  const _ServiceCategory({required this.icon, required this.label});
}
