import 'package:flutter/material.dart';

import '../../../../core/theme/app_text_styles.dart';
import '../../../../l10n/l10n.dart';
import '../../../../shared/service_types.dart';

/// Every kind of service, by group. Picking one shows the providers of that type.
class AllServicesPage extends StatelessWidget {
  final ValueChanged<ServiceType> onPick;

  const AllServicesPage({super.key, required this.onPick});

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    return Scaffold(
      appBar: AppBar(title: Text(l10n.allServices)),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          for (final group in ServiceGroup.values) ...[
            Padding(
              padding: const EdgeInsets.only(top: 12, bottom: 4),
              child: Text(serviceGroupLabel(group, l10n), style: AppTextStyles.heading3),
            ),
            for (final type in serviceTypes.where((t) => t.group == group && t.id != 'other'))
              ListTile(
                contentPadding: EdgeInsets.zero,
                leading: Icon(type.icon),
                title: Text(type.label(l10n), style: AppTextStyles.body1),
                trailing: const Icon(Icons.chevron_right),
                onTap: () {
                  Navigator.pop(context);
                  onPick(type);
                },
              ),
          ],
        ],
      ),
    );
  }
}
