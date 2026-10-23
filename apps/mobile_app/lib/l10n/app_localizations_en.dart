// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for English (`en`).
class AppLocalizationsEn extends AppLocalizations {
  AppLocalizationsEn([String locale = 'en']) : super(locale);

  @override
  String get appTitle => 'AlakhService';

  @override
  String get cancel => 'Cancel';

  @override
  String get save => 'Save';

  @override
  String get delete => 'Delete';

  @override
  String get done => 'Done';

  @override
  String get retry => 'Retry';

  @override
  String get tryAgain => 'Try again';

  @override
  String get tryAgainButton => 'Try Again';

  @override
  String get send => 'Send';

  @override
  String get submit => 'Submit';

  @override
  String get notNow => 'Not now';

  @override
  String get remove => 'Remove';

  @override
  String get apply => 'Apply';

  @override
  String get loadingMore => 'Loading…';

  @override
  String get somethingWentWrong => 'Something went wrong';

  @override
  String get showPassword => 'Show password';

  @override
  String get hidePassword => 'Hide password';

  @override
  String get requiredField => 'Required';

  @override
  String get today => 'Today';

  @override
  String get tomorrow => 'Tomorrow';

  @override
  String get yesterday => 'Yesterday';

  @override
  String get midnight => 'midnight';

  @override
  String get navHome => 'Home';

  @override
  String get navServices => 'Services';

  @override
  String get navBookings => 'Bookings';

  @override
  String get navJobs => 'Jobs';

  @override
  String get navProfile => 'Profile';

  @override
  String get errorTimeout =>
      'The server took too long to respond. Please try again.';

  @override
  String get errorCannotReach =>
      'Cannot reach AlakhService. Check your connection.';

  @override
  String errorRequestFailed(int status) {
    return 'Request failed ($status)';
  }

  @override
  String get errorGeneric => 'Something went wrong. Please try again.';

  @override
  String get errorNoInternet => 'No internet connection';

  @override
  String get vPhoneRequired => 'Phone number is required';

  @override
  String get vPhoneInvalid => 'Enter a valid phone number';

  @override
  String get vMobileRequired => 'Mobile number is required';

  @override
  String get vMobileInvalid => 'Enter a valid 10-digit mobile number';

  @override
  String get vPhoneOrEmailRequired => 'Enter your phone number or email';

  @override
  String get vPhoneOrEmailInvalid => 'Enter a valid phone number or email';

  @override
  String get vPasswordRequired => 'Password is required';

  @override
  String get vPasswordRules =>
      'At least 8 characters, with a capital letter and a number';

  @override
  String get vEmailRequired => 'Email is required';

  @override
  String get vEmailInvalid => 'Enter a valid email address';

  @override
  String get vPasswordShort => 'Password must be at least 8 characters';

  @override
  String get vPasswordUpper => 'Include at least one uppercase letter';

  @override
  String get vPasswordNumber => 'Include at least one number';

  @override
  String get vOtpRequired => 'OTP is required';

  @override
  String get vOtpInvalid => 'Enter a valid 6-digit OTP';

  @override
  String get vNameRequired => 'Name is required';

  @override
  String get vNameShort => 'Name must be at least 2 characters';

  @override
  String get vFieldRequired => 'This field is required';

  @override
  String vFieldRequiredNamed(String field) {
    return '$field is required';
  }

  @override
  String vFieldMinLength(String field, String min) {
    return '$field must be at least $min characters';
  }

  @override
  String get vConfirmPassword => 'Please confirm your password';

  @override
  String get vPasswordsDontMatch => 'Passwords do not match';

  @override
  String get loginWelcome => 'Welcome Back';

  @override
  String get loginSubtitle =>
      'Sign in to book, track and pay for your services';

  @override
  String get loginPhoneOrEmail => 'Phone or email';

  @override
  String get loginPhoneOrEmailHint => '98765 43210 or you@example.com';

  @override
  String get password => 'Password';

  @override
  String get loginPasswordHint => 'Enter your password';

  @override
  String get loginForgot => 'Forgot Password?';

  @override
  String get loginButton => 'Login';

