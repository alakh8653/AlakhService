import 'package:alakh_service/core/theme/app_colors.dart';
import 'package:alakh_service/core/theme/app_theme.dart';
import 'package:alakh_service/shared/widgets/custom_button.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

Color labelColour(WidgetTester tester, String label) {
  final element = tester.element(find.text(label));
  final text = tester.widget<Text>(find.text(label));
  return DefaultTextStyle.of(element).style.merge(text.style).color!;
}

void main() {
  testWidgets('every button variant draws its label in a colour that shows on its background', (tester) async {
    await tester.pumpWidget(MaterialApp(
      theme: AppTheme.lightTheme,
      home: Scaffold(
        body: Column(children: [
          CustomButton(label: 'Book Now', onPressed: () {}),
          CustomButton(label: 'Leave Queue', variant: ButtonVariant.secondary, onPressed: () {}),
          CustomButton(label: 'Join the walk-in queue', variant: ButtonVariant.outlined, onPressed: () {}),
        ]),
      ),
    ));

    expect(labelColour(tester, 'Book Now'), AppColors.textLight); // white on the primary fill
    expect(labelColour(tester, 'Leave Queue'), AppColors.primary); // on a white surface
    expect(labelColour(tester, 'Join the walk-in queue'), isNot(AppColors.textLight));
  });
}
