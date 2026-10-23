import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:intl/intl.dart' as intl;

import 'app_localizations_en.dart';
import 'app_localizations_hi.dart';

// ignore_for_file: type=lint

/// Callers can lookup localized strings with an instance of AppLocalizations
/// returned by `AppLocalizations.of(context)`.
///
/// Applications need to include `AppLocalizations.delegate()` in their app's
/// `localizationDelegates` list, and the locales they support in the app's
/// `supportedLocales` list. For example:
///
/// ```dart
/// import 'l10n/app_localizations.dart';
///
/// return MaterialApp(
///   localizationsDelegates: AppLocalizations.localizationsDelegates,
///   supportedLocales: AppLocalizations.supportedLocales,
///   home: MyApplicationHome(),
/// );
/// ```
///
/// ## Update pubspec.yaml
///
/// Please make sure to update your pubspec.yaml to include the following
/// packages:
///
/// ```yaml
/// dependencies:
///   # Internationalization support.
///   flutter_localizations:
///     sdk: flutter
///   intl: any # Use the pinned version from flutter_localizations
///
///   # Rest of dependencies
/// ```
///
/// ## iOS Applications
///
/// iOS applications define key application metadata, including supported
/// locales, in an Info.plist file that is built into the application bundle.
/// To configure the locales supported by your app, you’ll need to edit this
/// file.
///
/// First, open your project’s ios/Runner.xcworkspace Xcode workspace file.
/// Then, in the Project Navigator, open the Info.plist file under the Runner
/// project’s Runner folder.
///
/// Next, select the Information Property List item, select Add Item from the
/// Editor menu, then select Localizations from the pop-up menu.
///
/// Select and expand the newly-created Localizations item then, for each
/// locale your application supports, add a new item and select the locale
/// you wish to add from the pop-up menu in the Value field. This list should
/// be consistent with the languages listed in the AppLocalizations.supportedLocales
/// property.
abstract class AppLocalizations {
  AppLocalizations(String locale)
      : localeName = intl.Intl.canonicalizedLocale(locale.toString());

  final String localeName;

  static AppLocalizations? of(BuildContext context) {
    return Localizations.of<AppLocalizations>(context, AppLocalizations);
  }

  static const LocalizationsDelegate<AppLocalizations> delegate =
      _AppLocalizationsDelegate();

  /// A list of this localizations delegate along with the default localizations
  /// delegates.
  ///
  /// Returns a list of localizations delegates containing this delegate along with
  /// GlobalMaterialLocalizations.delegate, GlobalCupertinoLocalizations.delegate,
  /// and GlobalWidgetsLocalizations.delegate.
  ///
  /// Additional delegates can be added by appending to this list in
  /// MaterialApp. This list does not have to be used at all if a custom list
  /// of delegates is preferred or required.
  static const List<LocalizationsDelegate<dynamic>> localizationsDelegates =
      <LocalizationsDelegate<dynamic>>[
    delegate,
    GlobalMaterialLocalizations.delegate,
    GlobalCupertinoLocalizations.delegate,
    GlobalWidgetsLocalizations.delegate,
  ];

  /// A list of this localizations delegate's supported locales.
  static const List<Locale> supportedLocales = <Locale>[
    Locale('en'),
    Locale('hi')
  ];

  /// No description provided for @appTitle.
  ///
  /// In en, this message translates to:
  /// **'AlakhService'**
  String get appTitle;

  /// No description provided for @cancel.
  ///
  /// In en, this message translates to:
  /// **'Cancel'**
  String get cancel;

  /// No description provided for @save.
  ///
  /// In en, this message translates to:
  /// **'Save'**
  String get save;

  /// No description provided for @delete.
  ///
  /// In en, this message translates to:
  /// **'Delete'**
  String get delete;

  /// No description provided for @done.
  ///
  /// In en, this message translates to:
  /// **'Done'**
  String get done;

  /// No description provided for @retry.
  ///
  /// In en, this message translates to:
  /// **'Retry'**
  String get retry;

  /// No description provided for @tryAgain.
  ///
  /// In en, this message translates to:
  /// **'Try again'**
  String get tryAgain;

  /// No description provided for @tryAgainButton.
  ///
  /// In en, this message translates to:
  /// **'Try Again'**
  String get tryAgainButton;

  /// No description provided for @send.
  ///
  /// In en, this message translates to:
  /// **'Send'**
  String get send;

  /// No description provided for @submit.
  ///
  /// In en, this message translates to:
  /// **'Submit'**
  String get submit;

  /// No description provided for @notNow.
  ///
  /// In en, this message translates to:
  /// **'Not now'**
  String get notNow;

  /// No description provided for @remove.
  ///
  /// In en, this message translates to:
  /// **'Remove'**
  String get remove;

  /// No description provided for @apply.
  ///
  /// In en, this message translates to:
  /// **'Apply'**
  String get apply;

  /// No description provided for @loadingMore.
  ///
  /// In en, this message translates to:
  /// **'Loading…'**
  String get loadingMore;

  /// No description provided for @somethingWentWrong.
  ///
  /// In en, this message translates to:
  /// **'Something went wrong'**
  String get somethingWentWrong;

  /// No description provided for @showPassword.
  ///
  /// In en, this message translates to:
  /// **'Show password'**
  String get showPassword;

  /// No description provided for @hidePassword.
  ///
  /// In en, this message translates to:
  /// **'Hide password'**
  String get hidePassword;

  /// No description provided for @requiredField.
  ///
  /// In en, this message translates to:
  /// **'Required'**
  String get requiredField;

  /// No description provided for @today.
  ///
  /// In en, this message translates to:
  /// **'Today'**
  String get today;

  /// No description provided for @tomorrow.
  ///
  /// In en, this message translates to:
  /// **'Tomorrow'**
  String get tomorrow;

  /// No description provided for @yesterday.
  ///
  /// In en, this message translates to:
  /// **'Yesterday'**
  String get yesterday;

  /// No description provided for @midnight.
  ///
  /// In en, this message translates to:
  /// **'midnight'**
  String get midnight;

  /// No description provided for @navHome.
  ///
  /// In en, this message translates to:
  /// **'Home'**
  String get navHome;

  /// No description provided for @navServices.
  ///
  /// In en, this message translates to:
  /// **'Services'**
  String get navServices;

  /// No description provided for @navBookings.
  ///
  /// In en, this message translates to:
  /// **'Bookings'**
  String get navBookings;

  /// No description provided for @navJobs.
  ///
  /// In en, this message translates to:
  /// **'Jobs'**
  String get navJobs;

  /// No description provided for @navProfile.
  ///
  /// In en, this message translates to:
  /// **'Profile'**
  String get navProfile;

  /// No description provided for @errorTimeout.
  ///
  /// In en, this message translates to:
  /// **'The server took too long to respond. Please try again.'**
  String get errorTimeout;

  /// No description provided for @errorCannotReach.
  ///
  /// In en, this message translates to:
  /// **'Cannot reach AlakhService. Check your connection.'**
  String get errorCannotReach;

  /// No description provided for @errorRequestFailed.
  ///
  /// In en, this message translates to:
  /// **'Request failed ({status})'**
  String errorRequestFailed(int status);

  /// No description provided for @errorGeneric.
  ///
  /// In en, this message translates to:
  /// **'Something went wrong. Please try again.'**
  String get errorGeneric;

  /// No description provided for @errorNoInternet.
  ///
  /// In en, this message translates to:
  /// **'No internet connection'**
  String get errorNoInternet;

  /// No description provided for @vPhoneRequired.
  ///
  /// In en, this message translates to:
  /// **'Phone number is required'**
  String get vPhoneRequired;

  /// No description provided for @vPhoneInvalid.
  ///
  /// In en, this message translates to:
  /// **'Enter a valid phone number'**
  String get vPhoneInvalid;

  /// No description provided for @vMobileRequired.
  ///
  /// In en, this message translates to:
  /// **'Mobile number is required'**
  String get vMobileRequired;

  /// No description provided for @vMobileInvalid.
  ///
  /// In en, this message translates to:
  /// **'Enter a valid 10-digit mobile number'**
  String get vMobileInvalid;

  /// No description provided for @vPhoneOrEmailRequired.
  ///
  /// In en, this message translates to:
  /// **'Enter your phone number or email'**
  String get vPhoneOrEmailRequired;

  /// No description provided for @vPhoneOrEmailInvalid.
  ///
  /// In en, this message translates to:
  /// **'Enter a valid phone number or email'**
  String get vPhoneOrEmailInvalid;

  /// No description provided for @vPasswordRequired.
  ///
  /// In en, this message translates to:
  /// **'Password is required'**
  String get vPasswordRequired;

  /// No description provided for @vPasswordRules.
  ///
  /// In en, this message translates to:
  /// **'At least 8 characters, with a capital letter and a number'**
  String get vPasswordRules;

  /// No description provided for @vEmailRequired.
  ///
  /// In en, this message translates to:
  /// **'Email is required'**
  String get vEmailRequired;

  /// No description provided for @vEmailInvalid.
  ///
  /// In en, this message translates to:
  /// **'Enter a valid email address'**
  String get vEmailInvalid;