  @override
  String get loginWithOtp => 'Login with OTP instead';

  @override
  String get loginNoAccount => 'Don\'t have an account?';

  @override
  String get loginRegister => 'Register';

  @override
  String get registerTitle => 'Create Account';

  @override
  String get registerHeading => 'Join AlakhService';

  @override
  String get registerSubtitle => 'Create your account to get started';

  @override
  String get fullName => 'Full Name';

  @override
  String get registerNameHint => 'e.g. Priya Sharma';

  @override
  String get mobileNumber => 'Mobile Number';

  @override
  String get registerPasswordHint => 'Choose a password';

  @override
  String get registerCodeNote =>
      'We will text a verification code to this number.';

  @override
  String get registerButton => 'Create account';

  @override
  String get registerHaveAccount => 'Already have an account?';

  @override
  String get otpTitleLogin => 'Login with OTP';

  @override
  String get otpTitleVerifyPhone => 'Verify your phone';

  @override
  String get otpTitleVerifyEmail => 'Verify your email';

  @override
  String get otpResent => 'A new code is on its way';

  @override
  String get otpEnterCode => 'Enter the code';

  @override
  String otpSentTo(int length, String destination) {
    return 'We sent a $length-digit code to $destination.';
  }

  @override
  String get otpWrongPhone => 'Wrong phone? Change it';

  @override
  String get otpWrongEmail => 'Wrong email? Change it';

  @override
  String get otpFieldLabel => 'One-time code';

  @override
  String get otpVerifyLogin => 'Verify and login';

  @override
  String get otpVerify => 'Verify';

  @override
  String otpResendIn(int seconds) {
    return 'Didn\'t get it? You can resend in ${seconds}s';
  }

  @override
  String get otpResend => 'Didn\'t get it? Resend code';

  @override
  String get forgotTitle => 'Forgot Password';

  @override
  String get resetPassword => 'Reset Password';

  @override
  String get forgotIntro =>
      'Enter the phone number or email on your account and we\'ll send you a code.';

  @override
  String forgotEnterCode(String destination) {
    return 'Enter the code we sent to $destination and choose a new password.';
  }

  @override
  String get forgotDifferent => 'Use a different phone or email';

  @override
  String get code => 'Code';

  @override
  String get codeHint => '6-digit code';

  @override
  String get newPassword => 'New Password';

  @override
  String get newPasswordHint => 'Choose a new password';

  @override
  String get sendCode => 'Send Code';

  @override
  String get passwordChanged => 'Password Changed';

  @override
  String get passwordChangedBody =>
      'Sign in with your new password. Other devices have been signed out.';

  @override
  String get backToLogin => 'Back to Login';

  @override
  String get greetingMorning => 'Good morning';

  @override
  String get greetingAfternoon => 'Good afternoon';

  @override
  String get greetingEvening => 'Good evening';

  @override
  String get homeFindService => 'Find a Service';

  @override
  String get searchHint => 'Search haircut, AC repair, doctor…';

  @override
  String get searchServicesHint => 'Search services...';

  @override
  String get homeOurServices => 'Our Services';

  @override
  String get homePopular => 'Popular Services';

  @override
  String get homeLoadFailed => 'Could not load services.';

  @override
  String get homeNoServices => 'No services listed yet.';

  @override
  String get notifications => 'Notifications';

  @override
  String notificationsUnread(int count) {
    return 'Notifications, $count unread';
  }

  @override
  String get catHaircut => 'Haircut';

  @override
  String get catBeauty => 'Beauty Parlour';

  @override
  String get catDoctor => 'Doctor';

  @override
  String get catOffice => 'Office Visits';

  @override
  String get catCar => 'Car Repair';

  @override
  String get catBike => 'Bike Repair';

  @override
  String get catDevices => 'Laptop & Phone';

  @override
  String get catAc => 'AC Repair';

  @override
  String get catCleaning => 'Cleaning';

  @override
  String get catPlumbing => 'Plumbing';

  @override
  String get catElectrical => 'Electrical';

  @override
  String get catCarpentry => 'Carpentry';

