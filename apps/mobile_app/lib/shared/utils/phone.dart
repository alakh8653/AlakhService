/// Phone numbers in E.164 form ("+919876543210"), as the API expects.
///
/// Ten-digit numbers without a country code are taken as Indian (+91).
String normalizePhone(String input) {
  final trimmed = input.trim();
  final digits = trimmed.replaceAll(RegExp(r'\D'), '');
  if (trimmed.startsWith('+')) return '+$digits';
  if (digits.length == 10) return '+91$digits';
  if (digits.startsWith('0') && digits.length == 11) return '+91${digits.substring(1)}';
  return '+$digits';
}

/// Emails are passed through; anything else is treated as a phone number.
String normalizeIdentifier(String input) => input.contains('@') ? input.trim().toLowerCase() : normalizePhone(input);
