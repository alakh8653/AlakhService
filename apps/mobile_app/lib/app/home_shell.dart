import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../core/di/injection_container.dart';
import '../core/theme/app_theme.dart';
import '../features/auth/domain/entities/user.dart';
import '../features/booking/presentation/bloc/booking_bloc.dart';
import '../features/booking/presentation/pages/booking_history_page.dart';
import '../features/home/presentation/pages/home_page.dart';
import '../features/jobs/data/jobs_api.dart';
import '../features/jobs/presentation/jobs_page.dart';
import '../features/notifications/presentation/pages/notifications_page.dart';
import '../features/profile/presentation/pages/profile_page.dart';
import '../features/services/presentation/bloc/service_bloc.dart';
import '../features/services/presentation/pages/service_list_page.dart';
import '../features/shop_line/data/shop_line_api.dart';
import '../features/shop_owner/data/shop_owner_api.dart';
import '../features/shop_owner/presentation/owner_home_page.dart';
import '../features/shop_owner/presentation/shop_setup_page.dart';
import '../l10n/l10n.dart';
import '../shared/service_types.dart';
import '../shared/widgets/bottom_nav_bar.dart';
import 'shell_navigation.dart';

enum HomeTab { home, services, bookings, jobs, shop, profile }

/// The tabs on show. One person can both run a business and book services, and each side stays short and
/// uncluttered: My shop, Jobs and Profile while working; Home, Services, Bookings and Profile while booking.
/// Jobs stays beside the booking tabs for staff, who have no business side to switch to.
List<HomeTab> visibleTabs({required bool businessMode, required bool ownsShop, required bool hasJobs}) {
  if (businessMode && ownsShop) {
    return [HomeTab.shop, if (hasJobs) HomeTab.jobs, HomeTab.profile];
  }
  return [HomeTab.home, HomeTab.services, HomeTab.bookings, if (hasJobs && !ownsShop) HomeTab.jobs, HomeTab.profile];
}

/// The signed-in app, on its booking side or, for owners, its business side. Someone who joined to offer
/// services starts on setting up their business, and the app reopens on whichever side they used last.
class HomeShell extends StatefulWidget {
  final User user;
  final JobsApi? jobsApi;
  final ShopLineApi? shopLineApi;
  final ShopOwnerApi? ownerApi;

