import 'package:flutter/material.dart';

import '../../core/theme/app_text_styles.dart';
import '../../core/theme/app_theme.dart';
import '../../l10n/l10n.dart';

/// "✓ Verified": the platform checked the shop's documents (shop_service's is_verified).
class VerifiedBadge extends StatelessWidget {
  /// Just the tick, for tight rows.
  final bool compact;

  const VerifiedBadge({super.key, this.compact = false});

  @override
  Widget build(BuildContext context) {
    final color = context.palette.success;
    final label = context.l10n.verified;
    if (compact) {
      return Tooltip(message: label, child: Icon(Icons.verified, size: 16, color: color, semanticLabel: label));
    }
    return Container(
      key: const ValueKey('verified-badge'),
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(color: color.withValues(alpha: 0.12), borderRadius: BorderRadius.circular(6)),
      child: Row(mainAxisSize: MainAxisSize.min, children: [
        Icon(Icons.verified, size: 14, color: color),
        const SizedBox(width: 3),
        Text(label, style: AppTextStyles.caption.copyWith(color: color, fontWeight: FontWeight.w600)),
      ]),
    );
  }
}
