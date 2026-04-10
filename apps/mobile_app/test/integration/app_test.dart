import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';

import 'package:alakh_service/main.dart' as app;

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  group('App startup integration tests', () {
    testWidgets('app launches without errors', (tester) async {
      app.main();
      await tester.pumpAndSettle(const Duration(seconds: 5));

      // Verify the app is running and the root widget is present.
      expect(find.byType(MaterialApp), findsOneWidget);
    });

    testWidgets('AlakhService title is present', (tester) async {
      app.main();
      await tester.pumpAndSettle(const Duration(seconds: 5));

      // The app title should be set in the MaterialApp.
      final materialApp =
          tester.widget<MaterialApp>(find.byType(MaterialApp));
      expect(materialApp.title, 'AlakhService');
    });

    testWidgets('theme is applied on startup', (tester) async {
      app.main();
      await tester.pumpAndSettle(const Duration(seconds: 3));

      final materialApp =
          tester.widget<MaterialApp>(find.byType(MaterialApp));
      expect(materialApp.theme, isNotNull);
      expect(materialApp.darkTheme, isNotNull);
    });
  });
}