  /// No description provided for @vPasswordShort.
  ///
  /// In en, this message translates to:
  /// **'Password must be at least 8 characters'**
  String get vPasswordShort;

  /// No description provided for @vPasswordUpper.
  ///
  /// In en, this message translates to:
  /// **'Include at least one uppercase letter'**
  String get vPasswordUpper;

  /// No description provided for @vPasswordNumber.
  ///
  /// In en, this message translates to:
  /// **'Include at least one number'**
  String get vPasswordNumber;

  /// No description provided for @vOtpRequired.
  ///
  /// In en, this message translates to:
  /// **'OTP is required'**
  String get vOtpRequired;

  /// No description provided for @vOtpInvalid.
  ///
  /// In en, this message translates to:
  /// **'Enter a valid 6-digit OTP'**
  String get vOtpInvalid;

  /// No description provided for @vNameRequired.
  ///
  /// In en, this message translates to:
  /// **'Name is required'**
  String get vNameRequired;

  /// No description provided for @vNameShort.
  ///
  /// In en, this message translates to:
  /// **'Name must be at least 2 characters'**
  String get vNameShort;

  /// No description provided for @vFieldRequired.
  ///
  /// In en, this message translates to:
  /// **'This field is required'**
  String get vFieldRequired;

  /// No description provided for @vFieldRequiredNamed.
  ///
  /// In en, this message translates to:
  /// **'{field} is required'**
  String vFieldRequiredNamed(String field);

  /// No description provided for @vFieldMinLength.
  ///
  /// In en, this message translates to:
  /// **'{field} must be at least {min} characters'**
  String vFieldMinLength(String field, String min);

  /// No description provided for @vConfirmPassword.
  ///
  /// In en, this message translates to:
  /// **'Please confirm your password'**
  String get vConfirmPassword;

  /// No description provided for @vPasswordsDontMatch.
  ///
  /// In en, this message translates to:
  /// **'Passwords do not match'**
  String get vPasswordsDontMatch;

  /// No description provided for @loginWelcome.
  ///
  /// In en, this message translates to:
  /// **'Welcome Back'**
  String get loginWelcome;

  /// No description provided for @loginSubtitle.
  ///
  /// In en, this message translates to:
  /// **'Sign in to book, track and pay for your services'**
  String get loginSubtitle;

  /// No description provided for @loginPhoneOrEmail.
  ///
  /// In en, this message translates to:
  /// **'Phone or email'**
  String get loginPhoneOrEmail;

  /// No description provided for @loginPhoneOrEmailHint.
  ///
  /// In en, this message translates to:
  /// **'98765 43210 or you@example.com'**
  String get loginPhoneOrEmailHint;

  /// No description provided for @password.
  ///
  /// In en, this message translates to:
  /// **'Password'**
  String get password;

  /// No description provided for @loginPasswordHint.
  ///
  /// In en, this message translates to:
  /// **'Enter your password'**
  String get loginPasswordHint;

  /// No description provided for @loginForgot.
  ///
  /// In en, this message translates to:
  /// **'Forgot Password?'**
  String get loginForgot;

  /// No description provided for @loginButton.
  ///
  /// In en, this message translates to:
  /// **'Login'**
  String get loginButton;

  /// No description provided for @loginWithOtp.
  ///
  /// In en, this message translates to:
  /// **'Login with OTP instead'**
  String get loginWithOtp;

  /// No description provided for @loginNoAccount.
  ///
  /// In en, this message translates to:
  /// **'Don\'t have an account?'**
  String get loginNoAccount;

  /// No description provided for @loginRegister.
  ///
  /// In en, this message translates to:
  /// **'Register'**
  String get loginRegister;

  /// No description provided for @registerTitle.
  ///
  /// In en, this message translates to:
  /// **'Create Account'**
  String get registerTitle;

  /// No description provided for @registerHeading.
  ///
  /// In en, this message translates to:
  /// **'Join AlakhService'**
  String get registerHeading;

  /// No description provided for @registerSubtitle.
  ///
  /// In en, this message translates to:
  /// **'Create your account to get started'**
  String get registerSubtitle;

  /// No description provided for @fullName.
  ///
  /// In en, this message translates to:
  /// **'Full Name'**
  String get fullName;

  /// No description provided for @registerNameHint.
  ///
  /// In en, this message translates to:
  /// **'e.g. Priya Sharma'**
  String get registerNameHint;

  /// No description provided for @mobileNumber.
  ///
  /// In en, this message translates to:
  /// **'Mobile Number'**
  String get mobileNumber;

  /// No description provided for @registerPasswordHint.
  ///
  /// In en, this message translates to:
  /// **'Choose a password'**
  String get registerPasswordHint;

  /// No description provided for @registerCodeNote.
  ///
  /// In en, this message translates to:
  /// **'We will text a verification code to this number.'**
  String get registerCodeNote;

  /// No description provided for @registerButton.
  ///
  /// In en, this message translates to:
  /// **'Create account'**
  String get registerButton;

  /// No description provided for @registerHaveAccount.
  ///
  /// In en, this message translates to:
  /// **'Already have an account?'**
  String get registerHaveAccount;

  /// No description provided for @otpTitleLogin.
  ///
  /// In en, this message translates to:
  /// **'Login with OTP'**
  String get otpTitleLogin;

  /// No description provided for @otpTitleVerifyPhone.
  ///
  /// In en, this message translates to:
  /// **'Verify your phone'**
  String get otpTitleVerifyPhone;

  /// No description provided for @otpTitleVerifyEmail.
  ///
  /// In en, this message translates to:
  /// **'Verify your email'**
  String get otpTitleVerifyEmail;

  /// No description provided for @otpResent.
  ///
  /// In en, this message translates to:
  /// **'A new code is on its way'**
  String get otpResent;

  /// No description provided for @otpEnterCode.
  ///
  /// In en, this message translates to:
  /// **'Enter the code'**
  String get otpEnterCode;

  /// No description provided for @otpSentTo.
  ///
  /// In en, this message translates to:
  /// **'We sent a {length}-digit code to {destination}.'**
  String otpSentTo(int length, String destination);

  /// No description provided for @otpWrongPhone.
  ///
  /// In en, this message translates to:
  /// **'Wrong phone? Change it'**
  String get otpWrongPhone;

  /// No description provided for @otpWrongEmail.
  ///
  /// In en, this message translates to:
  /// **'Wrong email? Change it'**
  String get otpWrongEmail;

  /// No description provided for @otpFieldLabel.
  ///
  /// In en, this message translates to:
  /// **'One-time code'**
  String get otpFieldLabel;

  /// No description provided for @otpVerifyLogin.
  ///
  /// In en, this message translates to:
  /// **'Verify and login'**
  String get otpVerifyLogin;

  /// No description provided for @otpVerify.
  ///
  /// In en, this message translates to:
  /// **'Verify'**
  String get otpVerify;

  /// No description provided for @otpResendIn.
  ///
  /// In en, this message translates to:
  /// **'Didn\'t get it? You can resend in {seconds}s'**
  String otpResendIn(int seconds);

  /// No description provided for @otpResend.
  ///
  /// In en, this message translates to:
  /// **'Didn\'t get it? Resend code'**
  String get otpResend;

  /// No description provided for @forgotTitle.
  ///
  /// In en, this message translates to:
  /// **'Forgot Password'**
  String get forgotTitle;

  /// No description provided for @resetPassword.
  ///
  /// In en, this message translates to:
  /// **'Reset Password'**
  String get resetPassword;

  /// No description provided for @forgotIntro.
  ///
  /// In en, this message translates to:
  /// **'Enter the phone number or email on your account and we\'ll send you a code.'**
  String get forgotIntro;

  /// No description provided for @forgotEnterCode.
  ///
  /// In en, this message translates to:
  /// **'Enter the code we sent to {destination} and choose a new password.'**
  String forgotEnterCode(String destination);

  /// No description provided for @forgotDifferent.
  ///
  /// In en, this message translates to:
  /// **'Use a different phone or email'**
  String get forgotDifferent;

  /// No description provided for @code.
  ///
  /// In en, this message translates to:
  /// **'Code'**
  String get code;

  /// No description provided for @codeHint.
  ///
  /// In en, this message translates to:
  /// **'6-digit code'**
  String get codeHint;

  /// No description provided for @newPassword.
  ///
  /// In en, this message translates to:
  /// **'New Password'**
  String get newPassword;

  /// No description provided for @newPasswordHint.
  ///
  /// In en, this message translates to:
  /// **'Choose a new password'**
  String get newPasswordHint;

  /// No description provided for @sendCode.
  ///
  /// In en, this message translates to:
  /// **'Send Code'**
  String get sendCode;

  /// No description provided for @passwordChanged.
  ///
  /// In en, this message translates to:
  /// **'Password Changed'**
  String get passwordChanged;

  /// No description provided for @passwordChangedBody.
  ///
  /// In en, this message translates to:
  /// **'Sign in with your new password. Other devices have been signed out.'**
  String get passwordChangedBody;

  /// No description provided for @backToLogin.
  ///
  /// In en, this message translates to:
  /// **'Back to Login'**
  String get backToLogin;

