import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';
import '../../bloc/auth/auth_bloc.dart';
import '../../bloc/auth/auth_event.dart';
import '../../bloc/auth/auth_state.dart';
import '../../../config/routes.dart';

class ProfilePage extends StatelessWidget {
  const ProfilePage({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Profile')),
      body: BlocBuilder<AuthBloc, AuthState>(
        builder: (context, state) {
          final user = state is Authenticated ? state.user : null;
          return ListView(
            padding: const EdgeInsets.all(24),
            children: [
              CircleAvatar(radius: 48, child: Text(user?.name.substring(0,1).toUpperCase() ?? 'U', style: const TextStyle(fontSize: 36))),
              const SizedBox(height: 16),
              Text(user?.name ?? 'User', textAlign: TextAlign.center, style: Theme.of(context).textTheme.headlineMedium),
              Text(user?.email ?? '', textAlign: TextAlign.center, style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: Colors.grey)),
              const SizedBox(height: 32),
              ListTile(leading: const Icon(Icons.edit), title: const Text('Edit Profile'), onTap: () => context.push(Routes.editProfile)),
              ListTile(leading: const Icon(Icons.history), title: const Text('Booking History'), onTap: () => context.push(Routes.bookingHistory)),
              ListTile(leading: const Icon(Icons.lock_outline), title: const Text('Change Password'), onTap: () {}),
              ListTile(leading: const Icon(Icons.help_outline), title: const Text('Help & Support'), onTap: () {}),
              const Divider(),
              ListTile(
                leading: const Icon(Icons.logout, color: Colors.red),
                title: const Text('Logout', style: TextStyle(color: Colors.red)),
                onTap: () => context.read<AuthBloc>().add(LogoutRequested()),
              ),
            ],
          );
        },
      ),
    );
  }
}
