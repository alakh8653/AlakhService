import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../../core/di/injection_container.dart';
import '../../../../core/network/api_errors.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_theme.dart';
import '../../../../core/theme/app_text_styles.dart';
import '../../../../shared/utils/format.dart';
import '../../../../shared/utils/helpers.dart';
import '../../../../shared/widgets/custom_button.dart';
import '../../../auth/domain/entities/user.dart';
import '../../../auth/presentation/bloc/auth_bloc.dart';
import '../../../auth/presentation/bloc/auth_event.dart';
import '../../../help/presentation/help_support_page.dart';
import '../../../loyalty/presentation/rewards_page.dart';
import '../../../shops/presentation/saved_shops_page.dart';
import '../../data/profile_api.dart';
import 'addresses_page.dart';
import 'display_settings.dart';
import 'edit_profile_page.dart';
import 'legal_section.dart';
import '../../../../l10n/l10n.dart';

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
        title: Text(context.l10n.logoutQuestion),
        content: Text(context.l10n.logoutBody),
        actions: [
          TextButton(onPressed: () => Navigator.pop(dialogContext, false), child: Text(context.l10n.cancel)),
          TextButton(onPressed: () => Navigator.pop(dialogContext, true), child: Text(context.l10n.logout)),
        ],
      ),
    );
    if (confirmed == true && mounted) {
      context.read<AuthBloc>().add(const LogoutRequested());
    }
  }

  Future<void> _deleteAccount() async {
    final password = await showDialog<String>(context: context, builder: (_) => const _DeleteAccountDialog());
    if (password == null || !mounted) return;
    final messenger = ScaffoldMessenger.of(context);
    final deleted = context.l10n.accountDeleted;
    final auth = context.read<AuthBloc>();
    try {
      await sl<ProfileApi>().deleteAccount(password);
      messenger.showSnackBar(SnackBar(content: Text(deleted)));
      auth.add(const LogoutRequested());
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text(apiErrorMessage(e)), backgroundColor: AppColors.error));
    }
  }

  @override
  Widget build(BuildContext context) {
    final user = widget.user;
    final l10n = context.l10n;
    return Scaffold(
      appBar: AppBar(title: Text(l10n.profileTitle)),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(24),
        child: Column(
          children: [
            CircleAvatar(
              radius: 44,
              backgroundColor: context.colors.primaryContainer,
              child: _name.trim().isEmpty
                  ? Icon(Icons.person, size: 44, color: context.colors.primary)
                  : Text(AppHelpers.initials(_name), style: AppTextStyles.heading2.copyWith(color: context.colors.primary)),
            ),
            const SizedBox(height: 12),
            Text(_name, style: AppTextStyles.heading3),
            if (user.phone.isNotEmpty) Text(displayPhone(user.phone), style: AppTextStyles.body2.themed(context)),
            if (user.email != null) Text(user.email!, style: AppTextStyles.body2.themed(context)),
            const SizedBox(height: 24),
            _ProfileMenuItem(icon: Icons.edit_outlined, label: l10n.editProfile, onTap: _editProfile),
            _ProfileMenuItem(icon: Icons.history, label: l10n.myBookings, onTap: widget.onOpenBookings),
            _ProfileMenuItem(
              icon: Icons.card_giftcard,
              label: l10n.rewardsTitle,
              onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const RewardsPage())),
            ),
            _ProfileMenuItem(
              icon: Icons.favorite_border,
              label: l10n.savedShops,
              onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const SavedShopsPage())),
            ),
            _ProfileMenuItem(
              icon: Icons.location_on_outlined,
              label: l10n.savedAddresses,
              onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const AddressesPage())),
            ),
            _ProfileMenuItem(
              icon: Icons.notifications_outlined,
              label: l10n.notifications,
              onTap: widget.onOpenNotifications,
            ),
            const DisplaySettings(),
            _ProfileMenuItem(
              icon: Icons.help_outline,
              label: l10n.helpTitle,
              onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const HelpSupportPage())),
            ),
            LegalSection(userId: user.id),
            const SizedBox(height: 16),
            CustomButton(
              label: l10n.logout,
              variant: ButtonVariant.secondary,
              onPressed: _confirmLogout,
            ),
            const SizedBox(height: 8),
            TextButton(
              onPressed: _deleteAccount,
              style: TextButton.styleFrom(foregroundColor: context.colors.error),
              child: Text(l10n.deleteMyAccount),
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
      leading: Icon(icon, color: context.palette.muted),
      title: Text(label, style: AppTextStyles.body1),
      trailing: Icon(Icons.chevron_right, color: context.palette.muted),
      onTap: onTap,
      contentPadding: EdgeInsets.zero,
    );
  }
}


/// Explains what deleting removes and asks for the password; pops with it.
class _DeleteAccountDialog extends StatefulWidget {
  const _DeleteAccountDialog();

  @override
  State<_DeleteAccountDialog> createState() => _DeleteAccountDialogState();
}

class _DeleteAccountDialogState extends State<_DeleteAccountDialog> {
  final _password = TextEditingController();
  bool _obscure = true;

  @override
  void dispose() {
    _password.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: Text(context.l10n.deleteAccountQuestion),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            context.l10n.deleteAccountBody,
            style: AppTextStyles.body2.themed(context),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _password,
            obscureText: _obscure,
            autofillHints: const [AutofillHints.password],
            onChanged: (_) => setState(() {}),
            decoration: InputDecoration(
              labelText: context.l10n.enterPasswordConfirm,
              suffixIcon: IconButton(
                tooltip: _obscure ? context.l10n.showPassword : context.l10n.hidePassword,
                icon: Icon(_obscure ? Icons.visibility_off : Icons.visibility),
                onPressed: () => setState(() => _obscure = !_obscure),
              ),
            ),
          ),
        ],
      ),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context), child: Text(context.l10n.cancel)),
        TextButton(
          onPressed: _password.text.isEmpty ? null : () => Navigator.pop(context, _password.text),
          style: TextButton.styleFrom(foregroundColor: context.colors.error),
          child: Text(context.l10n.deleteAccount),
        ),
      ],
    );
  }
}