  /// No description provided for @greetingMorning.
  ///
  /// In en, this message translates to:
  /// **'Good morning'**
  String get greetingMorning;

  /// No description provided for @greetingAfternoon.
  ///
  /// In en, this message translates to:
  /// **'Good afternoon'**
  String get greetingAfternoon;

  /// No description provided for @greetingEvening.
  ///
  /// In en, this message translates to:
  /// **'Good evening'**
  String get greetingEvening;

  /// No description provided for @homeFindService.
  ///
  /// In en, this message translates to:
  /// **'Find a Service'**
  String get homeFindService;

  /// No description provided for @searchHint.
  ///
  /// In en, this message translates to:
  /// **'Search haircut, AC repair, doctor…'**
  String get searchHint;

  /// No description provided for @searchServicesHint.
  ///
  /// In en, this message translates to:
  /// **'Search services...'**
  String get searchServicesHint;

  /// No description provided for @homeOurServices.
  ///
  /// In en, this message translates to:
  /// **'Our Services'**
  String get homeOurServices;

  /// No description provided for @homePopular.
  ///
  /// In en, this message translates to:
  /// **'Popular Services'**
  String get homePopular;

  /// No description provided for @homeLoadFailed.
  ///
  /// In en, this message translates to:
  /// **'Could not load services.'**
  String get homeLoadFailed;

  /// No description provided for @homeNoServices.
  ///
  /// In en, this message translates to:
  /// **'No services listed yet.'**
  String get homeNoServices;

  /// No description provided for @notifications.
  ///
  /// In en, this message translates to:
  /// **'Notifications'**
  String get notifications;

  /// No description provided for @notificationsUnread.
  ///
  /// In en, this message translates to:
  /// **'Notifications, {count} unread'**
  String notificationsUnread(int count);

  /// No description provided for @catHaircut.
  ///
  /// In en, this message translates to:
  /// **'Haircut'**
  String get catHaircut;

  /// No description provided for @catBeauty.
  ///
  /// In en, this message translates to:
  /// **'Beauty Parlour'**
  String get catBeauty;

  /// No description provided for @catDoctor.
  ///
  /// In en, this message translates to:
  /// **'Doctor'**
  String get catDoctor;

  /// No description provided for @catOffice.
  ///
  /// In en, this message translates to:
  /// **'Office Visits'**
  String get catOffice;

  /// No description provided for @catCar.
  ///
  /// In en, this message translates to:
  /// **'Car Repair'**
  String get catCar;

  /// No description provided for @catBike.
  ///
  /// In en, this message translates to:
  /// **'Bike Repair'**
  String get catBike;

  /// No description provided for @catDevices.
  ///
  /// In en, this message translates to:
  /// **'Laptop & Phone'**
  String get catDevices;

  /// No description provided for @catAc.
  ///
  /// In en, this message translates to:
  /// **'AC Repair'**
  String get catAc;

  /// No description provided for @catCleaning.
  ///
  /// In en, this message translates to:
  /// **'Cleaning'**
  String get catCleaning;

  /// No description provided for @catPlumbing.
  ///
  /// In en, this message translates to:
  /// **'Plumbing'**
  String get catPlumbing;

  /// No description provided for @catElectrical.
  ///
  /// In en, this message translates to:
  /// **'Electrical'**
  String get catElectrical;

  /// No description provided for @catCarpentry.
  ///
  /// In en, this message translates to:
  /// **'Carpentry'**
  String get catCarpentry;

  /// No description provided for @catPest.
  ///
  /// In en, this message translates to:
  /// **'Pest Control'**
  String get catPest;

  /// No description provided for @catHandyman.
  ///
  /// In en, this message translates to:
  /// **'Handyman'**
  String get catHandyman;

  /// No description provided for @bannerTrack.
  ///
  /// In en, this message translates to:
  /// **'Track your\nbookings'**
  String get bannerTrack;

  /// No description provided for @bannerMyBookings.
  ///
  /// In en, this message translates to:
  /// **'My bookings'**
  String get bannerMyBookings;

  /// No description provided for @bannerSemantics.
  ///
  /// In en, this message translates to:
  /// **'Track your bookings. My bookings'**
  String get bannerSemantics;

  /// No description provided for @nextBooking.
  ///
  /// In en, this message translates to:
  /// **'Your next booking'**
  String get nextBooking;

  /// No description provided for @nextBookingSemantics.
  ///
  /// In en, this message translates to:
  /// **'Your next booking: {service}, {when}, {statusText}. Open my bookings'**
  String nextBookingSemantics(String service, String when, String statusText);

  /// No description provided for @servicesTitle.
  ///
  /// In en, this message translates to:
  /// **'Services'**
  String get servicesTitle;

  /// No description provided for @clearSearch.
  ///
  /// In en, this message translates to:
  /// **'Clear search'**
  String get clearSearch;

  /// No description provided for @loadingServices.
  ///
  /// In en, this message translates to:
  /// **'Loading services...'**
  String get loadingServices;

  /// No description provided for @noServicesListed.
  ///
  /// In en, this message translates to:
  /// **'No services listed yet'**
  String get noServicesListed;

  /// No description provided for @nothingFound.
  ///
  /// In en, this message translates to:
  /// **'Nothing found for \"{query}\"'**
  String nothingFound(String query);

  /// No description provided for @pullToCheck.
  ///
  /// In en, this message translates to:
  /// **'Pull down to check again.'**
  String get pullToCheck;

  /// No description provided for @tryDifferentWord.
  ///
  /// In en, this message translates to:
  /// **'Try a shorter or different word.'**
  String get tryDifferentWord;

  /// No description provided for @showAllServices.
  ///
  /// In en, this message translates to:
  /// **'Show all services'**
  String get showAllServices;

  /// No description provided for @modeHomeVisit.
  ///
  /// In en, this message translates to:
  /// **'Home visit'**
  String get modeHomeVisit;

  /// No description provided for @modePickupDrop.
  ///
  /// In en, this message translates to:
  /// **'Pickup & drop'**
  String get modePickupDrop;

  /// No description provided for @modeAtShop.
  ///
  /// In en, this message translates to:
  /// **'At shop'**
  String get modeAtShop;

  /// No description provided for @unavailable.
  ///
  /// In en, this message translates to:
  /// **'Unavailable'**
  String get unavailable;

  /// No description provided for @minutesShort.
  ///
  /// In en, this message translates to:
  /// **'{minutes} min'**
  String minutesShort(int minutes);

  /// No description provided for @ratingNew.
  ///
  /// In en, this message translates to:
  /// **'New'**
  String get ratingNew;

  /// No description provided for @ratingNewSemantics.
  ///
  /// In en, this message translates to:
  /// **'New, no reviews yet'**
  String get ratingNewSemantics;

  /// No description provided for @ratedSemantics.
  ///
  /// In en, this message translates to:
  /// **'Rated {rating} out of 5 from {count, plural, =1{1 review} other{{count} reviews}}'**
  String ratedSemantics(String rating, int count);

  /// No description provided for @starsLabel.
  ///
  /// In en, this message translates to:
  /// **'{rating} out of 5 stars'**
  String starsLabel(String rating);

  /// No description provided for @reviewsCount.
  ///
  /// In en, this message translates to:
  /// **'{count, plural, =1{1 review} other{{count} reviews}}'**
  String reviewsCount(int count);

  /// No description provided for @serviceNotTaking.
  ///
  /// In en, this message translates to:
  /// **'This service isn\'t taking bookings right now.'**
  String get serviceNotTaking;

  /// No description provided for @priceFrom.
  ///
  /// In en, this message translates to:
  /// **'From'**
  String get priceFrom;

  /// No description provided for @bookNow.
  ///
  /// In en, this message translates to:
  /// **'Book Now'**
  String get bookNow;

  /// No description provided for @aboutMinutes.
  ///
  /// In en, this message translates to:
  /// **'About {minutes} min'**
  String aboutMinutes(int minutes);

  /// No description provided for @howYouCanGetIt.
  ///
  /// In en, this message translates to:
  /// **'How you can get it'**
  String get howYouCanGetIt;

  /// No description provided for @modeAtYourPlace.
  ///
  /// In en, this message translates to:
  /// **'At your place'**
  String get modeAtYourPlace;

  /// No description provided for @modeAtTheShop.
  ///
  /// In en, this message translates to:
  /// **'At the shop'**
  String get modeAtTheShop;

  /// No description provided for @aboutService.
  ///
  /// In en, this message translates to:
  /// **'About this service'**
  String get aboutService;

  /// No description provided for @noDescription.
  ///
  /// In en, this message translates to:
  /// **'The shop has not added a description yet.'**
  String get noDescription;

  /// No description provided for @joinQueue.
  ///
  /// In en, this message translates to:
  /// **'Walk in now: join the queue'**
  String get joinQueue;

  /// No description provided for @joinQueueNote.
  ///
  /// In en, this message translates to:
  /// **'No appointment needed: we\'ll tell you your place and when it\'s your turn.'**
  String get joinQueueNote;

  /// No description provided for @howToGetThere.
  ///
  /// In en, this message translates to:
  /// **'How to get there'**
  String get howToGetThere;

