import 'package:alakh_service/shared/widgets/location_rationale.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  Future<bool?> ask(WidgetTester tester, LocationPurpose purpose, String button) async {
    bool? answer;
    await tester.pumpWidget(MaterialApp(
      home: Builder(
        builder: (context) => TextButton(
          onPressed: () async => answer = await explainLocation(purpose, context: context),
          child: const Text('go'),
        ),
      ),
    ));
    await tester.tap(find.text('go'));
    await tester.pumpAndSettle();
    expect(find.text('Use your location?'), findsOneWidget);
    await tester.tap(find.text(button));
    await tester.pumpAndSettle();
    return answer;
  }

  testWidgets('explains why before the system asks for location', (tester) async {
    expect(await ask(tester, LocationPurpose.eta, 'Continue'), isTrue);
  });

  testWidgets('Not now stops before the system prompt', (tester) async {
    expect(await ask(tester, LocationPurpose.sharing, 'Not now'), isFalse);
  });
}
