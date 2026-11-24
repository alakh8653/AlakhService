import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

/// A key written twice in an ARB file silently keeps only the last text, so one screen shows
/// another's words (e.g. the customer's Profile titled "My profile and work photos").
void main() {
  for (final file in ['lib/l10n/app_en.arb', 'lib/l10n/app_hi.arb']) {
    test('$file has every key once', () {
      final keys = RegExp(r'^  "([^"@][^"]*)":', multiLine: true)
          .allMatches(File(file).readAsStringSync())
          .map((m) => m.group(1)!)
          .toList();
      final seen = <String>{};
      final twice = keys.where((k) => !seen.add(k)).toList();
      expect(twice, isEmpty, reason: 'written more than once: $twice');
    });
  }
}