  /// No description provided for @hoursOpenCloses.
  ///
  /// In en, this message translates to:
  /// **'Open now · closes {time}'**
  String hoursOpenCloses(String time);

  /// No description provided for @hoursClosedOpens.
  ///
  /// In en, this message translates to:
  /// **'Closed · opens {time}'**
  String hoursClosedOpens(String time);

  /// No description provided for @hoursClosedOpensTomorrow.
  ///
  /// In en, this message translates to:
  /// **'Closed · opens tomorrow {time}'**
  String hoursClosedOpensTomorrow(String time);

  /// No description provided for @hoursClosedOpensDay.
  ///
  /// In en, this message translates to:
  /// **'Closed · opens {day} {time}'**
  String hoursClosedOpensDay(String day, String time);

  /// No description provided for @hoursClosed.
  ///
  /// In en, this message translates to:
  /// **'Closed'**
  String get hoursClosed;

  /// No description provided for @bookServiceTitle.
  ///
  /// In en, this message translates to:
  /// **'Book Service'**
  String get bookServiceTitle;

  /// No description provided for @howWouldYouLikeIt.
  ///
  /// In en, this message translates to:
  /// **'How would you like it?'**
  String get howWouldYouLikeIt;

  /// No description provided for @whenQuestion.
  ///
  /// In en, this message translates to:
  /// **'When?'**
  String get whenQuestion;

  /// No description provided for @timesLoadFailed.
  ///
  /// In en, this message translates to:
  /// **'Couldn\'t load the times for this day'**
  String get timesLoadFailed;

  /// No description provided for @findingTimes.
  ///
  /// In en, this message translates to:
  /// **'Finding free times…'**
  String get findingTimes;

  /// No description provided for @partMorning.
  ///
  /// In en, this message translates to:
  /// **'Morning'**
  String get partMorning;

  /// No description provided for @partAfternoon.
  ///
  /// In en, this message translates to:
  /// **'Afternoon'**
  String get partAfternoon;

  /// No description provided for @partEvening.
  ///
  /// In en, this message translates to:
  /// **'Evening'**
  String get partEvening;

  /// No description provided for @pickATime.
  ///
  /// In en, this message translates to:
  /// **'Pick a time'**
  String get pickATime;

  /// No description provided for @noMoreTimesToday.
  ///
  /// In en, this message translates to:
  /// **'No more times today — try another day'**
  String get noMoreTimesToday;

  /// No description provided for @closedOnDay.
  ///
  /// In en, this message translates to:
  /// **'Closed on this day'**
  String get closedOnDay;

  /// No description provided for @closedOnDayNote.
  ///
  /// In en, this message translates to:
  /// **'Closed on this day ({note})'**
  String closedOnDayNote(String note);

  /// No description provided for @fullyBooked.
  ///
  /// In en, this message translates to:
  /// **'Fully booked — try another day'**
  String get fullyBooked;

  /// No description provided for @noTimesOnDay.
  ///
  /// In en, this message translates to:
  /// **'No times on this day — try another day'**
  String get noTimesOnDay;

  /// No description provided for @collectFrom.
  ///
  /// In en, this message translates to:
  /// **'Collect from'**
  String get collectFrom;

  /// No description provided for @whereShouldWeCome.
  ///
  /// In en, this message translates to:
  /// **'Where should we come?'**
  String get whereShouldWeCome;

  /// No description provided for @noSavedAddress.
  ///
  /// In en, this message translates to:
  /// **'You have no saved address yet.'**
  String get noSavedAddress;

  /// No description provided for @addAddress.
  ///
  /// In en, this message translates to:
  /// **'Add address'**
  String get addAddress;

  /// No description provided for @savedAddress.
  ///
  /// In en, this message translates to:
  /// **'Saved address'**
  String get savedAddress;

  /// No description provided for @addAnotherAddress.
  ///
  /// In en, this message translates to:
  /// **'Add another address'**
  String get addAnotherAddress;

  /// No description provided for @whatToCollect.
  ///
  /// In en, this message translates to:
  /// **'What should we collect?'**
  String get whatToCollect;

  /// No description provided for @whatToCollectHint.
  ///
  /// In en, this message translates to:
  /// **'e.g. Honda Activa, brakes squeaking · Dell laptop, cracked screen'**
  String get whatToCollectHint;

  /// No description provided for @whatToCollectError.
  ///
  /// In en, this message translates to:
  /// **'Tell us what to collect and what is wrong'**
  String get whatToCollectError;

  /// No description provided for @notesOptional.
  ///
  /// In en, this message translates to:
  /// **'Notes (optional)'**
  String get notesOptional;

  /// No description provided for @notesHint.
  ///
  /// In en, this message translates to:
  /// **'Any special instructions...'**
  String get notesHint;

  /// No description provided for @couponOptional.
  ///
  /// In en, this message translates to:
  /// **'Coupon code (optional)'**
  String get couponOptional;

  /// No description provided for @couponHint.
  ///
  /// In en, this message translates to:
  /// **'e.g. WELCOME10'**
  String get couponHint;

  /// No description provided for @checking.
  ///
  /// In en, this message translates to:
  /// **'Checking…'**
  String get checking;

  /// No description provided for @homeVisitFee.
  ///
  /// In en, this message translates to:
  /// **'Home visit fee'**
  String get homeVisitFee;

  /// No description provided for @pickupDropFee.
  ///
  /// In en, this message translates to:
  /// **'Pickup & drop fee'**
  String get pickupDropFee;

  /// No description provided for @snackPickTime.
  ///
  /// In en, this message translates to:
  /// **'Pick a time for your booking'**
  String get snackPickTime;

  /// No description provided for @snackAddAddress.
  ///
  /// In en, this message translates to:
  /// **'Add the address we should come to'**
  String get snackAddAddress;

  /// No description provided for @snackFillDetails.
  ///
  /// In en, this message translates to:
  /// **'Please fill in the highlighted details'**
  String get snackFillDetails;

  /// No description provided for @bookingRequested.
  ///
  /// In en, this message translates to:
  /// **'Booking requested'**
  String get bookingRequested;

  /// No description provided for @bookingNumber.
  ///
  /// In en, this message translates to:
  /// **'Booking #{number}'**
  String bookingNumber(String number);

  /// No description provided for @bookingRequestedBody.
  ///
  /// In en, this message translates to:
  /// **'The shop will confirm it shortly. We\'ll notify you, and you can pay once it\'s confirmed.'**
  String get bookingRequestedBody;

  /// No description provided for @viewMyBookings.
  ///
  /// In en, this message translates to:
  /// **'View my bookings'**
  String get viewMyBookings;

  /// No description provided for @couponApplied.
  ///
  /// In en, this message translates to:
  /// **'{code} applied: {percent}% off, you save {saving}'**
  String couponApplied(String code, String percent, String saving);

  /// No description provided for @priceDetails.
  ///
  /// In en, this message translates to:
  /// **'Price details'**
  String get priceDetails;

  /// No description provided for @priceService.
  ///
  /// In en, this message translates to:
  /// **'Service'**
  String get priceService;

  /// No description provided for @priceCoupon.
  ///
  /// In en, this message translates to:
  /// **'Coupon {code}'**
  String priceCoupon(String code);

  /// No description provided for @total.
  ///
  /// In en, this message translates to:
  /// **'Total'**
  String get total;

  /// No description provided for @payLaterNote.
  ///
  /// In en, this message translates to:
  /// **'Nothing to pay now. Pay online or in cash once the shop confirms.'**
  String get payLaterNote;

  /// No description provided for @confirmBooking.
  ///
  /// In en, this message translates to:
  /// **'Confirm Booking'**
  String get confirmBooking;

  /// No description provided for @chooseDayTime.
  ///
  /// In en, this message translates to:
  /// **'Choose a day and time below'**
  String get chooseDayTime;

  /// No description provided for @modeChoiceAtHome.
  ///
  /// In en, this message translates to:
  /// **'At my place'**
  String get modeChoiceAtHome;

  /// No description provided for @modeChoiceAtShop.
  ///
  /// In en, this message translates to:
  /// **'Visit the shop'**
  String get modeChoiceAtShop;

  /// No description provided for @explainAtHome.
  ///
  /// In en, this message translates to:
  /// **'A professional comes to your address at the time you choose.'**
  String get explainAtHome;

  /// No description provided for @explainPickup.
  ///
  /// In en, this message translates to:
  /// **'We collect your item from your address, service it and bring it back. You\'ll be told at each step.'**
  String get explainPickup;

  /// No description provided for @explainAtShop.
  ///
  /// In en, this message translates to:
  /// **'You go to the shop at the time you choose. See \"How to get there\" on your booking.'**
  String get explainAtShop;

  /// No description provided for @myBookings.
  ///
  /// In en, this message translates to:
  /// **'My Bookings'**
  String get myBookings;

  /// No description provided for @statusPending.
  ///
  /// In en, this message translates to:
  /// **'Awaiting confirmation'**
  String get statusPending;

  /// No description provided for @statusConfirmed.
  ///
  /// In en, this message translates to:
  /// **'Confirmed'**
  String get statusConfirmed;

  /// No description provided for @statusAssigned.
  ///
  /// In en, this message translates to:
  /// **'Provider assigned'**
  String get statusAssigned;

