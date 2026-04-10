import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:get_it/get_it.dart';

import 'config/routes.dart';
import 'config/theme.dart';
import 'presentation/bloc/auth/auth_bloc.dart';
import 'presentation/bloc/booking/booking_bloc.dart';
import 'presentation/bloc/service/service_bloc.dart';

class AlakhServiceApp extends StatelessWidget {
  const AlakhServiceApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MultiBlocProvider(
      providers: [
        BlocProvider<AuthBloc>(
          create: (_) => GetIt.instance<AuthBloc>()..add(AppStarted()),
        ),
        BlocProvider<ServiceBloc>(
          create: (_) => GetIt.instance<ServiceBloc>(),
        ),
        BlocProvider<BookingBloc>(
          create: (_) => GetIt.instance<BookingBloc>(),
        ),
      ],
      child: MaterialApp.router(
        title: 'AlakhService',
        debugShowCheckedModeBanner: false,
        theme: AppTheme.lightTheme,
        darkTheme: AppTheme.darkTheme,
        themeMode: ThemeMode.system,
        routerConfig: AppRouter.router,
      ),
    );
  }
}