  @override
  String get catPest => 'Pest Control';

  @override
  String get catHandyman => 'Handyman';

  @override
  String get bannerTrack => 'Track your\nbookings';

  @override
  String get bannerMyBookings => 'My bookings';

  @override
  String get bannerSemantics => 'Track your bookings. My bookings';

  @override
  String get nextBooking => 'Your next booking';

  @override
  String nextBookingSemantics(String service, String when, String statusText) {
    return 'Your next booking: $service, $when, $statusText. Open my bookings';
  }

  @override
  String get servicesTitle => 'Services';

  @override
  String get clearSearch => 'Clear search';

  @override
  String get loadingServices => 'Loading services...';

  @override
  String get noServicesListed => 'No services listed yet';

  @override
  String nothingFound(String query) {
    return 'Nothing found for \"$query\"';
  }

  @override
  String get pullToCheck => 'Pull down to check again.';

  @override
  String get tryDifferentWord => 'Try a shorter or different word.';

  @override
  String get showAllServices => 'Show all services';

  @override
  String get modeHomeVisit => 'Home visit';

  @override
  String get modePickupDrop => 'Pickup & drop';

  @override
  String get modeAtShop => 'At shop';

  @override
  String get unavailable => 'Unavailable';

  @override
  String minutesShort(int minutes) {
    return '$minutes min';
  }

  @override
  String get ratingNew => 'New';

  @override
  String get ratingNewSemantics => 'New, no reviews yet';