  /// No description provided for @statusEnRoute.
  ///
  /// In en, this message translates to:
  /// **'Provider on the way'**
  String get statusEnRoute;

  /// No description provided for @statusPickedUp.
  ///
  /// In en, this message translates to:
  /// **'Item picked up'**
  String get statusPickedUp;

  /// No description provided for @statusInProgress.
  ///
  /// In en, this message translates to:
  /// **'In progress'**
  String get statusInProgress;

  /// No description provided for @statusOutForDelivery.
  ///
  /// In en, this message translates to:
  /// **'On its way back'**
  String get statusOutForDelivery;

  /// No description provided for @statusCompleted.
  ///
  /// In en, this message translates to:
  /// **'Completed'**
  String get statusCompleted;

  /// No description provided for @statusCancelled.
  ///
  /// In en, this message translates to:
  /// **'Cancelled'**
  String get statusCancelled;

  /// No description provided for @statusDisputed.
  ///
  /// In en, this message translates to:
  /// **'Problem reported'**
  String get statusDisputed;

  /// No description provided for @statusRefunded.
  ///
  /// In en, this message translates to:
  /// **'Refunded'**
  String get statusRefunded;

  /// No description provided for @cancelBookingQuestion.
  ///
  /// In en, this message translates to:
  /// **'Cancel this booking?'**
  String get cancelBookingQuestion;

  /// No description provided for @cancelBookingBody.
  ///
  /// In en, this message translates to:
  /// **'{service}, {when}, will be cancelled. This cannot be undone.'**
  String cancelBookingBody(String service, String when);

  /// No description provided for @keepBooking.
  ///
  /// In en, this message translates to:
  /// **'Keep booking'**
  String get keepBooking;

  /// No description provided for @yesCancel.
  ///
  /// In en, this message translates to:
  /// **'Yes, cancel'**
  String get yesCancel;

  /// No description provided for @thanksRating.
  ///
  /// In en, this message translates to:
  /// **'Thanks for rating!'**
  String get thanksRating;

  /// No description provided for @thanksReview.
  ///
  /// In en, this message translates to:
  /// **'Thanks for your review! It helps others choose.'**
  String get thanksReview;

  /// No description provided for @reportThanks.
  ///
  /// In en, this message translates to:
  /// **'Thanks. Our support team will look into it and get back to you.'**
  String get reportThanks;

  /// No description provided for @bookingCancelled.
  ///
  /// In en, this message translates to:
  /// **'Booking cancelled'**
  String get bookingCancelled;

  /// No description provided for @loadingBookings.
  ///
  /// In en, this message translates to:
  /// **'Loading bookings...'**
  String get loadingBookings;

  /// No description provided for @noBookings.
  ///
  /// In en, this message translates to:
  /// **'No bookings yet'**
  String get noBookings;

  /// No description provided for @noBookingsBody.
  ///
  /// In en, this message translates to:
  /// **'Book a salon visit, a doctor, a repair and more. Your bookings will show up here.'**
  String get noBookingsBody;

  /// No description provided for @browseServices.
  ///
  /// In en, this message translates to:
  /// **'Browse services'**
  String get browseServices;

  /// No description provided for @upcomingActive.
  ///
  /// In en, this message translates to:
  /// **'Upcoming & active'**
  String get upcomingActive;

  /// No description provided for @pastBookings.
  ///
  /// In en, this message translates to:
  /// **'Past'**
  String get pastBookings;

  /// No description provided for @track.
  ///
  /// In en, this message translates to:
  /// **'Track'**
  String get track;

  /// No description provided for @payOnlineInstead.
  ///
  /// In en, this message translates to:
  /// **'Pay online instead'**
  String get payOnlineInstead;

  /// No description provided for @payAmount.
  ///
  /// In en, this message translates to:
  /// **'Pay {amount}'**
  String payAmount(String amount);

  /// No description provided for @rate.
  ///
  /// In en, this message translates to:
  /// **'Rate'**
  String get rate;

  /// No description provided for @reportProblem.
  ///
  /// In en, this message translates to:
  /// **'Report a problem'**
  String get reportProblem;

  /// No description provided for @cancelling.
  ///
  /// In en, this message translates to:
  /// **'Cancelling…'**
  String get cancelling;

  /// No description provided for @cancelBooking.
  ///
  /// In en, this message translates to:
  /// **'Cancel booking'**
  String get cancelBooking;

  /// No description provided for @overduePending.
  ///
  /// In en, this message translates to:
  /// **'This time has passed and the shop hasn\'t confirmed. You can cancel and book another time.'**
  String get overduePending;

  /// No description provided for @overdueConfirmed.
  ///
  /// In en, this message translates to:
  /// **'This time has passed. If you missed it, contact Alakh support or cancel.'**
  String get overdueConfirmed;

  /// No description provided for @expectedBackBy.
  ///
  /// In en, this message translates to:
  /// **'Expected back by {when}'**
  String expectedBackBy(String when);

  /// No description provided for @paid.
  ///
  /// In en, this message translates to:
  /// **'Paid'**
  String get paid;

  /// No description provided for @payingCash.
  ///
  /// In en, this message translates to:
  /// **'Paying in cash'**
  String get payingCash;

  /// No description provided for @youRated.
  ///
  /// In en, this message translates to:
  /// **'You rated it {stars}★'**
  String youRated(int stars);

  /// No description provided for @howWasIt.
  ///
  /// In en, this message translates to:
  /// **'How was it?'**
  String get howWasIt;

  /// No description provided for @starsCount.
  ///
  /// In en, this message translates to:
  /// **'{count, plural, =1{1 star} other{{count} stars}}'**
  String starsCount(int count);

  /// No description provided for @ratingPoor.
  ///
  /// In en, this message translates to:
  /// **'Poor'**
  String get ratingPoor;

  /// No description provided for @ratingBelowAverage.
  ///
  /// In en, this message translates to:
  /// **'Below average'**
  String get ratingBelowAverage;

  /// No description provided for @ratingOkay.
  ///
  /// In en, this message translates to:
  /// **'Okay'**
  String get ratingOkay;

  /// No description provided for @ratingGood.
  ///
  /// In en, this message translates to:
  /// **'Good'**
  String get ratingGood;

  /// No description provided for @ratingExcellent.
  ///
  /// In en, this message translates to:
  /// **'Excellent'**
  String get ratingExcellent;

  /// No description provided for @writeReview.
  ///
  /// In en, this message translates to:
  /// **'Write a review (optional)'**
  String get writeReview;

  /// No description provided for @reviewHint.
  ///
  /// In en, this message translates to:
  /// **'What went well, what could be better?'**
  String get reviewHint;

  /// No description provided for @reviewHelper.
  ///
  /// In en, this message translates to:
  /// **'Shown with your first name and last initial'**
  String get reviewHelper;

  /// No description provided for @whatWentWrong.
  ///
  /// In en, this message translates to:
  /// **'What went wrong?'**
  String get whatWentWrong;

  /// No description provided for @tellWhatHappened.
  ///
  /// In en, this message translates to:
  /// **'Tell us what happened'**
  String get tellWhatHappened;

  /// No description provided for @atLeast3.
  ///
  /// In en, this message translates to:
  /// **'At least 3 characters'**
  String get atLeast3;

  /// No description provided for @disputeServiceQuality.
  ///
  /// In en, this message translates to:
  /// **'Poor service'**
  String get disputeServiceQuality;

  /// No description provided for @disputeNoShow.
  ///
  /// In en, this message translates to:
  /// **'Provider didn\'t show up'**
  String get disputeNoShow;

  /// No description provided for @disputeDamage.
  ///
  /// In en, this message translates to:
  /// **'Something was damaged'**
  String get disputeDamage;

  /// No description provided for @disputeBilling.
  ///
  /// In en, this message translates to:
  /// **'Charged incorrectly'**
  String get disputeBilling;

  /// No description provided for @disputeOther.
  ///
  /// In en, this message translates to:
  /// **'Something else'**
  String get disputeOther;

  /// No description provided for @liveTracking.
  ///
  /// In en, this message translates to:
  /// **'Live Tracking'**
  String get liveTracking;

  /// No description provided for @yourProvider.
  ///
  /// In en, this message translates to:
  /// **'Your provider'**
  String get yourProvider;

  /// No description provided for @arrivingNow.
  ///
  /// In en, this message translates to:
  /// **'Arriving now'**
  String get arrivingNow;

  /// No description provided for @awayEstimate.
  ///
  /// In en, this message translates to:
  /// **'About {minutes} min away · {distance}'**
  String awayEstimate(int minutes, String distance);

  /// No description provided for @estimateFrom.
  ///
  /// In en, this message translates to:
  /// **'{estimate} from {place}'**
  String estimateFrom(String estimate, String place);

  /// No description provided for @findingProvider.
  ///
  /// In en, this message translates to:
  /// **'Finding your provider…'**
  String get findingProvider;

  /// No description provided for @waitingLocation.
  ///
  /// In en, this message translates to:
  /// **'Waiting for your provider to share their location'**
  String get waitingLocation;

  /// No description provided for @justNow.
  ///
  /// In en, this message translates to:
  /// **'just now'**
  String get justNow;

