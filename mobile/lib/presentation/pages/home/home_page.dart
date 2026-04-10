import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';

import '../../bloc/service/service_bloc.dart';
import '../../bloc/service/service_event.dart';
import '../../bloc/auth/auth_bloc.dart';
import '../../bloc/auth/auth_state.dart';
import '../../../config/routes.dart';
import '../../../core/constants/app_constants.dart';
import '../../widgets/service_card.dart';
import '../../widgets/loading_indicator.dart';
import '../../widgets/bottom_nav_bar.dart';
import 'home_widgets.dart';

class HomePage extends StatefulWidget {
  const HomePage({super.key});

  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  int _selectedIndex = 0;

  @override
  void initState() {
    super.initState();
    context.read<ServiceBloc>().add(const LoadServices());
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text(AppConstants.appName),
        actions: [
          IconButton(
            icon: const Icon(Icons.notifications_outlined),
            onPressed: () {},
          ),
        ],
      ),
      body: BlocBuilder<AuthBloc, AuthState>(
        builder: (context, authState) {
          final userName = authState is Authenticated ? authState.user.name : 'there';
          return RefreshIndicator(
            onRefresh: () async =>
                context.read<ServiceBloc>().add(RefreshServices()),
            child: SingleChildScrollView(
              physics: const AlwaysScrollableScrollPhysics(),
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  HomeGreetingWidget(userName: userName),
                  const SizedBox(height: 16),
                  const HomeSearchBar(),
                  const SizedBox(height: 24),
                  Text(
                    'Popular Services',
                    style: Theme.of(context).textTheme.titleLarge,
                  ),
                  const SizedBox(height: 12),
                  const _ServiceGrid(),
                ],
              ),
            ),
          );
        },
      ),
      bottomNavigationBar: AppBottomNavBar(
        currentIndex: _selectedIndex,
        onTap: (index) {
          setState(() => _selectedIndex = index);
          switch (index) {
            case 1:
              context.push(Routes.serviceList);
            case 2:
              context.push(Routes.bookingHistory);
            case 3:
              context.push(Routes.profile);
            default:
              break;
          }
        },
      ),
    );
  }
}

class _ServiceGrid extends StatelessWidget {
  const _ServiceGrid();

  @override
  Widget build(BuildContext context) {
    return BlocBuilder<ServiceBloc, dynamic>(
      builder: (context, state) {
        if (state is dynamic && state.runtimeType.toString() == 'ServiceLoading') {
          return const LoadingIndicator();
        }
        // Simplified display — full list is on ServiceListPage
        return const SizedBox.shrink();
      },
    );
  }
}