  @override
  String ratedSemantics(String rating, int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count reviews',
      one: '1 review',
    );
    return 'Rated $rating out of 5 from $_temp0';
  }

  @override
  String starsLabel(String rating) {
    return '$rating out of 5 stars';
  }

  @override
  String reviewsCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count reviews',
      one: '1 review',
    );
    return '$_temp0';
  }

  @override
  String get serviceNotTaking =>
      'This service isn\'t taking bookings right now.';

  @override
  String get priceFrom => 'From';

  @override
  String get bookNow => 'Book Now';

  @override
  String aboutMinutes(int minutes) {
    return 'About $minutes min';
  }

  @override
  String get howYouCanGetIt => 'How you can get it';

  @override
  String get modeAtYourPlace => 'At your place';

  @override
  String get modeAtTheShop => 'At the shop';

  @override
  String get aboutService => 'About this service';

  @override
  String get noDescription => 'The shop has not added a description yet.';

  @override
  String get joinQueue => 'Walk in now: join the queue';

  @override
  String get joinQueueNote =>
      'No appointment needed: we\'ll tell you your place and when it\'s your turn.';

  @override
  String get howToGetThere => 'How to get there';

  @override
  String hoursOpenCloses(String time) {
    return 'Open now · closes $time';
  }

  @override
  String hoursClosedOpens(String time) {
    return 'Closed · opens $time';
  }

  @override
  String hoursClosedOpensTomorrow(String time) {
    return 'Closed · opens tomorrow $time';
  }

  @override
  String hoursClosedOpensDay(String day, String time) {
    return 'Closed · opens $day $time';
  }

  @override
  String get hoursClosed => 'Closed';

  @override
  String get bookServiceTitle => 'Book Service';

  @override
  String get howWouldYouLikeIt => 'How would you like it?';

  @override
  String get whenQuestion => 'When?';

  @override
  String get timesLoadFailed => 'Couldn\'t load the times for this day';

  @override
  String get findingTimes => 'Finding free times…';

  @override
  String get partMorning => 'Morning';

  @override
  String get partAfternoon => 'Afternoon';

  @override
  String get partEvening => 'Evening';

  @override
  String get pickATime => 'Pick a time';

  @override
  String get noMoreTimesToday => 'No more times today — try another day';

  @override
  String get closedOnDay => 'Closed on this day';

  @override
  String closedOnDayNote(String note) {
    return 'Closed on this day ($note)';
  }

  @override
  String get fullyBooked => 'Fully booked — try another day';

  @override
  String get noTimesOnDay => 'No times on this day — try another day';

  @override
  String get collectFrom => 'Collect from';

  @override
  String get whereShouldWeCome => 'Where should we come?';

  @override
  String get noSavedAddress => 'You have no saved address yet.';

  @override
  String get addAddress => 'Add address';

  @override
  String get savedAddress => 'Saved address';

  @override
  String get addAnotherAddress => 'Add another address';

  @override
  String get whatToCollect => 'What should we collect?';

  @override
  String get whatToCollectHint =>
      'e.g. Honda Activa, brakes squeaking · Dell laptop, cracked screen';

  @override
  String get whatToCollectError => 'Tell us what to collect and what is wrong';

  @override
  String get notesOptional => 'Notes (optional)';

  @override
  String get notesHint => 'Any special instructions...';

  @override
  String get couponOptional => 'Coupon code (optional)';

  @override
  String get couponHint => 'e.g. WELCOME10';

  @override
  String get checking => 'Checking…';

  @override
  String get homeVisitFee => 'Home visit fee';

  @override
  String get pickupDropFee => 'Pickup & drop fee';

  @override
  String get snackPickTime => 'Pick a time for your booking';

  @override
  String get snackAddAddress => 'Add the address we should come to';

  @override
  String get snackFillDetails => 'Please fill in the highlighted details';

  @override
  String get bookingRequested => 'Booking requested';

  @override
  String bookingNumber(String number) {
    return 'Booking #$number';
  }

  @override
  String get bookingRequestedBody =>
      'The shop will confirm it shortly. We\'ll notify you, and you can pay once it\'s confirmed.';

  @override
  String get viewMyBookings => 'View my bookings';

  @override
  String couponApplied(String code, String percent, String saving) {
    return '$code applied: $percent% off, you save $saving';
  }

  @override
  String get priceDetails => 'Price details';

  @override
  String get priceService => 'Service';

  @override
  String priceCoupon(String code) {
    return 'Coupon $code';
  }

  @override
  String get total => 'Total';

  @override
  String get payLaterNote =>
      'Nothing to pay now. Pay online or in cash once the shop confirms.';

  @override
  String get confirmBooking => 'Confirm Booking';

  @override
  String get chooseDayTime => 'Choose a day and time below';

  @override
  String get modeChoiceAtHome => 'At my place';

  @override
  String get modeChoiceAtShop => 'Visit the shop';

  @override
  String get explainAtHome =>
      'A professional comes to your address at the time you choose.';

  @override
  String get explainPickup =>
      'We collect your item from your address, service it and bring it back. You\'ll be told at each step.';

  @override
  String get explainAtShop =>
      'You go to the shop at the time you choose. See \"How to get there\" on your booking.';

  @override
  String get myBookings => 'My Bookings';

  @override
  String get statusPending => 'Awaiting confirmation';

  @override
  String get statusConfirmed => 'Confirmed';

  @override
  String get statusAssigned => 'Provider assigned';

  @override
  String get statusEnRoute => 'Provider on the way';

  @override
  String get statusPickedUp => 'Item picked up';

  @override
  String get statusInProgress => 'In progress';

  @override
  String get statusOutForDelivery => 'On its way back';

  @override
  String get statusCompleted => 'Completed';

  @override
  String get statusCancelled => 'Cancelled';

  @override
  String get statusDisputed => 'Problem reported';

  @override
  String get statusRefunded => 'Refunded';

  @override
  String get cancelBookingQuestion => 'Cancel this booking?';

  @override
  String cancelBookingBody(String service, String when) {
    return '$service, $when, will be cancelled. This cannot be undone.';
  }

  @override
  String get keepBooking => 'Keep booking';

  @override
  String get yesCancel => 'Yes, cancel';

  @override
  String get thanksRating => 'Thanks for rating!';

  @override
  String get thanksReview => 'Thanks for your review! It helps others choose.';

  @override
  String get reportThanks =>
      'Thanks. Our support team will look into it and get back to you.';

  @override
  String get bookingCancelled => 'Booking cancelled';

  @override
  String get loadingBookings => 'Loading bookings...';

  @override
  String get noBookings => 'No bookings yet';

  @override
  String get noBookingsBody =>
      'Book a salon visit, a doctor, a repair and more. Your bookings will show up here.';

  @override
  String get browseServices => 'Browse services';

  @override
  String get upcomingActive => 'Upcoming & active';

  @override
  String get pastBookings => 'Past';

  @override
  String get track => 'Track';

  @override
  String get payOnlineInstead => 'Pay online instead';

  @override
  String payAmount(String amount) {
    return 'Pay $amount';
  }

  @override
  String get rate => 'Rate';

  @override
  String get reportProblem => 'Report a problem';

  @override
  String get cancelling => 'Cancelling…';

  @override
  String get cancelBooking => 'Cancel booking';

  @override
  String get overduePending =>
      'This time has passed and the shop hasn\'t confirmed. You can cancel and book another time.';

  @override
  String get overdueConfirmed =>
      'This time has passed. If you missed it, contact Alakh support or cancel.';

  @override
  String expectedBackBy(String when) {
    return 'Expected back by $when';
  }

  @override
  String get paid => 'Paid';

  @override
  String get payingCash => 'Paying in cash';

  @override
  String youRated(int stars) {
    return 'You rated it $stars★';
  }

  @override
  String get howWasIt => 'How was it?';

  @override
  String starsCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count stars',
      one: '1 star',
    );
    return '$_temp0';
  }

  @override
  String get ratingPoor => 'Poor';

  @override
  String get ratingBelowAverage => 'Below average';

  @override
  String get ratingOkay => 'Okay';

  @override
  String get ratingGood => 'Good';

  @override
  String get ratingExcellent => 'Excellent';

  @override
  String get writeReview => 'Write a review (optional)';

  @override
  String get reviewHint => 'What went well, what could be better?';

  @override
  String get reviewHelper => 'Shown with your first name and last initial';

  @override
  String get whatWentWrong => 'What went wrong?';

  @override
  String get tellWhatHappened => 'Tell us what happened';

  @override
  String get atLeast3 => 'At least 3 characters';

  @override
  String get disputeServiceQuality => 'Poor service';

  @override
  String get disputeNoShow => 'Provider didn\'t show up';

  @override
  String get disputeDamage => 'Something was damaged';

  @override
  String get disputeBilling => 'Charged incorrectly';

  @override
  String get disputeOther => 'Something else';

  @override
  String get liveTracking => 'Live Tracking';

  @override
  String get yourProvider => 'Your provider';

  @override
  String get arrivingNow => 'Arriving now';

  @override
  String awayEstimate(int minutes, String distance) {
    return 'About $minutes min away · $distance';
  }

  @override
  String estimateFrom(String estimate, String place) {
    return '$estimate from $place';
  }

  @override
  String get findingProvider => 'Finding your provider…';

  @override
  String get waitingLocation =>
      'Waiting for your provider to share their location';

  @override
  String get justNow => 'just now';

  @override
  String minutesAgo(int minutes) {
    return '$minutes min ago';
  }

  @override
  String trackComingToCollect(String ago) {
    return 'Coming to collect your item · updated $ago';
  }

  @override
  String trackOnTheWay(String ago) {
    return 'On the way · updated $ago';
  }

  @override
  String trackTakingToShop(String ago) {
    return 'Taking your item to the shop · updated $ago';
  }

  @override
  String trackItemWorkedOn(String ago) {
    return 'Your item is being worked on · updated $ago';
  }

  @override
  String trackWorking(String ago) {
    return 'Working on your booking · updated $ago';
  }

  @override
  String trackBringingBack(String ago) {
    return 'Bringing your item back · updated $ago';
  }

  @override
  String trackAssigned(String ago) {
    return 'Provider assigned · updated $ago';
  }

  @override
  String starsReviewsSemantics(int stars, int count) {
    String _temp0 = intl.Intl.pluralLogic(
      stars,
      locale: localeName,
      other: '$stars stars',
      one: '1 star',
    );
    String _temp1 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count reviews',
      one: '1 review',
    );
    return '$_temp0: $_temp1';
  }

  @override
  String get verifiedBooking => 'Verified booking';

  @override
  String shopReply(String date) {
    return 'Reply from the shop · $date';
  }

  @override
  String get ratingsReviews => 'Ratings & reviews';

  @override
  String get noReviewsYetLong =>
      'No reviews yet. Customers can review the shop after a completed booking.';

  @override
  String seeAllReviews(int count) {
    return 'See all reviews ($count)';
  }

  @override
  String get allRatings => 'All ratings';

  @override
  String starsOnly(int stars) {
    String _temp0 = intl.Intl.pluralLogic(
      stars,
      locale: localeName,
      other: '$stars stars only',
      one: '1 star only',
    );
    return '$_temp0';
  }

  @override
  String get allFilter => 'All';

  @override
  String get loadingReviews => 'Loading reviews...';

  @override
  String get noReviewsYet => 'No reviews yet.';

  @override
  String noStarReviews(int stars) {
    return 'No $stars-star reviews yet.';
  }

  @override
  String get showMoreReviews => 'Show more reviews';

  @override
  String get reviewsTitle => 'Reviews';

  @override
  String reviewsOf(String shop) {
    return 'Reviews of $shop';
  }

  @override
  String get profileTitle => 'Profile';

  @override
  String get editProfile => 'Edit Profile';

  @override
  String get savedAddresses => 'Saved addresses';

  @override
  String get logout => 'Log out';

  @override
  String get logoutQuestion => 'Log out?';

  @override
  String get logoutBody =>
      'You\'ll need to sign in again to book or see your bookings.';

  @override
  String get accountDeleted => 'Your account has been deleted.';

  @override
  String get deleteMyAccount => 'Delete my account';

  @override
  String get deleteAccountQuestion => 'Delete your account?';

  @override
  String get deleteAccountBody =>
      'Your profile, saved addresses and sign-in are removed and cannot be recovered. Past bookings and payments are kept without your name for the shops\' records.';

  @override
  String get enterPasswordConfirm => 'Enter your password to confirm';

  @override
  String get deleteAccount => 'Delete account';

  @override
  String get settingTheme => 'Theme';

  @override
  String get themeSystem => 'System';

  @override
  String get themeLight => 'Light';

  @override
  String get themeDark => 'Dark';

  @override
  String get settingLanguage => 'Language';

  @override
  String get languageSystem => 'System';

  @override
  String get profileUpdated => 'Profile updated successfully';

  @override
  String get personalInfo => 'Personal Information';

  @override
  String get aboutYou => 'About you';

  @override
  String get optional => 'Optional';

  @override
  String get phoneNumber => 'Phone Number';

  @override
  String get phoneCantChange => 'Your sign-in number can\'t be changed here.';

  @override
  String get saveChanges => 'Save Changes';

  @override
  String get addressSaved => 'Address saved';

  @override
  String deleteAddressQuestion(String label) {
    return 'Delete \"$label\"?';
  }

  @override
  String get keepIt => 'Keep it';

  @override
  String get addressDeleted => 'Address deleted';

  @override
  String defaultAddressSet(String label) {
    return '$label is now your default address';
  }

  @override
  String get noAddresses => 'No saved addresses yet';

  @override
  String get noAddressesBody =>
      'Add your home or work address for home visits and pickups.';

  @override
  String addressOptions(String label) {
    return 'Options for $label';
  }

  @override
  String get makeDefault => 'Make default';

  @override
  String get newAddress => 'New address';

  @override
  String get addressDefaultLabel => 'Home';

  @override
  String get addressLabel => 'Label (Home, Work…)';

  @override
  String get addressStreet => 'Flat / house no., street, area';

  @override
  String get city => 'City';

  @override
  String get state => 'State';

  @override
  String get pinCode => 'PIN code';

  @override
  String get pinInvalid => 'Enter a 6-digit PIN code';

  @override
  String get offlineBanner =>
      'You\'re offline. Showing saved info; bookings will need a connection.';

  @override
  String get backOnline => 'Back online';

  @override
  String get helpTitle => 'Help & Support';

  @override
  String get helpSearchHint => 'Search help';

  @override
  String get helpFaqHeading => 'Common questions';

  @override
  String helpNoMatch(String query) {
    return 'No answers match \"$query\". Contact us below.';
  }

  @override
  String get helpContactHeading => 'Contact the Alakh support team';

  @override
  String get helpContactNote =>
      'Write to us or call. If it is about a booking, keep the booking number handy.';

  @override
  String get helpEmail => 'Email support';

  @override
  String get helpCall => 'Call support';

  @override
  String get helpReport => 'Report a problem with a booking';

  @override
  String get helpReportSubtitle =>
      'Pick the booking and tell us what went wrong';

  @override
  String get helpPickBooking => 'Which booking?';

  @override
  String get helpPickBookingNote =>
      'Bookings under way or finished are reported in the app; for others we open an email to support.';

  @override
  String get helpEmailInstead => 'Not listed? Email support';

  @override
  String get helpBookingsFailed => 'Couldn\'t load your bookings.';

  @override
  String helpCouldNotOpen(String email, String phone) {
    return 'Couldn\'t open that. Write to $email or call $phone.';
  }

  @override
  String get helpEmailSubject => 'AlakhService support';

  @override
  String helpEmailBookingSubject(String number) {
    return 'Problem with booking #$number';
  }

  @override
  String helpEmailBookingBody(String number) {
    return 'Booking number: $number\n\nWhat happened:\n';
  }

  @override
  String get faqTopicBooking => 'Booking';

  @override
  String get faqTopicCancel => 'Cancelling & rescheduling';

  @override
  String get faqTopicPayments => 'Payments & refunds';

  @override
  String get faqTopicPickup => 'Pickup & drop';

  @override
  String get faqTopicHome => 'Home visits';

  @override
  String get faqTopicReviews => 'Reviews';

  @override
  String get faqTopicAccount => 'Account & privacy';

  @override
  String get faqBookQ => 'How do I book a service?';

  @override
  String get faqBookA =>
      'Find the service on Home or Services and tap Book Now. Choose how you want it (at the shop, at your place or pickup & drop), pick a day and a free time, and confirm. The shop then confirms your request and we let you know.';

  @override
  String get faqNoTimesQ => 'Why can\'t I see any times on a day?';

  @override
  String get faqNoTimesA =>
      'The shop may be closed that day or fully booked, or today\'s times may have passed. The message under the dates says which; try another day.';

  @override
  String get faqCancelQ => 'How do I cancel a booking?';

  @override
  String get faqCancelA =>
      'Open Bookings and tap Cancel booking on it. You can cancel until the provider is on the way.';

  @override
  String get faqRescheduleQ => 'Can I change the time of a booking?';

  @override
  String get faqRescheduleA =>
      'Not in the app yet. Cancel the booking while you still can and book the new time. If the provider is already on the way, contact Alakh support.';

  @override
  String get faqPayQ => 'When and how do I pay?';

  @override
  String get faqPayA =>
      'Nothing is paid when you book. Once the shop confirms, tap Pay on the booking to pay online by UPI, card or net banking (through Razorpay), or choose to pay in cash when the job is done.';

  @override
  String get faqRefundQ => 'How do refunds work?';

  @override
  String get faqRefundA =>
      'When an online payment is refunded, the money goes back the way you paid; your bank may take a few working days to show it. The booking then shows Refunded. For a problem with a paid booking, report it and Alakh support will look into it.';

  @override
  String get faqPickupQ => 'How does pickup & drop work?';

  @override
  String get faqPickupA =>
      'Choose Pickup & drop when booking, pick the address and tell us what to collect. The item is collected, serviced at the shop and brought back. Bookings shows each step and when it is expected back.';

  @override
  String get faqHomeQ => 'How do home visits work?';

  @override
  String get faqHomeA =>
      'Choose At my place when booking and pick a saved address. A professional comes at the time you chose, and once they are on the way you can follow them live from Bookings. Any home visit fee is shown before you confirm.';

  @override
  String get faqReviewQ => 'How do I rate or review a shop?';

  @override
  String get faqReviewA =>
      'After a booking is completed, tap Rate on it in Bookings. Reviews show your first name and last initial and are marked Verified booking.';

  @override
  String get faqProblemQ =>
      'Something went wrong with my booking. What do I do?';

  @override
  String get faqProblemA =>
      'Tap Report a problem on the booking, or use \"Report a problem with a booking\" below. Alakh support looks into every report and gets back to you.';

  @override
  String get faqProfileQ => 'How do I change my name or addresses?';

  @override
  String get faqProfileA =>
      'In Profile, use Edit Profile for your name and Saved addresses for the places we come to. Your sign-in number can\'t be changed in the app; contact Alakh support for that.';

  @override
  String get faqSessionsQ => 'How do I sign out, or sign out of other devices?';

  @override
  String get faqSessionsA =>
      'Tap Log out in Profile to sign out on this phone. To sign out of all your other devices (a lost phone, say), choose a new password with Forgot Password on the sign-in screen: every other device is signed out. Alakh support can also help.';

  @override
  String get faqDeleteQ => 'How do I delete my account?';

  @override
  String get faqDeleteA =>
      'In Profile, tap Delete my account. Your profile, saved addresses and sign-in are removed; past bookings and payments are kept without your name for the shops\' records.';

  @override
  String get chatTitle => 'Chat with the shop';

  @override
  String get chatOpen => 'Chat';

  @override
  String chatUnread(int count) {
    return 'Chat, $count unread';
  }

  @override
  String get chatLoading => 'Loading messages…';

  @override
  String get chatEmpty =>
      'No messages yet. Ask the shop anything about this booking.';

  @override
  String get chatHint => 'Write a message';

  @override
  String get chatLoadEarlier => 'Load earlier messages';

  @override
  String get chatShop => 'Shop';

  @override
  String get chatRead => 'Read';

  @override
  String get chatSent => 'Sent';

  @override
  String get chatFlaggedHint => 'Contact details are hidden to keep you safe';

  @override
  String get chatClosed => 'This chat is closed. You can still read it.';

  @override
  String chatClosedSince(String when) {
    return 'This chat closed $when. You can still read it.';
  }

  @override
  String chatOpenUntil(String when) {
    return 'You can send messages until $when';
  }

  @override
  String get chatCallShop => 'Call shop';

  @override
  String get chatCallPlaced => 'We\'re calling you to connect you to the shop.';

  @override
  String get bookingDetailsTitle => 'Booking details';

  @override
  String get viewInvoice => 'View invoice';

  @override
  String get invoiceTitle => 'Invoice';

  @override
  String get invoiceLoading => 'Loading invoice…';

  @override
  String get paymentPartlyRefunded => 'Partly refunded';

  @override
  String get cancelPolicy =>
      'Free cancellation until 2 hours before your booking. After that, a cancellation fee may apply.';

  @override
  String get cancelPolicyLate =>
      'Your booking is less than 2 hours away, so a cancellation fee may apply.';

  @override
  String get termsRequired => 'Please accept the Terms and Privacy Policy';

  @override
  String get termsAgree => 'I agree to the';

  @override
  String get termsOfService => 'Terms of Service';

  @override
  String get termsAnd => 'and';

  @override
  String get privacyPolicy => 'Privacy Policy';

  @override
  String get legalSection => 'Legal';

  @override
  String get refundPolicy => 'Refund policy';

  @override
  String get grievanceOfficer => 'Grievance redressal';

  @override
  String get downloadMyData => 'Download my data';

  @override
  String get dataExportNone =>
      'Get a copy of your account, bookings and payments';

  @override
  String dataExportPending(String day) {
    return 'Requested: $day. We\'re preparing it.';
  }

  @override
  String get dataExportReady => 'Ready. Tap to download.';

  @override
  String get dataExportDeclined => 'Your last request was declined.';

  @override
  String get dataExportQuestion => 'Request a copy of your data?';

  @override
  String get dataExportBody =>
      'We\'ll prepare a file with your account, bookings and payments. You\'ll see here when it\'s ready to download.';

  @override
  String get dataExportRequest => 'Request';

  @override
  String get dataExportRequested => 'Request sent. We\'ll prepare your data.';

  @override
  String get view => 'View';
}
