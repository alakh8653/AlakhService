import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_text_styles.dart';
import '../../../../shared/widgets/custom_button.dart';
import '../../../auth/domain/entities/user.dart';
import '../../../auth/presentation/bloc/auth_bloc.dart';
import '../../../auth/presentation/bloc/auth_event.dart';
import 'edit_profile_page.dart';

class ProfilePage extends StatefulWidget {
  final User user;
  final VoidCallback onOpenBookings;
  final VoidCallback onOpenNotifications;

  const ProfilePage({
    super.key,
    required this.user,
    required this.onOpenBookings,
    required this.onOpenNotifications,
  });

  @override
  State<ProfilePage> createState() => _ProfilePageState();
}

class _ProfilePageState extends State<ProfilePage> {
  late String _name = widget.user.name;

  Future<void> _editProfile() async {
    final updated = await Navigator.push<String>(
      context,
      MaterialPageRoute(builder: (_) => EditProfilePage(user: widget.user)),
    );
    if (updated != null && mounted) setState(() => _name = updated);
  }

  Future<void> _confirmLogout() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Log out?'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(dialogContext, false), child: const Text('Cancel')),
          TextButton(onPressed: () => Navigator.pop(dialogContext, true), child: const Text('Log out')),
        ],
      ),
    );
    if (confirmed == true && mounted) {
      context.read<AuthBloc>().add(const LogoutRequested());
    }
  }

  @override
  Widget build(BuildContext context) {
    final user = widget.user;
    return Scaffold(
      appBar: AppBar(title: const Text('Profile')),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(24),
        child: Column(
          children: [
            const CircleAvatar(
              radius: 52,
              backgroundColor: AppColors.primaryLight,
              child: Icon(Icons.person, size: 52, color: AppColors.primary),
            ),
            const SizedBox(height: 12),
            Text(_name, style: AppTextStyles.heading3),
            if (user.phone.isNotEmpty) Text(user.phone, style: AppTextStyles.body2),
            if (user.email != null) Text(user.email!, style: AppTextStyles.body2),
            const SizedBox(height: 24),
            _ProfileMenuItem(icon: Icons.edit_outlined, label: 'Edit Profile', onTap: _editProfile),
            _ProfileMenuItem(icon: Icons.history, label: 'My Bookings', onTap: widget.onOpenBookings),
            _ProfileMenuItem(
              icon: Icons.notifications_outlined,
              label: 'Notifications',
              onTap: widget.onOpenNotifications,
            ),
            const SizedBox(height: 16),
            CustomButton(
              label: 'Logout',
              variant: ButtonVariant.secondary,
              onPressed: _confirmLogout,
            ),
          ],
        ),
      ),
    );
  }
}

class _ProfileMenuItem extends StatelessWidget {
  final IconData icon;
  final String label;
  final VoidCallback onTap;

  const _ProfileMenuItem({required this.icon, required this.label, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return ListTile(
      leading: Icon(icon, color: AppColors.textSecondary),
      title: Text(label, style: AppTextStyles.body1),
      trailing: const Icon(Icons.chevron_right, color: AppColors.textSecondary),
      onTap: onTap,
      contentPadding: EdgeInsets.zero,
    );
  }
}
