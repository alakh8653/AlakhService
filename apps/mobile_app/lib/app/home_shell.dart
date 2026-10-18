import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../core/di/injection_container.dart';
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
import '../shared/widgets/bottom_nav_bar.dart';
import 'shell_navigation.dart';

/// The signed-in app: Home, Services, Bookings and Profile tabs, plus Jobs for providers.
class HomeShell extends StatefulWidget {
  final User user;
  final JobsApi? jobsApi;

  const HomeShell({super.key, required this.user, this.jobsApi});

  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> {
  // Tab ids; the bar shows them in this order, Jobs only for providers.
  static const _home = 0, _services = 1, _bookings = 2, _jobs = 3, _profile = 4;

  int _index = _home;
  // Shown once the user turns out to have jobs assigned to them as a provider.
  bool _showJobs = false;

  @override
  void initState() {
    super.initState();
    (widget.jobsApi ?? sl<JobsApi>()).hasJobs().then((has) {
      if (has && mounted) setState(() => _showJobs = true);
    }).catchError((Object _) {});
    ShellNavigation.instance.addListener(_onTabRequest);
  }

  @override
  void dispose() {
    ShellNavigation.instance.removeListener(_onTabRequest);
    super.dispose();
  }

  void _onTabRequest() {
    final tab = ShellNavigation.instance.requested;
    if (tab == null || !mounted) return;
    _select(switch (tab) {
      ShellTab.home => _home,
      ShellTab.services => _services,
      ShellTab.bookings => _bookings,
      ShellTab.profile => _profile,
    });
  }

  List<int> get _tabs => [_home, _services, _bookings, if (_showJobs) _jobs, _profile];
  String? _serviceQuery;
  // Bumped on every visit so a tab reloads its data when shown again.
  int _visit = 0;

  void _select(int index, {String? query}) => setState(() {
        _index = index;
        _serviceQuery = query;
        _visit++;
      });

  Future<void> _openNotifications() =>
      Navigator.push<void>(context, MaterialPageRoute(builder: (_) => const NotificationsPage()));

  Widget _tab() {
    switch (_index) {
      case _home:
        return HomePage(
          user: widget.user,
          onSearch: (query) => _select(_services, query: query),
          onOpenNotifications: _openNotifications,
          onOpenBookings: () => _select(_bookings),
        );
      case _services:
        return BlocProvider<ServiceBloc>(
          key: ValueKey('services-$_visit'),
          create: (_) => sl<ServiceBloc>(),
          child: ServiceListPage(initialQuery: _serviceQuery),
        );
      case _bookings:
        return BlocProvider<BookingBloc>(
          key: ValueKey('bookings-$_visit'),
          create: (_) => sl<BookingBloc>(),
          child: BookingHistoryPage(onBrowseServices: () => _select(_services)),
        );
      case _jobs:
        return JobsPage(key: ValueKey('jobs-$_visit'), providerId: widget.user.id);
      default:
        return ProfilePage(
          user: widget.user,
          onOpenBookings: () => _select(_bookings),
          onOpenNotifications: _openNotifications,
        );
    }
  }

  @override
  Widget build(BuildContext context) {
    // Android back on another tab goes Home first instead of closing the app.
    return PopScope(
      canPop: _index == _home,
      onPopInvokedWithResult: (didPop, _) {
        if (!didPop) _select(_home);
      },
      child: Scaffold(
        body: _tab(),
        bottomNavigationBar: AppBottomNavBar(
          currentIndex: _tabs.indexOf(_index),
          onTap: (i) => _select(_tabs[i]),
          showJobs: _showJobs,
        ),
      ),
    );
  }
}
