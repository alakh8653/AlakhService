import 'package:flutter/material.dart';

import '../../../core/theme/app_text_styles.dart';
import '../../../core/theme/app_theme.dart';
import '../../../l10n/l10n.dart';
import '../../../shared/utils/format.dart';
import '../data/shop_owner_api.dart';

/// Which days the business is open and from when to when. One set of hours for the chosen days covers
/// most small businesses; the shop dashboard handles breaks and different hours per day.
class WeekHoursEditor extends StatelessWidget {
  final WeekHours hours;
  final ValueChanged<WeekHours> onChanged;

  const WeekHoursEditor({super.key, required this.hours, required this.onChanged});

  // 2024-01-01 was a Monday.
  static DateTime _monday(int day) => DateTime(2024, 1, 1 + day);

  String _time(int minutes) => clockTime(DateTime(2024, 1, 1, minutes ~/ 60, minutes % 60));

  Future<void> _pick(BuildContext context, {required bool opening}) async {
    final current = opening ? hours.opens : hours.closes;
    final picked = await showTimePicker(
      context: context,
      initialTime: TimeOfDay(hour: (current ~/ 60) % 24, minute: current % 60),
    );
    if (picked == null) return;
    final minutes = WeekHours.toQuarterHour(picked.hour * 60 + picked.minute);
    onChanged(WeekHours(
      days: hours.days,
      opens: opening ? minutes : hours.opens,
      closes: opening ? hours.closes : minutes,
    ));
  }

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(l10n.ownerOpenDays, style: AppTextStyles.body2.themed(context)),
        const SizedBox(height: 8),
        Wrap(
          spacing: 8,
          runSpacing: 4,
          children: [
            for (var day = 0; day < 7; day++)
              FilterChip(
                label: Text(shortWeekday(_monday(day), l10n)),
                selected: hours.days.contains(day),
                onSelected: (on) => onChanged(WeekHours(
                  days: on ? {...hours.days, day} : ({...hours.days}..remove(day)),
                  opens: hours.opens,
                  closes: hours.closes,
                )),
              ),
          ],
        ),
        const SizedBox(height: 16),
        Row(
          children: [
            Expanded(
              child: OutlinedButton.icon(
                key: const ValueKey('opens'),
                icon: const Icon(Icons.schedule),
                label: Text('${l10n.ownerOpensAt} ${_time(hours.opens)}'),
                onPressed: () => _pick(context, opening: true),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: OutlinedButton.icon(
                key: const ValueKey('closes'),
                icon: const Icon(Icons.schedule),
                label: Text('${l10n.ownerClosesAt} ${_time(hours.closes)}'),
                onPressed: () => _pick(context, opening: false),
              ),
            ),
          ],
        ),
        if (hours.opens >= hours.closes) ...[
          const SizedBox(height: 8),
          Text(l10n.ownerHoursInvalid, style: AppTextStyles.caption.copyWith(color: Theme.of(context).colorScheme.error)),
        ],
      ],
    );
  }
}
