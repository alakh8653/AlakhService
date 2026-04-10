import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:alakh_service_mobile/presentation/bloc/auth/auth_bloc.dart';
import 'package:alakh_service_mobile/presentation/bloc/auth/auth_state.dart';
import 'package:alakh_service_mobile/presentation/pages/auth/login_page.dart';

class MockAuthBloc extends MockBloc<dynamic, AuthState> implements AuthBloc {}

void main() {
  late MockAuthBloc mockAuthBloc;
  setUp(() { mockAuthBloc = MockAuthBloc(); when(() => mockAuthBloc.state).thenReturn(AuthInitial()); });

  testWidgets('LoginPage renders email and password fields', (tester) async {
    await tester.pumpWidget(MaterialApp(home: BlocProvider<AuthBloc>.value(value: mockAuthBloc, child: const LoginPage())));
    expect(find.text('Email'), findsOneWidget);
    expect(find.text('Password'), findsOneWidget);
    expect(find.text('Sign In'), findsOneWidget);
  });
}