  const HomeShell({super.key, required this.user, this.jobsApi, this.shopLineApi, this.ownerApi});

  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> {
  HomeTab _tab = HomeTab.home;
  // Shown once the user turns out to have jobs assigned to them as a provider.
  bool _showJobs = false;
  // The shop the user owns, if any.
  OwnedShop? _shop;
  // False until the server has answered, so a slow or failed answer never looks like "no shop".
  bool _shopKnown = false;
  bool _businessMode = false;

  @override
  void initState() {
    super.initState();
    (widget.jobsApi ?? sl<JobsApi>()).hasJobs().then((has) {
      if (has && mounted) setState(() => _showJobs = true);
    }).catchError((Object _) {});
    _loadShop(openingApp: true);
    ShellNavigation.instance.addListener(_onTabRequest);
  }

  @override
  void dispose() {
    ShellNavigation.instance.removeListener(_onTabRequest);
    super.dispose();
  }

  /// Finds the user's shop. On opening the app, someone who came to offer services lands on it, or on
  /// setting it up.
  Future<void> _loadShop({bool openingApp = false}) async {
    final lineApi = widget.shopLineApi ?? (sl.isRegistered<ShopLineApi>() ? sl<ShopLineApi>() : null);
    if (lineApi == null) return;
    final OwnedShop? shop;
    try {
      shop = await lineApi.ownedShop(widget.user.id);
    } catch (_) {
      return; // Not knowing is not the same as having no shop: never offer setup on an error.
    }
    if (!mounted) return;
    setState(() {
      _shop = shop;
      _shopKnown = true;
    });
    if (!openingApp || !await OwnerIntent.read() || !mounted) return;
    if (shop != null) {
      _setBusinessMode(true);
    } else {
      await _setUpBusiness();
    }
  }

  Future<void> _setUpBusiness() async {
    await Navigator.push<void>(
      context,
      MaterialPageRoute(builder: (_) => ShopSetupPage(user: widget.user, api: widget.ownerApi)),
    );
    await _loadShop();
    if (_shop != null && mounted) _setBusinessMode(true);
  }

  /// Switches sides and remembers it, so the app reopens here.
  void _setBusinessMode(bool business) {
    OwnerIntent.save(business);
    setState(() {
      _businessMode = business;
      _tab = business ? HomeTab.shop : HomeTab.home;
      _visit++;
    });
  }

  void _onTabRequest() {
    final tab = ShellNavigation.instance.requested;
    if (tab == null || !mounted) return;
    // Screens ask for the booking side's tabs (after making a booking, say), so show that side.
    if (tab != ShellTab.profile) _businessMode = false;
    _select(switch (tab) {
      ShellTab.home => HomeTab.home,
      ShellTab.services => HomeTab.services,
      ShellTab.bookings => HomeTab.bookings,
      ShellTab.profile => HomeTab.profile,
    });
  }

  bool get _inBusiness => _businessMode && _shop != null;
  HomeTab get _firstTab => _inBusiness ? HomeTab.shop : HomeTab.home;
  List<HomeTab> get _tabs => visibleTabs(businessMode: _businessMode, ownsShop: _shop != null, hasJobs: _showJobs);
  String? _serviceQuery;
  ServiceType? _serviceType;
  // Bumped on every visit so a tab reloads its data when shown again.
  int _visit = 0;

  void _select(HomeTab tab, {String? query, ServiceType? type}) => setState(() {
        _tab = tab;
        _serviceQuery = query;
        _serviceType = type;
        _visit++;
      });

  Future<void> _openNotifications() =>
      Navigator.push<void>(context, MaterialPageRoute(builder: (_) => const NotificationsPage()));

  Widget _body(AppLocalizations l10n) {
    switch (_tab) {
      case HomeTab.home:
        return HomePage(
          user: widget.user,
          onSearch: (query) => _select(HomeTab.services, query: query),
          onOpenType: (type) => _select(HomeTab.services, type: type),
          onOpenNotifications: _openNotifications,
          onOpenBookings: () => _select(HomeTab.bookings),
        );
      case HomeTab.services:
        return BlocProvider<ServiceBloc>(
          key: ValueKey('services-$_visit'),
          create: (_) => sl<ServiceBloc>(),
          child: ServiceListPage(initialQuery: _serviceQuery, type: _serviceType),
        );
      case HomeTab.bookings:
        return BlocProvider<BookingBloc>(
          key: ValueKey('bookings-$_visit'),
          create: (_) => sl<BookingBloc>(),
          child: BookingHistoryPage(onBrowseServices: () => _select(HomeTab.services)),
        );
      case HomeTab.jobs:
        return JobsPage(key: ValueKey('jobs-$_visit'), providerId: widget.user.id);
      case HomeTab.shop:
        return OwnerHomePage(
          key: ValueKey('owner-$_visit'),
          shop: _shop!,
          user: widget.user,
          api: widget.ownerApi,
          lineApi: widget.shopLineApi,
          onSwitchToBooking: () => _setBusinessMode(false),
        );
      case HomeTab.profile:
        return ProfilePage(
          user: widget.user,
          onOpenBookings: () {
            if (_inBusiness) _businessMode = false;
            _select(HomeTab.bookings);
          },
          onOpenNotifications: _openNotifications,
          onOfferServices: _shopKnown && _shop == null ? _setUpBusiness : null,
          switchModeLabel: _shop == null ? null : (_inBusiness ? l10n.modeSwitchToBooking : l10n.modeSwitchToBusiness),
          onSwitchMode: _shop == null ? null : () => _setBusinessMode(!_inBusiness),
        );
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final tabs = _tabs;
    final showSwitchStrip = _shop != null && !_inBusiness && _tab == HomeTab.home;
    // Android back on another tab goes to the side's first tab instead of closing the app.
    return PopScope(
      canPop: _tab == _firstTab,
      onPopInvokedWithResult: (didPop, _) {
        if (!didPop) _select(_firstTab);
      },
      child: Scaffold(
        body: _body(l10n),
        bottomNavigationBar: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (showSwitchStrip)
              Material(
                color: context.colors.primaryContainer,
                child: InkWell(
                  key: const ValueKey('switch-to-business'),
                  onTap: () => _setBusinessMode(true),
                  child: Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                    child: Row(
                      children: [
                        Icon(Icons.storefront_outlined, size: 20, color: context.colors.primary),
                        const SizedBox(width: 8),
                        Expanded(child: Text(l10n.modeSwitchToBusiness)),
                        Icon(Icons.chevron_right, color: context.colors.primary),
                      ],
                    ),
                  ),
                ),
              ),
            AppBottomNavBar(
              currentIndex: tabs.contains(_tab) ? tabs.indexOf(_tab) : 0,
              onTap: (i) => _select(tabs[i]),
              showJobs: tabs.contains(HomeTab.jobs),
              showShopLine: tabs.contains(HomeTab.shop),
              businessMode: _inBusiness,
            ),
          ],
        ),
      ),
    );
  }
}
