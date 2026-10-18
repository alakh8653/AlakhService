import 'package:flutter/material.dart';

import '../../../../core/di/injection_container.dart';
import '../../../../core/network/api_errors.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_text_styles.dart';
import '../../../../shared/utils/format.dart';
import '../../../../shared/utils/validators.dart';
import '../../../../shared/widgets/custom_button.dart';
import '../../../../shared/widgets/custom_text_field.dart';
import '../../../auth/domain/entities/user.dart';
import '../../data/profile_api.dart';

/// Edits the profile details kept by user_service. Pops with the saved name.
class EditProfilePage extends StatefulWidget {
  final User user;
  final ProfileApi? profileApi;

  const EditProfilePage({super.key, required this.user, this.profileApi});

  @override
  State<EditProfilePage> createState() => _EditProfilePageState();
}

class _EditProfilePageState extends State<EditProfilePage> {
  late final ProfileApi _api = widget.profileApi ?? sl<ProfileApi>();
  final _formKey = GlobalKey<FormState>();
  late final _nameController = TextEditingController(text: widget.user.name);
  final _bioController = TextEditingController();
  late final _phoneController = TextEditingController(text: displayPhone(widget.user.phone));
  bool _isSaving = false;

  @override
  void initState() {
    super.initState();
    _api.get().then((profile) {
      if (!mounted || profile == null) return;
      if (profile.fullName != null) _nameController.text = profile.fullName!;
      if (profile.bio != null) _bioController.text = profile.bio!;
    }).catchError((Object _) {});
  }

  @override
  void dispose() {
    _nameController.dispose();
    _bioController.dispose();
    _phoneController.dispose();
    super.dispose();
  }

  Future<void> _onSave() async {
    if (_isSaving) return;
    if (!(_formKey.currentState?.validate() ?? false)) return;
    setState(() => _isSaving = true);
    try {
      final profile = await _api.update(
        fullName: _nameController.text.trim(),
        bio: _bioController.text.trim(),
      );
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Profile updated successfully')),
      );
      Navigator.pop(context, profile.fullName ?? _nameController.text.trim());
    } catch (e) {
      if (!mounted) return;
      setState(() => _isSaving = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(apiErrorMessage(e)), backgroundColor: AppColors.error),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Edit Profile')),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(24),
        child: Form(
          key: _formKey,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('Personal Information', style: AppTextStyles.subtitle1),
              const SizedBox(height: 16),
              CustomTextField(
                controller: _nameController,
                label: 'Full Name',
                textCapitalization: TextCapitalization.words,
                autofillHints: const [AutofillHints.name],
                validator: Validators.name,
              ),
              const SizedBox(height: 16),
              CustomTextField(
                controller: _bioController,
                label: 'About you',
                hint: 'Optional',
                maxLines: 3,
                textCapitalization: TextCapitalization.sentences,
              ),
              const SizedBox(height: 16),
              CustomTextField(
                controller: _phoneController,
                label: 'Phone Number',
                helper: "Your sign-in number can't be changed here.",
                readOnly: true,
              ),
              const SizedBox(height: 32),
              CustomButton(
                label: 'Save Changes',
                onPressed: _isSaving ? null : _onSave,
                isLoading: _isSaving,
              ),
            ],
          ),
        ),
      ),
    );
  }
}