  /// No description provided for @minutesAgo.
  ///
  /// In en, this message translates to:
  /// **'{minutes} min ago'**
  String minutesAgo(int minutes);

  /// No description provided for @trackComingToCollect.
  ///
  /// In en, this message translates to:
  /// **'Coming to collect your item · updated {ago}'**
  String trackComingToCollect(String ago);

  /// No description provided for @trackOnTheWay.
  ///
  /// In en, this message translates to:
  /// **'On the way · updated {ago}'**
  String trackOnTheWay(String ago);

  /// No description provided for @trackTakingToShop.
  ///
  /// In en, this message translates to:
  /// **'Taking your item to the shop · updated {ago}'**
  String trackTakingToShop(String ago);

  /// No description provided for @trackItemWorkedOn.
  ///
  /// In en, this message translates to:
  /// **'Your item is being worked on · updated {ago}'**
  String trackItemWorkedOn(String ago);

  /// No description provided for @trackWorking.
  ///
  /// In en, this message translates to:
  /// **'Working on your booking · updated {ago}'**
  String trackWorking(String ago);

  /// No description provided for @trackBringingBack.
  ///
  /// In en, this message translates to:
  /// **'Bringing your item back · updated {ago}'**
  String trackBringingBack(String ago);

  /// No description provided for @trackAssigned.
  ///
  /// In en, this message translates to:
  /// **'Provider assigned · updated {ago}'**
  String trackAssigned(String ago);

  /// No description provided for @starsReviewsSemantics.
  ///
  /// In en, this message translates to:
  /// **'{stars, plural, =1{1 star} other{{stars} stars}}: {count, plural, =1{1 review} other{{count} reviews}}'**
  String starsReviewsSemantics(int stars, int count);

  /// No description provided for @verifiedBooking.
  ///
  /// In en, this message translates to:
  /// **'Verified booking'**
  String get verifiedBooking;

  /// No description provided for @shopReply.
  ///
  /// In en, this message translates to:
  /// **'Reply from the shop · {date}'**
  String shopReply(String date);

  /// No description provided for @ratingsReviews.
  ///
  /// In en, this message translates to:
  /// **'Ratings & reviews'**
  String get ratingsReviews;

  /// No description provided for @noReviewsYetLong.
  ///
  /// In en, this message translates to:
  /// **'No reviews yet. Customers can review the shop after a completed booking.'**
  String get noReviewsYetLong;

  /// No description provided for @seeAllReviews.
  ///
  /// In en, this message translates to:
  /// **'See all reviews ({count})'**
  String seeAllReviews(int count);

  /// No description provided for @allRatings.
  ///
  /// In en, this message translates to:
  /// **'All ratings'**
  String get allRatings;

  /// No description provided for @starsOnly.
  ///
  /// In en, this message translates to:
  /// **'{stars, plural, =1{1 star only} other{{stars} stars only}}'**
  String starsOnly(int stars);

  /// No description provided for @allFilter.
  ///
  /// In en, this message translates to:
  /// **'All'**
  String get allFilter;

  /// No description provided for @loadingReviews.
  ///
  /// In en, this message translates to:
  /// **'Loading reviews...'**
  String get loadingReviews;

  /// No description provided for @noReviewsYet.
  ///
  /// In en, this message translates to:
  /// **'No reviews yet.'**
  String get noReviewsYet;

  /// No description provided for @noStarReviews.
  ///
  /// In en, this message translates to:
  /// **'No {stars}-star reviews yet.'**
  String noStarReviews(int stars);

  /// No description provided for @showMoreReviews.
  ///
  /// In en, this message translates to:
  /// **'Show more reviews'**
  String get showMoreReviews;

  /// No description provided for @reviewsTitle.
  ///
  /// In en, this message translates to:
  /// **'Reviews'**
  String get reviewsTitle;

  /// No description provided for @reviewsOf.
  ///
  /// In en, this message translates to:
  /// **'Reviews of {shop}'**
  String reviewsOf(String shop);

  /// No description provided for @profileTitle.
  ///
  /// In en, this message translates to:
  /// **'Profile'**
  String get profileTitle;

  /// No description provided for @editProfile.
  ///
  /// In en, this message translates to:
  /// **'Edit Profile'**
  String get editProfile;

  /// No description provided for @savedAddresses.
  ///
  /// In en, this message translates to:
  /// **'Saved addresses'**
  String get savedAddresses;

  /// No description provided for @logout.
  ///
  /// In en, this message translates to:
  /// **'Log out'**
  String get logout;

  /// No description provided for @logoutQuestion.
  ///
  /// In en, this message translates to:
  /// **'Log out?'**
  String get logoutQuestion;

  /// No description provided for @logoutBody.
  ///
  /// In en, this message translates to:
  /// **'You\'ll need to sign in again to book or see your bookings.'**
  String get logoutBody;

  /// No description provided for @accountDeleted.
  ///
  /// In en, this message translates to:
  /// **'Your account has been deleted.'**
  String get accountDeleted;

  /// No description provided for @deleteMyAccount.
  ///
  /// In en, this message translates to:
  /// **'Delete my account'**
  String get deleteMyAccount;

  /// No description provided for @deleteAccountQuestion.
  ///
  /// In en, this message translates to:
  /// **'Delete your account?'**
  String get deleteAccountQuestion;

  /// No description provided for @deleteAccountBody.
  ///
  /// In en, this message translates to:
  /// **'Your profile, saved addresses and sign-in are removed and cannot be recovered. Past bookings and payments are kept without your name for the shops\' records.'**
  String get deleteAccountBody;

  /// No description provided for @enterPasswordConfirm.
  ///
  /// In en, this message translates to:
  /// **'Enter your password to confirm'**
  String get enterPasswordConfirm;

  /// No description provided for @deleteAccount.
  ///
  /// In en, this message translates to:
  /// **'Delete account'**
  String get deleteAccount;

  /// No description provided for @settingTheme.
  ///
  /// In en, this message translates to:
  /// **'Theme'**
  String get settingTheme;

  /// No description provided for @themeSystem.
  ///
  /// In en, this message translates to:
  /// **'System'**
  String get themeSystem;

  /// No description provided for @themeLight.
  ///
  /// In en, this message translates to:
  /// **'Light'**
  String get themeLight;

  /// No description provided for @themeDark.
  ///
  /// In en, this message translates to:
  /// **'Dark'**
  String get themeDark;

  /// No description provided for @settingLanguage.
  ///
  /// In en, this message translates to:
  /// **'Language'**
  String get settingLanguage;

  /// No description provided for @languageSystem.
  ///
  /// In en, this message translates to:
  /// **'System'**
  String get languageSystem;

  /// No description provided for @profileUpdated.
  ///
  /// In en, this message translates to:
  /// **'Profile updated successfully'**
  String get profileUpdated;

  /// No description provided for @personalInfo.
  ///
  /// In en, this message translates to:
  /// **'Personal Information'**
  String get personalInfo;

  /// No description provided for @aboutYou.
  ///
  /// In en, this message translates to:
  /// **'About you'**
  String get aboutYou;

  /// No description provided for @optional.
  ///
  /// In en, this message translates to:
  /// **'Optional'**
  String get optional;

  /// No description provided for @phoneNumber.
  ///
  /// In en, this message translates to:
  /// **'Phone Number'**
  String get phoneNumber;

  /// No description provided for @phoneCantChange.
  ///
  /// In en, this message translates to:
  /// **'Your sign-in number can\'t be changed here.'**
  String get phoneCantChange;

  /// No description provided for @saveChanges.
  ///
  /// In en, this message translates to:
  /// **'Save Changes'**
  String get saveChanges;

  /// No description provided for @addressSaved.
  ///
  /// In en, this message translates to:
  /// **'Address saved'**
  String get addressSaved;

  /// No description provided for @deleteAddressQuestion.
  ///
  /// In en, this message translates to:
  /// **'Delete \"{label}\"?'**
  String deleteAddressQuestion(String label);

  /// No description provided for @keepIt.
  ///
  /// In en, this message translates to:
  /// **'Keep it'**
  String get keepIt;

  /// No description provided for @addressDeleted.
  ///
  /// In en, this message translates to:
  /// **'Address deleted'**
  String get addressDeleted;

  /// No description provided for @defaultAddressSet.
  ///
  /// In en, this message translates to:
  /// **'{label} is now your default address'**
  String defaultAddressSet(String label);

  /// No description provided for @noAddresses.
  ///
  /// In en, this message translates to:
  /// **'No saved addresses yet'**
  String get noAddresses;

  /// No description provided for @noAddressesBody.
  ///
  /// In en, this message translates to:
  /// **'Add your home or work address for home visits and pickups.'**
  String get noAddressesBody;

  /// No description provided for @addressOptions.
  ///
  /// In en, this message translates to:
  /// **'Options for {label}'**
  String addressOptions(String label);

  /// No description provided for @makeDefault.
  ///
  /// In en, this message translates to:
  /// **'Make default'**
  String get makeDefault;

  /// No description provided for @newAddress.
  ///
  /// In en, this message translates to:
  /// **'New address'**
  String get newAddress;

