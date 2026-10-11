import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../core/di/injection_container.dart';
import '../features/auth/domain/entities/user.dart';
import '../features/booking/presentation/bloc/booking_bloc.dart';
import '../features/booking/presentation/pages/booking_history_page.dart';
import '../features/home/presentation/pages/home_page.dart';
import '../features/notifications/presentation/pages/notifications_page.dart';
import '../features/profile/presentation/pages/profile_page.dart';
import '../features/services/presentation/bloc/service_bloc.dart';
import '../features/services/presentation/pages/service_list_page.dart';
import '../shared/widgets/bottom_nav_bar.dart';

/// The signed-in app: Home, Services, Bookings and Profile tabs.
class HomeShell extends StatefulWidget {
  final User user;

  const HomeShell({super.key, required this.user});

  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> {
  static const _home = 0, _services = 1, _bookings = 2;

  int _index = _home;
  String? _serviceQuery;
  // Bumped on every visit so a tab reloads its data when shown again.
  int _visit = 0;

  void _select(int index, {String? query}) => setState(() {
        _index = index;
        _serviceQuery = query;
        _visit++;
      });

  void _openNotifications() =>
      Navigator.push(context, MaterialPageRoute(builder: (_) => const NotificationsPage()));

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
          child: const BookingHistoryPage(),
        );
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
    return Scaffold(
      body: _tab(),
      bottomNavigationBar: AppBottomNavBar(currentIndex: _index, onTap: _select),
    );
  }
}
