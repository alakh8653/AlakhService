import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../presentation/pages/splash_page.dart';
import '../presentation/pages/onboarding_page.dart';
import '../presentation/pages/auth/login_page.dart';
import '../presentation/pages/auth/register_page.dart';
import '../presentation/pages/auth/forgot_password_page.dart';
import '../presentation/pages/home/home_page.dart';
import '../presentation/pages/services/service_list_page.dart';
import '../presentation/pages/services/service_detail_page.dart';
import '../presentation/pages/booking/booking_page.dart';
import '../presentation/pages/booking/booking_history_page.dart';
import '../presentation/pages/payment/payment_page.dart';
import '../presentation/pages/profile/profile_page.dart';
import '../presentation/pages/profile/edit_profile_page.dart';

/// Named route constants.
abstract class Routes {
  static const splash = '/';
  static const onboarding = '/onboarding';
  static const login = '/login';
  static const register = '/register';
  static const forgotPassword = '/forgot-password';
  static const home = '/home';
  static const serviceList = '/services';
  static const serviceDetail = '/services/:id';
  static const booking = '/booking';
  static const bookingHistory = '/booking/history';
  static const payment = '/payment';
  static const profile = '/profile';
  static const editProfile = '/profile/edit';
}

class AppRouter {
  AppRouter._();

  static final GoRouter router = GoRouter(
    initialLocation: Routes.splash,
    debugLogDiagnostics: true,
    errorBuilder: (context, state) => Scaffold(
      body: Center(child: Text('Page not found: ${state.uri}')),
    ),
    routes: [
      GoRoute(
        path: Routes.splash,
        name: 'splash',
        builder: (context, state) => const SplashPage(),
      ),
      GoRoute(
        path: Routes.onboarding,
        name: 'onboarding',
        builder: (context, state) => const OnboardingPage(),
      ),
      GoRoute(
        path: Routes.login,
        name: 'login',
        builder: (context, state) => const LoginPage(),
      ),
      GoRoute(
        path: Routes.register,
        name: 'register',
        builder: (context, state) => const RegisterPage(),
      ),
      GoRoute(
        path: Routes.forgotPassword,
        name: 'forgotPassword',
        builder: (context, state) => const ForgotPasswordPage(),
      ),
      GoRoute(
        path: Routes.home,
        name: 'home',
        builder: (context, state) => const HomePage(),
      ),
      GoRoute(
        path: Routes.serviceList,
        name: 'serviceList',
        builder: (context, state) => const ServiceListPage(),
      ),
      GoRoute(
        path: Routes.serviceDetail,
        name: 'serviceDetail',
        builder: (context, state) {
          final id = state.pathParameters['id'] ?? '';
          return ServiceDetailPage(serviceId: id);
        },
      ),
      GoRoute(
        path: Routes.booking,
        name: 'booking',
        builder: (context, state) {
          final serviceId = state.uri.queryParameters['serviceId'] ?? '';
          return BookingPage(serviceId: serviceId);
        },
      ),
      GoRoute(
        path: Routes.bookingHistory,
        name: 'bookingHistory',
        builder: (context, state) => const BookingHistoryPage(),
      ),
      GoRoute(
        path: Routes.payment,
        name: 'payment',
        builder: (context, state) {
          final bookingId = state.uri.queryParameters['bookingId'] ?? '';
          return PaymentPage(bookingId: bookingId);
        },
      ),
      GoRoute(
        path: Routes.profile,
        name: 'profile',
        builder: (context, state) => const ProfilePage(),
      ),
      GoRoute(
        path: Routes.editProfile,
        name: 'editProfile',
        builder: (context, state) => const EditProfilePage(),
      ),
    ],
  );
}