  /// No description provided for @addressDefaultLabel.
  ///
  /// In en, this message translates to:
  /// **'Home'**
  String get addressDefaultLabel;

  /// No description provided for @addressLabel.
  ///
  /// In en, this message translates to:
  /// **'Label (Home, Work…)'**
  String get addressLabel;

  /// No description provided for @addressStreet.
  ///
  /// In en, this message translates to:
  /// **'Flat / house no., street, area'**
  String get addressStreet;

  /// No description provided for @city.
  ///
  /// In en, this message translates to:
  /// **'City'**
  String get city;

  /// No description provided for @state.
  ///
  /// In en, this message translates to:
  /// **'State'**
  String get state;

  /// No description provided for @pinCode.
  ///
  /// In en, this message translates to:
  /// **'PIN code'**
  String get pinCode;

  /// No description provided for @pinInvalid.
  ///
  /// In en, this message translates to:
  /// **'Enter a 6-digit PIN code'**
  String get pinInvalid;

  /// No description provided for @offlineBanner.
  ///
  /// In en, this message translates to:
  /// **'You\'re offline. Showing saved info; bookings will need a connection.'**
  String get offlineBanner;

  /// No description provided for @backOnline.
  ///
  /// In en, this message translates to:
  /// **'Back online'**
  String get backOnline;

  /// No description provided for @helpTitle.
  ///
  /// In en, this message translates to:
  /// **'Help & Support'**
  String get helpTitle;

  /// No description provided for @helpSearchHint.
  ///
  /// In en, this message translates to:
  /// **'Search help'**
  String get helpSearchHint;

  /// No description provided for @helpFaqHeading.
  ///
  /// In en, this message translates to:
  /// **'Common questions'**
  String get helpFaqHeading;

  /// No description provided for @helpNoMatch.
  ///
  /// In en, this message translates to:
  /// **'No answers match \"{query}\". Contact us below.'**
  String helpNoMatch(String query);

  /// No description provided for @helpContactHeading.
  ///
  /// In en, this message translates to:
  /// **'Contact the Alakh support team'**
  String get helpContactHeading;

  /// No description provided for @helpContactNote.
  ///
  /// In en, this message translates to:
  /// **'Write to us or call. If it is about a booking, keep the booking number handy.'**
  String get helpContactNote;

  /// No description provided for @helpEmail.
  ///
  /// In en, this message translates to:
  /// **'Email support'**
  String get helpEmail;

  /// No description provided for @helpCall.
  ///
  /// In en, this message translates to:
  /// **'Call support'**
  String get helpCall;

  /// No description provided for @helpReport.
  ///
  /// In en, this message translates to:
  /// **'Report a problem with a booking'**
  String get helpReport;

  /// No description provided for @helpReportSubtitle.
  ///
  /// In en, this message translates to:
  /// **'Pick the booking and tell us what went wrong'**
  String get helpReportSubtitle;

  /// No description provided for @helpPickBooking.
  ///
  /// In en, this message translates to:
  /// **'Which booking?'**
  String get helpPickBooking;

  /// No description provided for @helpPickBookingNote.
  ///
  /// In en, this message translates to:
  /// **'Bookings under way or finished are reported in the app; for others we open an email to support.'**
  String get helpPickBookingNote;

  /// No description provided for @helpEmailInstead.
  ///
  /// In en, this message translates to:
  /// **'Not listed? Email support'**
  String get helpEmailInstead;

  /// No description provided for @helpBookingsFailed.
  ///
  /// In en, this message translates to:
  /// **'Couldn\'t load your bookings.'**
  String get helpBookingsFailed;

  /// No description provided for @helpCouldNotOpen.
  ///
  /// In en, this message translates to:
  /// **'Couldn\'t open that. Write to {email} or call {phone}.'**
  String helpCouldNotOpen(String email, String phone);

  /// No description provided for @helpEmailSubject.
  ///
  /// In en, this message translates to:
  /// **'AlakhService support'**
  String get helpEmailSubject;

  /// No description provided for @helpEmailBookingSubject.
  ///
  /// In en, this message translates to:
  /// **'Problem with booking #{number}'**
  String helpEmailBookingSubject(String number);

  /// No description provided for @helpEmailBookingBody.
  ///
  /// In en, this message translates to:
  /// **'Booking number: {number}\n\nWhat happened:\n'**
  String helpEmailBookingBody(String number);

  /// No description provided for @faqTopicBooking.
  ///
  /// In en, this message translates to:
  /// **'Booking'**
  String get faqTopicBooking;

  /// No description provided for @faqTopicCancel.
  ///
  /// In en, this message translates to:
  /// **'Cancelling & rescheduling'**
  String get faqTopicCancel;

  /// No description provided for @faqTopicPayments.
  ///
  /// In en, this message translates to:
  /// **'Payments & refunds'**
  String get faqTopicPayments;

  /// No description provided for @faqTopicPickup.
  ///
  /// In en, this message translates to:
  /// **'Pickup & drop'**
  String get faqTopicPickup;

  /// No description provided for @faqTopicHome.
  ///
  /// In en, this message translates to:
  /// **'Home visits'**
  String get faqTopicHome;

  /// No description provided for @faqTopicReviews.
  ///
  /// In en, this message translates to:
  /// **'Reviews'**
  String get faqTopicReviews;

  /// No description provided for @faqTopicAccount.
  ///
  /// In en, this message translates to:
  /// **'Account & privacy'**
  String get faqTopicAccount;

  /// No description provided for @faqBookQ.
  ///
  /// In en, this message translates to:
  /// **'How do I book a service?'**
  String get faqBookQ;

  /// No description provided for @faqBookA.
  ///
  /// In en, this message translates to:
  /// **'Find the service on Home or Services and tap Book Now. Choose how you want it (at the shop, at your place or pickup & drop), pick a day and a free time, and confirm. The shop then confirms your request and we let you know.'**
  String get faqBookA;

  /// No description provided for @faqNoTimesQ.
  ///
  /// In en, this message translates to:
  /// **'Why can\'t I see any times on a day?'**
  String get faqNoTimesQ;

  /// No description provided for @faqNoTimesA.
  ///
  /// In en, this message translates to:
  /// **'The shop may be closed that day or fully booked, or today\'s times may have passed. The message under the dates says which; try another day.'**
  String get faqNoTimesA;

  /// No description provided for @faqCancelQ.
  ///
  /// In en, this message translates to:
  /// **'How do I cancel a booking?'**
  String get faqCancelQ;

  /// No description provided for @faqCancelA.
  ///
  /// In en, this message translates to:
  /// **'Open Bookings and tap Cancel booking on it. You can cancel until the provider is on the way.'**
  String get faqCancelA;

  /// No description provided for @faqRescheduleQ.
  ///
  /// In en, this message translates to:
  /// **'Can I change the time of a booking?'**
  String get faqRescheduleQ;

  /// No description provided for @faqRescheduleA.
  ///
  /// In en, this message translates to:
  /// **'Not in the app yet. Cancel the booking while you still can and book the new time. If the provider is already on the way, contact Alakh support.'**
  String get faqRescheduleA;

  /// No description provided for @faqPayQ.
  ///
  /// In en, this message translates to:
  /// **'When and how do I pay?'**
  String get faqPayQ;

  /// No description provided for @faqPayA.
  ///
  /// In en, this message translates to:
  /// **'Nothing is paid when you book. Once the shop confirms, tap Pay on the booking to pay online by UPI, card or net banking (through Razorpay), or choose to pay in cash when the job is done.'**
  String get faqPayA;

  /// No description provided for @faqRefundQ.
  ///
  /// In en, this message translates to:
  /// **'How do refunds work?'**
  String get faqRefundQ;

  /// No description provided for @faqRefundA.
  ///
  /// In en, this message translates to:
  /// **'When an online payment is refunded, the money goes back the way you paid; your bank may take a few working days to show it. The booking then shows Refunded. For a problem with a paid booking, report it and Alakh support will look into it.'**
  String get faqRefundA;

  /// No description provided for @faqPickupQ.
  ///
  /// In en, this message translates to:
  /// **'How does pickup & drop work?'**
  String get faqPickupQ;

  /// No description provided for @faqPickupA.
  ///
  /// In en, this message translates to:
  /// **'Choose Pickup & drop when booking, pick the address and tell us what to collect. The item is collected, serviced at the shop and brought back. Bookings shows each step and when it is expected back.'**
  String get faqPickupA;

  /// No description provided for @faqHomeQ.
  ///
  /// In en, this message translates to:
  /// **'How do home visits work?'**
  String get faqHomeQ;

  /// No description provided for @faqHomeA.
  ///
  /// In en, this message translates to:
  /// **'Choose At my place when booking and pick a saved address. A professional comes at the time you chose, and once they are on the way you can follow them live from Bookings. Any home visit fee is shown before you confirm.'**
  String get faqHomeA;

  /// No description provided for @faqReviewQ.
  ///
  /// In en, this message translates to:
  /// **'How do I rate or review a shop?'**
  String get faqReviewQ;

  /// No description provided for @faqReviewA.
  ///
  /// In en, this message translates to:
  /// **'After a booking is completed, tap Rate on it in Bookings. Reviews show your first name and last initial and are marked Verified booking.'**
  String get faqReviewA;

