import 'package:flutter/material.dart';
import '../../widgets/custom_button.dart';
import '../../widgets/custom_text_field.dart';
import '../../../core/utils/validators.dart';

class EditProfilePage extends StatefulWidget {
  const EditProfilePage({super.key});
  @override
  State<EditProfilePage> createState() => _EditProfilePageState();
}

class _EditProfilePageState extends State<EditProfilePage> {
  final _formKey = GlobalKey<FormState>();
  final _nameCtrl = TextEditingController();
  final _phoneCtrl = TextEditingController();

  @override
  void dispose() { _nameCtrl.dispose(); _phoneCtrl.dispose(); super.dispose(); }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Edit Profile')),
      body: Padding(
        padding: const EdgeInsets.all(24),
        child: Form(
          key: _formKey,
          child: Column(
            children: [
              CustomTextField(controller: _nameCtrl, label: 'Full Name', prefixIcon: Icons.person_outline, validator: AppValidators.name),
              const SizedBox(height: 16),
              CustomTextField(controller: _phoneCtrl, label: 'Phone', keyboardType: TextInputType.phone, prefixIcon: Icons.phone_outlined, validator: AppValidators.phone),
              const SizedBox(height: 32),
              CustomButton(label: 'Save Changes', onPressed: () { if (_formKey.currentState!.validate()) Navigator.pop(context); }),
            ],
          ),
        ),
      ),
    );
  }
}
