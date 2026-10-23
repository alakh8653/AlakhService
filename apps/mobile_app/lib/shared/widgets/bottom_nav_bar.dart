import 'package:flutter/material.dart';
import '../../core/theme/app_theme.dart';
import '../../core/theme/app_text_styles.dart';
import '../../l10n/l10n.dart';

class AppBottomNavBar extends StatelessWidget {
  final int currentIndex;
  final ValueChanged<int> onTap;

  /// Adds a Jobs tab (before Profile) for people who work as providers.
  final bool showJobs;

  const AppBottomNavBar({
    super.key,
    required this.currentIndex,
    required this.onTap,
    this.showJobs = false,
  });

  static String _jobsLabel(AppLocalizations l10n) => l10n.navJobs;
  static const _jobs = _NavItem(icon: Icons.work_outline, activeIcon: Icons.work, label: _jobsLabel);

  static const List<_NavItem> _items = [
    _NavItem(icon: Icons.home_outlined, activeIcon: Icons.home, label: _home),
    _NavItem(
      icon: Icons.search_outlined,
      activeIcon: Icons.search,
      label: _services,
    ),
    _NavItem(
      icon: Icons.calendar_today_outlined,
      activeIcon: Icons.calendar_today,
      label: _bookings,
    ),
    _NavItem(
      icon: Icons.person_outline,
      activeIcon: Icons.person,
      label: _profile,
    ),
  ];

  @override
  Widget build(BuildContext context) {
    return BottomNavigationBar(
      currentIndex: currentIndex,
      onTap: onTap,
      type: BottomNavigationBarType.fixed,
      selectedItemColor: context.colors.primary,
      unselectedItemColor: context.palette.muted,
      selectedLabelStyle: AppTextStyles.caption.themed(context).copyWith(
        color: context.colors.primary,
        fontWeight: FontWeight.w600,
      ),
      unselectedLabelStyle: AppTextStyles.caption.themed(context),
      items: [..._items.take(3), if (showJobs) _jobs, _items.last]
          .map(
            (item) => BottomNavigationBarItem(
              icon: Icon(item.icon),
              activeIcon: Icon(item.activeIcon),
              label: item.label(context.l10n),
            ),
          )
          .toList(),
    );
  }
}

String _home(AppLocalizations l10n) => l10n.navHome;
String _services(AppLocalizations l10n) => l10n.navServices;
String _bookings(AppLocalizations l10n) => l10n.navBookings;
String _profile(AppLocalizations l10n) => l10n.navProfile;

class _NavItem {
  final IconData icon;
  final IconData activeIcon;
  final String Function(AppLocalizations) label;

  const _NavItem({
    required this.icon,
    required this.activeIcon,
    required this.label,
  });
}