  /// No description provided for @faqProblemQ.
  ///
  /// In en, this message translates to:
  /// **'Something went wrong with my booking. What do I do?'**
  String get faqProblemQ;

  /// No description provided for @faqProblemA.
  ///
  /// In en, this message translates to:
  /// **'Tap Report a problem on the booking, or use \"Report a problem with a booking\" below. Alakh support looks into every report and gets back to you.'**
  String get faqProblemA;

  /// No description provided for @faqProfileQ.
  ///
  /// In en, this message translates to:
  /// **'How do I change my name or addresses?'**
  String get faqProfileQ;

  /// No description provided for @faqProfileA.
  ///
  /// In en, this message translates to:
  /// **'In Profile, use Edit Profile for your name and Saved addresses for the places we come to. Your sign-in number can\'t be changed in the app; contact Alakh support for that.'**
  String get faqProfileA;

  /// No description provided for @faqSessionsQ.
  ///
  /// In en, this message translates to:
  /// **'How do I sign out, or sign out of other devices?'**
  String get faqSessionsQ;

  /// No description provided for @faqSessionsA.
  ///
  /// In en, this message translates to:
  /// **'Tap Log out in Profile to sign out on this phone. To sign out of all your other devices (a lost phone, say), choose a new password with Forgot Password on the sign-in screen: every other device is signed out. Alakh support can also help.'**
  String get faqSessionsA;

  /// No description provided for @faqDeleteQ.
  ///
  /// In en, this message translates to:
  /// **'How do I delete my account?'**
  String get faqDeleteQ;

  /// No description provided for @faqDeleteA.
  ///
  /// In en, this message translates to:
  /// **'In Profile, tap Delete my account. Your profile, saved addresses and sign-in are removed; past bookings and payments are kept without your name for the shops\' records.'**
  String get faqDeleteA;

  /// No description provided for @chatTitle.
  ///
  /// In en, this message translates to:
  /// **'Chat with the shop'**
  String get chatTitle;

  /// No description provided for @chatOpen.
  ///
  /// In en, this message translates to:
  /// **'Chat'**
  String get chatOpen;

  /// No description provided for @chatUnread.
  ///
  /// In en, this message translates to:
  /// **'Chat, {count} unread'**
  String chatUnread(int count);

  /// No description provided for @chatLoading.
  ///
  /// In en, this message translates to:
  /// **'Loading messages…'**
  String get chatLoading;

  /// No description provided for @chatEmpty.
  ///
  /// In en, this message translates to:
  /// **'No messages yet. Ask the shop anything about this booking.'**
  String get chatEmpty;

  /// No description provided for @chatHint.
  ///
  /// In en, this message translates to:
  /// **'Write a message'**
  String get chatHint;

  /// No description provided for @chatLoadEarlier.
  ///
  /// In en, this message translates to:
  /// **'Load earlier messages'**
  String get chatLoadEarlier;

  /// No description provided for @chatShop.
  ///
  /// In en, this message translates to:
  /// **'Shop'**
  String get chatShop;

  /// No description provided for @chatRead.
  ///
  /// In en, this message translates to:
  /// **'Read'**
  String get chatRead;

  /// No description provided for @chatSent.
  ///
  /// In en, this message translates to:
  /// **'Sent'**
  String get chatSent;

  /// No description provided for @chatFlaggedHint.
  ///
  /// In en, this message translates to:
  /// **'Contact details are hidden to keep you safe'**
  String get chatFlaggedHint;

  /// No description provided for @chatClosed.
  ///
  /// In en, this message translates to:
  /// **'This chat is closed. You can still read it.'**
  String get chatClosed;

  /// No description provided for @chatClosedSince.
  ///
  /// In en, this message translates to:
  /// **'This chat closed {when}. You can still read it.'**
  String chatClosedSince(String when);

  /// No description provided for @chatOpenUntil.
  ///
  /// In en, this message translates to:
  /// **'You can send messages until {when}'**
  String chatOpenUntil(String when);

  /// No description provided for @chatCallShop.
  ///
  /// In en, this message translates to:
  /// **'Call shop'**
  String get chatCallShop;

  /// No description provided for @chatCallPlaced.
  ///
  /// In en, this message translates to:
  /// **'We\'re calling you to connect you to the shop.'**
  String get chatCallPlaced;

  /// No description provided for @bookingDetailsTitle.
  ///
  /// In en, this message translates to:
  /// **'Booking details'**
  String get bookingDetailsTitle;

  /// No description provided for @viewInvoice.
  ///
  /// In en, this message translates to:
  /// **'View invoice'**
  String get viewInvoice;

  /// No description provided for @invoiceTitle.
  ///
  /// In en, this message translates to:
  /// **'Invoice'**
  String get invoiceTitle;

  /// No description provided for @invoiceLoading.
  ///
  /// In en, this message translates to:
  /// **'Loading invoice…'**
  String get invoiceLoading;

  /// No description provided for @paymentPartlyRefunded.
  ///
  /// In en, this message translates to:
  /// **'Partly refunded'**
  String get paymentPartlyRefunded;

  /// No description provided for @cancelPolicy.
  ///
  /// In en, this message translates to:
  /// **'Free cancellation until 2 hours before your booking. After that, a cancellation fee may apply.'**
  String get cancelPolicy;

  /// No description provided for @cancelPolicyLate.
  ///
  /// In en, this message translates to:
  /// **'Your booking is less than 2 hours away, so a cancellation fee may apply.'**
  String get cancelPolicyLate;

  /// No description provided for @termsRequired.
  ///
  /// In en, this message translates to:
  /// **'Please accept the Terms and Privacy Policy'**
  String get termsRequired;

  /// No description provided for @termsAgree.
  ///
  /// In en, this message translates to:
  /// **'I agree to the'**
  String get termsAgree;

  /// No description provided for @termsOfService.
  ///
  /// In en, this message translates to:
  /// **'Terms of Service'**
  String get termsOfService;

  /// No description provided for @termsAnd.
  ///
  /// In en, this message translates to:
  /// **'and'**
  String get termsAnd;

  /// No description provided for @privacyPolicy.
  ///
  /// In en, this message translates to:
  /// **'Privacy Policy'**
  String get privacyPolicy;

  /// No description provided for @legalSection.
  ///
  /// In en, this message translates to:
  /// **'Legal'**
  String get legalSection;

  /// No description provided for @refundPolicy.
  ///
  /// In en, this message translates to:
  /// **'Refund policy'**
  String get refundPolicy;

  /// No description provided for @grievanceOfficer.
  ///
  /// In en, this message translates to:
  /// **'Grievance redressal'**
  String get grievanceOfficer;

  /// No description provided for @downloadMyData.
  ///
  /// In en, this message translates to:
  /// **'Download my data'**
  String get downloadMyData;

  /// No description provided for @dataExportNone.
  ///
  /// In en, this message translates to:
  /// **'Get a copy of your account, bookings and payments'**
  String get dataExportNone;

  /// No description provided for @dataExportPending.
  ///
  /// In en, this message translates to:
  /// **'Requested: {day}. We\'re preparing it.'**
  String dataExportPending(String day);

  /// No description provided for @dataExportReady.
  ///
  /// In en, this message translates to:
  /// **'Ready. Tap to download.'**
  String get dataExportReady;

  /// No description provided for @dataExportDeclined.
  ///
  /// In en, this message translates to:
  /// **'Your last request was declined.'**
  String get dataExportDeclined;

  /// No description provided for @dataExportQuestion.
  ///
  /// In en, this message translates to:
  /// **'Request a copy of your data?'**
  String get dataExportQuestion;

  /// No description provided for @dataExportBody.
  ///
  /// In en, this message translates to:
  /// **'We\'ll prepare a file with your account, bookings and payments. You\'ll see here when it\'s ready to download.'**
  String get dataExportBody;

  /// No description provided for @dataExportRequest.
  ///
  /// In en, this message translates to:
  /// **'Request'**
  String get dataExportRequest;

  /// No description provided for @dataExportRequested.
  ///
  /// In en, this message translates to:
  /// **'Request sent. We\'ll prepare your data.'**
  String get dataExportRequested;
}

class _AppLocalizationsDelegate
    extends LocalizationsDelegate<AppLocalizations> {
  const _AppLocalizationsDelegate();

  @override
  Future<AppLocalizations> load(Locale locale) {
    return SynchronousFuture<AppLocalizations>(lookupAppLocalizations(locale));
  }

  @override
  bool isSupported(Locale locale) =>
      <String>['en', 'hi'].contains(locale.languageCode);

  @override
  bool shouldReload(_AppLocalizationsDelegate old) => false;
}

AppLocalizations lookupAppLocalizations(Locale locale) {
  // Lookup logic when only language code is specified.
  switch (locale.languageCode) {
    case 'en':
      return AppLocalizationsEn();
    case 'hi':
      return AppLocalizationsHi();
  }

  throw FlutterError(
      'AppLocalizations.delegate failed to load unsupported locale "$locale". This is likely '
      'an issue with the localizations generation tool. Please file an issue '
      'on GitHub with a reproducible sample app and the gen-l10n configuration '
      'that was used.');
}
