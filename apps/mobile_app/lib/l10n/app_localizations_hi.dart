// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for Hindi (`hi`).
class AppLocalizationsHi extends AppLocalizations {
  AppLocalizationsHi([String locale = 'hi']) : super(locale);

  @override
  String get appTitle => 'AlakhService';

  @override
  String get cancel => 'रद्द करें';

  @override
  String get save => 'सेव करें';

  @override
  String get delete => 'हटाएँ';

  @override
  String get done => 'ठीक है';

  @override
  String get retry => 'फिर कोशिश करें';

  @override
  String get tryAgain => 'फिर कोशिश करें';

  @override
  String get tryAgainButton => 'फिर कोशिश करें';

  @override
  String get send => 'भेजें';

  @override
  String get submit => 'जमा करें';

  @override
  String get notNow => 'अभी नहीं';

  @override
  String get remove => 'हटाएँ';

  @override
  String get apply => 'लागू करें';

  @override
  String get loadingMore => 'लोड हो रहा है…';

  @override
  String get somethingWentWrong => 'कुछ गड़बड़ हो गई';

  @override
  String get showPassword => 'पासवर्ड दिखाएँ';

  @override
  String get hidePassword => 'पासवर्ड छिपाएँ';

  @override
  String get requiredField => 'ज़रूरी है';

  @override
  String get today => 'आज';

  @override
  String get tomorrow => 'कल';

  @override
  String get yesterday => 'बीता कल';

  @override
  String get midnight => 'रात 12';

  @override
  String get navHome => 'होम';

  @override
  String get navServices => 'सेवाएँ';

  @override
  String get navBookings => 'बुकिंग';

  @override
  String get navJobs => 'काम';

  @override
  String get navProfile => 'प्रोफ़ाइल';

  @override
  String get errorTimeout =>
      'सर्वर ने जवाब देने में बहुत देर लगाई। कृपया फिर कोशिश करें।';

  @override
  String get errorCannotReach =>
      'AlakhService से जुड़ नहीं पा रहे। अपना इंटरनेट कनेक्शन देखें।';

  @override
  String errorRequestFailed(int status) {
    return 'अनुरोध पूरा नहीं हुआ ($status)';
  }

  @override
  String get errorGeneric => 'कुछ गड़बड़ हो गई। कृपया फिर कोशिश करें।';

  @override
  String get errorNoInternet => 'इंटरनेट कनेक्शन नहीं है';

  @override
  String get vPhoneRequired => 'फ़ोन नंबर ज़रूरी है';

  @override
  String get vPhoneInvalid => 'सही फ़ोन नंबर डालें';

  @override
  String get vMobileRequired => 'मोबाइल नंबर ज़रूरी है';

  @override
  String get vMobileInvalid => 'सही 10 अंकों का मोबाइल नंबर डालें';

  @override
  String get vPhoneOrEmailRequired => 'अपना फ़ोन नंबर या ईमेल डालें';

  @override
  String get vPhoneOrEmailInvalid => 'सही फ़ोन नंबर या ईमेल डालें';

  @override
  String get vPasswordRequired => 'पासवर्ड ज़रूरी है';

  @override
  String get vPasswordRules =>
      'कम से कम 8 अक्षर, जिनमें एक कैपिटल अक्षर और एक अंक हो';

  @override
  String get vEmailRequired => 'ईमेल ज़रूरी है';

  @override
  String get vEmailInvalid => 'सही ईमेल पता डालें';

  @override
  String get vPasswordShort => 'पासवर्ड कम से कम 8 अक्षरों का होना चाहिए';

  @override
  String get vPasswordUpper => 'कम से कम एक कैपिटल अक्षर डालें';

  @override
  String get vPasswordNumber => 'कम से कम एक अंक डालें';

  @override
  String get vOtpRequired => 'OTP ज़रूरी है';

  @override
  String get vOtpInvalid => 'सही 6 अंकों का OTP डालें';

  @override
  String get vNameRequired => 'नाम ज़रूरी है';

  @override
  String get vNameShort => 'नाम कम से कम 2 अक्षरों का होना चाहिए';

  @override
  String get vFieldRequired => 'यह जानकारी ज़रूरी है';

  @override
  String vFieldRequiredNamed(String field) {
    return '$field ज़रूरी है';
  }

  @override
  String vFieldMinLength(String field, String min) {
    return '$field कम से कम $min अक्षरों का होना चाहिए';
  }

  @override
  String get vConfirmPassword => 'कृपया पासवर्ड दोबारा डालें';

  @override
  String get vPasswordsDontMatch => 'पासवर्ड मेल नहीं खाते';

  @override
  String get loginWelcome => 'फिर से स्वागत है';

  @override
  String get loginSubtitle =>
      'सेवाएँ बुक करने, ट्रैक करने और भुगतान करने के लिए साइन इन करें';

  @override
  String get loginPhoneOrEmail => 'फ़ोन या ईमेल';

  @override
  String get loginPhoneOrEmailHint => '98765 43210 या you@example.com';

  @override
  String get password => 'पासवर्ड';

  @override
  String get loginPasswordHint => 'अपना पासवर्ड डालें';

  @override
  String get loginForgot => 'पासवर्ड भूल गए?';

  @override
  String get loginButton => 'लॉग इन करें';

  @override
  String get loginWithOtp => 'इसके बजाय OTP से लॉग इन करें';

  @override
  String get loginNoAccount => 'खाता नहीं है?';

  @override
  String get loginRegister => 'रजिस्टर करें';

  @override
  String get registerTitle => 'खाता बनाएँ';

  @override
  String get registerHeading => 'AlakhService से जुड़ें';

  @override
  String get registerSubtitle => 'शुरू करने के लिए अपना खाता बनाएँ';

  @override
  String get fullName => 'पूरा नाम';

  @override
  String get registerNameHint => 'जैसे प्रिया शर्मा';

  @override
  String get mobileNumber => 'मोबाइल नंबर';

  @override
  String get registerPasswordHint => 'पासवर्ड चुनें';

  @override
  String get registerCodeNote => 'हम इस नंबर पर SMS से एक पुष्टि कोड भेजेंगे।';

  @override
  String get registerButton => 'खाता बनाएँ';

  @override
  String get registerHaveAccount => 'पहले से खाता है?';

  @override
  String get otpTitleLogin => 'OTP से लॉग इन';

  @override
  String get otpTitleVerifyPhone => 'अपने फ़ोन की पुष्टि करें';

  @override
  String get otpTitleVerifyEmail => 'अपने ईमेल की पुष्टि करें';

  @override
  String get otpResent => 'नया कोड भेजा जा रहा है';

  @override
  String get otpEnterCode => 'कोड डालें';

  @override
  String otpSentTo(int length, String destination) {
    return 'हमने $destination पर $length अंकों का कोड भेजा है।';
  }

  @override
  String get otpWrongPhone => 'फ़ोन नंबर गलत है? बदलें';

  @override
  String get otpWrongEmail => 'ईमेल गलत है? बदलें';

  @override
  String get otpFieldLabel => 'एक बार का कोड (OTP)';

  @override
  String get otpVerifyLogin => 'पुष्टि करें और लॉग इन करें';

  @override
  String get otpVerify => 'पुष्टि करें';

  @override
  String otpResendIn(int seconds) {
    return 'कोड नहीं मिला? $seconds सेकंड में दोबारा भेज सकते हैं';
  }

  @override
  String get otpResend => 'कोड नहीं मिला? दोबारा भेजें';

  @override
  String get forgotTitle => 'पासवर्ड भूल गए';

  @override
  String get resetPassword => 'नया पासवर्ड बनाएँ';

  @override
  String get forgotIntro =>
      'अपने खाते का फ़ोन नंबर या ईमेल डालें, हम आपको एक कोड भेजेंगे।';

  @override
  String forgotEnterCode(String destination) {
    return '$destination पर भेजा गया कोड डालें और नया पासवर्ड चुनें।';
  }

  @override
  String get forgotDifferent => 'कोई दूसरा फ़ोन या ईमेल इस्तेमाल करें';

  @override
  String get code => 'कोड';

  @override
  String get codeHint => '6 अंकों का कोड';

  @override
  String get newPassword => 'नया पासवर्ड';

  @override
  String get newPasswordHint => 'नया पासवर्ड चुनें';

  @override
  String get sendCode => 'कोड भेजें';

  @override
  String get passwordChanged => 'पासवर्ड बदल गया';

  @override
  String get passwordChangedBody =>
      'नए पासवर्ड से साइन इन करें। दूसरे डिवाइस से आपको साइन आउट कर दिया गया है।';

  @override
  String get backToLogin => 'लॉग इन पर वापस जाएँ';

  @override
  String get greetingMorning => 'सुप्रभात';

  @override
  String get greetingAfternoon => 'नमस्ते';

  @override
  String get greetingEvening => 'शुभ संध्या';

  @override
  String get homeFindService => 'सेवा खोजें';

  @override
  String get searchHint => 'हेयरकट, AC रिपेयर, डॉक्टर खोजें…';

  @override
  String get searchServicesHint => 'सेवाएँ खोजें...';

  @override
  String get homeOurServices => 'हमारी सेवाएँ';

  @override
  String get homePopular => 'लोकप्रिय सेवाएँ';

  @override
  String get homeLoadFailed => 'सेवाएँ लोड नहीं हो सकीं।';

  @override
  String get homeNoServices => 'अभी कोई सेवा नहीं जुड़ी है।';

  @override
  String get notifications => 'सूचनाएँ';

  @override
  String notificationsUnread(int count) {
    return 'सूचनाएँ, $count बिना पढ़ी';
  }

  @override
  String get catHaircut => 'हेयरकट';

  @override
  String get catBeauty => 'ब्यूटी पार्लर';

  @override
  String get catDoctor => 'डॉक्टर';

  @override
  String get catOffice => 'दफ़्तर के काम';

  @override
  String get catCar => 'कार रिपेयर';

  @override
  String get catBike => 'बाइक रिपेयर';

  @override
  String get catDevices => 'लैपटॉप और फ़ोन';

  @override
  String get catAc => 'AC रिपेयर';

  @override
  String get catCleaning => 'सफ़ाई';

  @override
  String get catPlumbing => 'प्लंबिंग';

  @override
  String get catElectrical => 'बिजली का काम';

  @override
  String get catCarpentry => 'बढ़ई का काम';

  @override
  String get catPest => 'कीड़े-मकोड़े भगाना';

  @override
  String get catHandyman => 'घर की मरम्मत';

  @override
  String get bannerTrack => 'अपनी बुकिंग\nट्रैक करें';

  @override
  String get bannerMyBookings => 'मेरी बुकिंग';

  @override
  String get bannerSemantics => 'अपनी बुकिंग ट्रैक करें। मेरी बुकिंग';

  @override
  String get nextBooking => 'आपकी अगली बुकिंग';

  @override
  String nextBookingSemantics(String service, String when, String statusText) {
    return 'आपकी अगली बुकिंग: $service, $when, $statusText। मेरी बुकिंग खोलें';
  }

  @override
  String get servicesTitle => 'सेवाएँ';

  @override
  String get clearSearch => 'खोज मिटाएँ';

  @override
  String get loadingServices => 'सेवाएँ लोड हो रही हैं...';

  @override
  String get noServicesListed => 'अभी कोई सेवा नहीं जुड़ी है';

  @override
  String nothingFound(String query) {
    return '\"$query\" के लिए कुछ नहीं मिला';
  }

  @override
  String get pullToCheck => 'दोबारा देखने के लिए नीचे खींचें।';

  @override
  String get tryDifferentWord => 'छोटा या कोई दूसरा शब्द आज़माएँ।';

  @override
  String get showAllServices => 'सभी सेवाएँ दिखाएँ';

  @override
  String get modeHomeVisit => 'घर पर सेवा';

  @override
  String get modePickupDrop => 'पिकअप और ड्रॉप';

  @override
  String get modeAtShop => 'दुकान पर';

  @override
  String get unavailable => 'उपलब्ध नहीं';

  @override
  String minutesShort(int minutes) {
    return '$minutes मिनट';
  }

  @override
  String get ratingNew => 'नया';

  @override
  String get ratingNewSemantics => 'नया, अभी कोई समीक्षा नहीं';

  @override
  String ratedSemantics(String rating, int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count समीक्षाओं',
      one: '1 समीक्षा',
    );
    return '$_temp0 से 5 में से $rating रेटिंग';
  }

  @override
  String starsLabel(String rating) {
    return '5 में से $rating स्टार';
  }

  @override
  String reviewsCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count समीक्षाएँ',
      one: '1 समीक्षा',
    );
    return '$_temp0';
  }

  @override
  String get serviceNotTaking => 'यह सेवा अभी बुकिंग नहीं ले रही है।';

  @override
  String get priceFrom => 'शुरुआती कीमत';

  @override
  String get bookNow => 'अभी बुक करें';

  @override
  String aboutMinutes(int minutes) {
    return 'लगभग $minutes मिनट';
  }

  @override
  String get howYouCanGetIt => 'यह सेवा कैसे मिलेगी';

  @override
  String get modeAtYourPlace => 'आपके घर पर';

  @override
  String get modeAtTheShop => 'दुकान पर';

  @override
  String get aboutService => 'इस सेवा के बारे में';

  @override
  String get noDescription => 'दुकान ने अभी विवरण नहीं जोड़ा है।';

  @override
  String get joinQueue => 'अभी आएँ: कतार में जुड़ें';

  @override
  String get joinQueueNote =>
      'अपॉइंटमेंट की ज़रूरत नहीं: हम आपको कतार में आपकी जगह और आपकी बारी बताएँगे।';

  @override
  String get howToGetThere => 'वहाँ कैसे पहुँचें';

  @override
  String hoursOpenCloses(String time) {
    return 'अभी खुला है · $time पर बंद होगा';
  }

  @override
  String hoursClosedOpens(String time) {
    return 'बंद है · $time पर खुलेगा';
  }

  @override
  String hoursClosedOpensTomorrow(String time) {
    return 'बंद है · कल $time पर खुलेगा';
  }

  @override
  String hoursClosedOpensDay(String day, String time) {
    return 'बंद है · $day को $time पर खुलेगा';
  }

  @override
  String get hoursClosed => 'बंद है';

  @override
  String get bookServiceTitle => 'सेवा बुक करें';

  @override
  String get howWouldYouLikeIt => 'आप यह सेवा कैसे लेना चाहेंगे?';

  @override
  String get whenQuestion => 'कब?';

  @override
  String get timesLoadFailed => 'इस दिन के समय लोड नहीं हो सके';

  @override
  String get findingTimes => 'खाली समय ढूँढ रहे हैं…';

  @override
  String get partMorning => 'सुबह';

  @override
  String get partAfternoon => 'दोपहर';

  @override
  String get partEvening => 'शाम';

  @override
  String get pickATime => 'समय चुनें';

  @override
  String get noMoreTimesToday =>
      'आज और कोई समय खाली नहीं — कोई दूसरा दिन चुनें';

  @override
  String get closedOnDay => 'इस दिन बंद है';

  @override
  String closedOnDayNote(String note) {
    return 'इस दिन बंद है ($note)';
  }

  @override
  String get fullyBooked => 'सारी जगह भर गई — कोई दूसरा दिन चुनें';

  @override
  String get noTimesOnDay => 'इस दिन कोई समय नहीं — कोई दूसरा दिन चुनें';

  @override
  String get collectFrom => 'सामान कहाँ से लेना है';

  @override
  String get whereShouldWeCome => 'हम कहाँ आएँ?';

  @override
  String get noSavedAddress => 'आपका कोई पता अभी सेव नहीं है।';

  @override
  String get addAddress => 'पता जोड़ें';

  @override
  String get savedAddress => 'सेव किया हुआ पता';

  @override
  String get addAnotherAddress => 'दूसरा पता जोड़ें';

  @override
  String get whatToCollect => 'हमें क्या ले जाना है?';

  @override
  String get whatToCollectHint =>
      'जैसे Honda Activa, ब्रेक से आवाज़ · Dell लैपटॉप, स्क्रीन टूटी';

  @override
  String get whatToCollectError =>
      'बताएँ कि क्या ले जाना है और उसमें क्या खराबी है';

  @override
  String get notesOptional => 'नोट (अगर कुछ बताना हो)';

  @override
  String get notesHint => 'कोई खास निर्देश...';

  @override
  String get couponOptional => 'कूपन कोड (अगर हो)';

  @override
  String get couponHint => 'जैसे WELCOME10';

  @override
  String get checking => 'जाँच रहे हैं…';

  @override
  String get homeVisitFee => 'घर आने का शुल्क';

  @override
  String get pickupDropFee => 'पिकअप और ड्रॉप शुल्क';

  @override
  String get snackPickTime => 'अपनी बुकिंग के लिए समय चुनें';

  @override
  String get snackAddAddress => 'वह पता जोड़ें जहाँ हमें आना है';

  @override
  String get snackFillDetails => 'कृपया हाइलाइट की गई जानकारी भरें';

  @override
  String get bookingRequested => 'बुकिंग का अनुरोध भेज दिया गया';

  @override
  String bookingNumber(String number) {
    return 'बुकिंग #$number';
  }

  @override
  String get bookingRequestedBody =>
      'दुकान को आपका अनुरोध स्वीकार करना होगा। हम आपको बताएँगे, और पुष्टि के बाद आप भुगतान कर सकते हैं।';

  @override
  String get viewMyBookings => 'मेरी बुकिंग देखें';

  @override
  String couponApplied(String code, String percent, String saving) {
    return '$code लागू हुआ: $percent% छूट, आपकी बचत $saving';
  }

  @override
  String get priceDetails => 'कीमत का ब्योरा';

  @override
  String get priceService => 'सेवा';

  @override
  String priceCoupon(String code) {
    return 'कूपन $code';
  }

  @override
  String get total => 'कुल';

  @override
  String get payLaterNote =>
      'अभी कुछ नहीं देना है। दुकान की पुष्टि के बाद ऑनलाइन या नकद भुगतान करें।';

  @override
  String get confirmBooking => 'बुकिंग पक्की करें';

  @override
  String get chooseDayTime => 'नीचे दिन और समय चुनें';

  @override
  String get modeChoiceAtHome => 'मेरे घर पर';

  @override
  String get modeChoiceAtShop => 'दुकान पर जाएँ';

  @override
  String get explainAtHome =>
      'आपके चुने हुए समय पर एक प्रोफ़ेशनल आपके पते पर आएगा।';

  @override
  String get explainPickup =>
      'हम आपका सामान आपके पते से ले जाएँगे, ठीक करके वापस लाएँगे। हर कदम पर आपको बताया जाएगा।';

  @override
  String get explainAtShop =>
      'आप चुने हुए समय पर दुकान जाएँ। रास्ता अपनी बुकिंग में \"वहाँ कैसे पहुँचें\" में देखें।';

  @override
  String get myBookings => 'मेरी बुकिंग';

  @override
  String get statusPending => 'दुकान के जवाब का इंतज़ार';

  @override
  String get statusConfirmed => 'पक्की हो गई';

  @override
  String get statusAssigned => 'प्रोफ़ेशनल तय हो गया';

  @override
  String get statusEnRoute => 'प्रोफ़ेशनल रास्ते में है';

  @override
  String get statusPickedUp => 'सामान ले लिया गया';

  @override
  String get statusInProgress => 'काम चल रहा है';

  @override
  String get statusOutForDelivery => 'वापस आ रहा है';

  @override
  String get statusCompleted => 'पूरी हो गई';

  @override
  String get statusCancelled => 'रद्द हो गई';

  @override
  String get statusDisputed => 'समस्या दर्ज है';

  @override
  String get statusRefunded => 'पैसे वापस हो गए';

  @override
  String get cancelBookingQuestion => 'यह बुकिंग रद्द करें?';

  @override
  String cancelBookingBody(String service, String when) {
    return '$service, $when, रद्द हो जाएगी। इसे वापस नहीं किया जा सकता।';
  }

  @override
  String get keepBooking => 'बुकिंग रखें';

  @override
  String get yesCancel => 'हाँ, रद्द करें';

  @override
  String get thanksRating => 'रेटिंग देने के लिए धन्यवाद!';

  @override
  String get thanksReview =>
      'समीक्षा के लिए धन्यवाद! इससे दूसरों को चुनने में मदद मिलती है।';

  @override
  String get reportThanks =>
      'धन्यवाद। हमारी सपोर्ट टीम इसे देखेगी और आपसे संपर्क करेगी।';

  @override
  String get bookingCancelled => 'बुकिंग रद्द हो गई';

  @override
  String get loadingBookings => 'बुकिंग लोड हो रही हैं...';

  @override
  String get noBookings => 'अभी कोई बुकिंग नहीं';

  @override
  String get noBookingsBody =>
      'सैलून, डॉक्टर, रिपेयर और बहुत कुछ बुक करें। आपकी बुकिंग यहाँ दिखेंगी।';

  @override
  String get browseServices => 'सेवाएँ देखें';

  @override
  String get upcomingActive => 'आने वाली और चालू';

  @override
  String get pastBookings => 'पुरानी';

  @override
  String get track => 'ट्रैक करें';

  @override
  String get payOnlineInstead => 'इसके बजाय ऑनलाइन भुगतान करें';

  @override
  String payAmount(String amount) {
    return '$amount का भुगतान करें';
  }

  @override
  String get rate => 'रेटिंग दें';

  @override
  String get reportProblem => 'समस्या बताएँ';

  @override
  String get cancelling => 'रद्द हो रही है…';

  @override
  String get cancelBooking => 'बुकिंग रद्द करें';

  @override
  String get overduePending =>
      'यह समय निकल गया और दुकान ने पुष्टि नहीं की। आप इसे रद्द करके कोई दूसरा समय बुक कर सकते हैं।';

  @override
  String get overdueConfirmed =>
      'यह समय निकल गया। अगर आप नहीं पहुँच पाए, तो Alakh सपोर्ट से संपर्क करें या बुकिंग रद्द करें।';

  @override
  String expectedBackBy(String when) {
    return '$when तक वापस आने की उम्मीद';
  }

  @override
  String get paid => 'भुगतान हो गया';

  @override
  String get payingCash => 'नकद भुगतान';

  @override
  String youRated(int stars) {
    return 'आपने $stars★ दिए';
  }

  @override
  String get howWasIt => 'कैसा रहा?';

  @override
  String starsCount(int count) {
    return '$count स्टार';
  }

  @override
  String get ratingPoor => 'खराब';

  @override
  String get ratingBelowAverage => 'औसत से कम';

  @override
  String get ratingOkay => 'ठीक-ठाक';

  @override
  String get ratingGood => 'अच्छा';

  @override
  String get ratingExcellent => 'बहुत बढ़िया';

  @override
  String get writeReview => 'समीक्षा लिखें (अगर चाहें)';

  @override
  String get reviewHint => 'क्या अच्छा रहा, क्या बेहतर हो सकता था?';

  @override
  String get reviewHelper =>
      'आपके पहले नाम और उपनाम के पहले अक्षर के साथ दिखेगी';

  @override
  String get whatWentWrong => 'क्या गड़बड़ हुई?';

  @override
  String get tellWhatHappened => 'बताएँ क्या हुआ';

  @override
  String get atLeast3 => 'कम से कम 3 अक्षर';

  @override
  String get disputeServiceQuality => 'सेवा खराब थी';

  @override
  String get disputeNoShow => 'प्रोफ़ेशनल नहीं आया';

  @override
  String get disputeDamage => 'कुछ नुकसान हुआ';

  @override
  String get disputeBilling => 'गलत पैसे लिए गए';

  @override
  String get disputeOther => 'कुछ और';

  @override
  String get liveTracking => 'लाइव ट्रैकिंग';

  @override
  String get yourProvider => 'आपका प्रोफ़ेशनल';

  @override
  String get arrivingNow => 'बस पहुँचने वाले हैं';

  @override
  String awayEstimate(int minutes, String distance) {
    return 'लगभग $minutes मिनट दूर · $distance';
  }

  @override
  String estimateFrom(String estimate, String place) {
    return '$place से $estimate';
  }

  @override
  String get findingProvider => 'आपके प्रोफ़ेशनल को ढूँढ रहे हैं…';

  @override
  String get waitingLocation => 'प्रोफ़ेशनल की लोकेशन मिलने का इंतज़ार है';

  @override
  String get justNow => 'अभी-अभी';

  @override
  String minutesAgo(int minutes) {
    return '$minutes मिनट पहले';
  }

  @override
  String trackComingToCollect(String ago) {
    return 'आपका सामान लेने आ रहे हैं · $ago अपडेट हुआ';
  }

  @override
  String trackOnTheWay(String ago) {
    return 'रास्ते में हैं · $ago अपडेट हुआ';
  }

  @override
  String trackTakingToShop(String ago) {
    return 'आपका सामान दुकान ले जा रहे हैं · $ago अपडेट हुआ';
  }

  @override
  String trackItemWorkedOn(String ago) {
    return 'आपके सामान पर काम चल रहा है · $ago अपडेट हुआ';
  }

  @override
  String trackWorking(String ago) {
    return 'आपकी बुकिंग पर काम चल रहा है · $ago अपडेट हुआ';
  }

  @override
  String trackBringingBack(String ago) {
    return 'आपका सामान वापस ला रहे हैं · $ago अपडेट हुआ';
  }

  @override
  String trackAssigned(String ago) {
    return 'प्रोफ़ेशनल तय हो गया · $ago अपडेट हुआ';
  }

  @override
  String starsReviewsSemantics(int stars, int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count समीक्षाएँ',
      one: '1 समीक्षा',
    );
    return '$stars स्टार: $_temp0';
  }

  @override
  String get verifiedBooking => 'पुष्ट बुकिंग';

  @override
  String shopReply(String date) {
    return 'दुकान का जवाब · $date';
  }

  @override
  String get ratingsReviews => 'रेटिंग और समीक्षाएँ';

  @override
  String get noReviewsYetLong =>
      'अभी कोई समीक्षा नहीं। बुकिंग पूरी होने के बाद ग्राहक दुकान की समीक्षा कर सकते हैं।';

  @override
  String seeAllReviews(int count) {
    return 'सभी समीक्षाएँ देखें ($count)';
  }

  @override
  String get allRatings => 'सभी रेटिंग';

  @override
  String starsOnly(int stars) {
    return 'केवल $stars स्टार';
  }

  @override
  String get allFilter => 'सभी';

  @override
  String get loadingReviews => 'समीक्षाएँ लोड हो रही हैं...';

  @override
  String get noReviewsYet => 'अभी कोई समीक्षा नहीं।';

  @override
  String noStarReviews(int stars) {
    return 'अभी कोई $stars-स्टार समीक्षा नहीं।';
  }

  @override
  String get showMoreReviews => 'और समीक्षाएँ दिखाएँ';

  @override
  String get reviewsTitle => 'समीक्षाएँ';

  @override
  String reviewsOf(String shop) {
    return '$shop की समीक्षाएँ';
  }

  @override
  String get profileTitle => 'मेरी प्रोफ़ाइल और काम की फ़ोटो';

  @override
  String get editProfile => 'प्रोफ़ाइल बदलें';

  @override
  String get savedAddresses => 'सेव किए गए पते';

  @override
  String get logout => 'लॉग आउट करें';

  @override
  String get logoutQuestion => 'लॉग आउट करें?';

  @override
  String get logoutBody =>
      'बुक करने या अपनी बुकिंग देखने के लिए आपको फिर से साइन इन करना होगा।';

  @override
  String get accountDeleted => 'आपका खाता हटा दिया गया है।';

  @override
  String get deleteMyAccount => 'मेरा खाता हटाएँ';

  @override
  String get deleteAccountQuestion => 'अपना खाता हटाएँ?';

  @override
  String get deleteAccountBody =>
      'आपकी प्रोफ़ाइल, सेव किए गए पते और साइन-इन हटा दिए जाएँगे और वापस नहीं मिलेंगे। पुरानी बुकिंग और भुगतान दुकानों के रिकॉर्ड के लिए आपके नाम के बिना रखे जाएँगे।';

  @override
  String get enterPasswordConfirm => 'पुष्टि के लिए अपना पासवर्ड डालें';

  @override
  String get deleteAccount => 'खाता हटाएँ';

  @override
  String get settingTheme => 'थीम';

  @override
  String get themeSystem => 'फ़ोन के अनुसार';

  @override
  String get themeLight => 'हल्की (लाइट)';

  @override
  String get themeDark => 'गहरी (डार्क)';

  @override
  String get settingLanguage => 'भाषा';

  @override
  String get languageSystem => 'फ़ोन के अनुसार';

  @override
  String get profileUpdated => 'प्रोफ़ाइल अपडेट हो गई';

  @override
  String get personalInfo => 'निजी जानकारी';

  @override
  String get aboutYou => 'आपके बारे में';

  @override
  String get optional => 'अगर चाहें';

  @override
  String get phoneNumber => 'फ़ोन नंबर';

  @override
  String get phoneCantChange => 'आपका साइन-इन नंबर यहाँ नहीं बदला जा सकता।';

  @override
  String get saveChanges => 'बदलाव सेव करें';

  @override
  String get addressSaved => 'पता सेव हो गया';

  @override
  String deleteAddressQuestion(String label) {
    return '\"$label\" हटाएँ?';
  }

  @override
  String get keepIt => 'रहने दें';

  @override
  String get addressDeleted => 'पता हटा दिया गया';

  @override
  String defaultAddressSet(String label) {
    return '$label अब आपका डिफ़ॉल्ट पता है';
  }

  @override
  String get noAddresses => 'अभी कोई पता सेव नहीं है';

  @override
  String get noAddressesBody =>
      'घर पर सेवा और पिकअप के लिए अपने घर या दफ़्तर का पता जोड़ें।';

  @override
  String addressOptions(String label) {
    return '$label के विकल्प';
  }

  @override
  String get makeDefault => 'डिफ़ॉल्ट बनाएँ';

  @override
  String get newAddress => 'नया पता';

  @override
  String get addressDefaultLabel => 'घर';

  @override
  String get addressLabel => 'नाम (घर, दफ़्तर…)';

  @override
  String get addressStreet => 'फ़्लैट / मकान नं., गली, इलाका';

  @override
  String get city => 'शहर';

  @override
  String get state => 'राज्य';

  @override
  String get pinCode => 'पिन कोड';

  @override
  String get pinInvalid => '6 अंकों का पिन कोड डालें';

  @override
  String get offlineBanner =>
      'आप ऑफ़लाइन हैं। सेव की गई जानकारी दिख रही है; बुकिंग के लिए इंटरनेट चाहिए।';

  @override
  String get backOnline => 'फिर से ऑनलाइन';

  @override
  String get helpTitle => 'मदद और सहायता';

  @override
  String get helpSearchHint => 'मदद में खोजें';

  @override
  String get helpFaqHeading => 'आम सवाल';

  @override
  String helpNoMatch(String query) {
    return '\"$query\" से मिलता कोई जवाब नहीं। नीचे हमसे संपर्क करें।';
  }

  @override
  String get helpContactHeading => 'Alakh सपोर्ट टीम से संपर्क करें';

  @override
  String get helpContactNote =>
      'हमें लिखें या कॉल करें। बुकिंग से जुड़ी बात हो तो बुकिंग नंबर साथ रखें।';

  @override
  String get helpEmail => 'सपोर्ट को ईमेल करें';

  @override
  String get helpCall => 'सपोर्ट को कॉल करें';

  @override
  String get helpReport => 'बुकिंग से जुड़ी समस्या बताएँ';

  @override
  String get helpReportSubtitle => 'बुकिंग चुनें और बताएँ क्या गड़बड़ हुई';

  @override
  String get helpPickBooking => 'कौन-सी बुकिंग?';

  @override
  String get helpPickBookingNote =>
      'चालू या पूरी हो चुकी बुकिंग की समस्या ऐप में दर्ज होती है; बाकी के लिए सपोर्ट को ईमेल खुलेगा।';

  @override
  String get helpEmailInstead => 'सूची में नहीं है? सपोर्ट को ईमेल करें';

  @override
  String get helpBookingsFailed => 'आपकी बुकिंग लोड नहीं हो सकीं।';

  @override
  String helpCouldNotOpen(String email, String phone) {
    return 'यह नहीं खुल सका। $email पर लिखें या $phone पर कॉल करें।';
  }

  @override
  String get helpEmailSubject => 'AlakhService सपोर्ट';

  @override
  String helpEmailBookingSubject(String number) {
    return 'बुकिंग #$number में समस्या';
  }

  @override
  String helpEmailBookingBody(String number) {
    return 'बुकिंग नंबर: $number\n\nक्या हुआ:\n';
  }

  @override
  String get faqTopicBooking => 'बुकिंग';

  @override
  String get faqTopicCancel => 'रद्द करना और समय बदलना';

  @override
  String get faqTopicPayments => 'भुगतान और पैसे वापसी';

  @override
  String get faqTopicPickup => 'पिकअप और ड्रॉप';

  @override
  String get faqTopicHome => 'घर पर सेवा';

  @override
  String get faqTopicReviews => 'समीक्षाएँ';

  @override
  String get faqTopicAccount => 'खाता और प्राइवेसी';

  @override
  String get faqBookQ => 'सेवा कैसे बुक करें?';

  @override
  String get faqBookA =>
      'होम या सेवाएँ में सेवा खोजें और \"अभी बुक करें\" दबाएँ। तरीका चुनें (दुकान पर, आपके घर पर या पिकअप और ड्रॉप), दिन और खाली समय चुनें और पक्का करें। फिर दुकान आपके अनुरोध की पुष्टि करती है और हम आपको बताते हैं।';

  @override
  String get faqNoTimesQ => 'किसी दिन कोई समय क्यों नहीं दिख रहा?';

  @override
  String get faqNoTimesA =>
      'उस दिन दुकान बंद हो सकती है या सारी जगह भर चुकी हो सकती है, या आज के समय निकल चुके हों। तारीखों के नीचे लिखा संदेश वजह बताता है; कोई दूसरा दिन चुनें।';

  @override
  String get faqCancelQ => 'बुकिंग कैसे रद्द करें?';

  @override
  String get faqCancelA =>
      '\"बुकिंग\" खोलें और उस पर \"बुकिंग रद्द करें\" दबाएँ। प्रोफ़ेशनल के रास्ते में निकलने तक आप रद्द कर सकते हैं।';

  @override
  String get faqRescheduleQ => 'क्या बुकिंग का समय बदला जा सकता है?';

  @override
  String get faqRescheduleA =>
      'हाँ। बुकिंग खोलें और \'समय बदलें\' दबाएँ। हर बुकिंग का समय दो बार तक, शुरू होने से 2 घंटे पहले तक बदला जा सकता है, जब तक कोई प्रोफ़ेशनल तय नहीं हुआ है। उसके बाद बुकिंग की चैट से दुकान को मैसेज करें।';

  @override
  String get faqPayQ => 'भुगतान कब और कैसे करें?';

  @override
  String get faqPayA =>
      'बुक करते समय कुछ नहीं देना होता। दुकान की पुष्टि के बाद बुकिंग पर \"भुगतान करें\" दबाकर UPI, कार्ड या नेट बैंकिंग से (Razorpay के ज़रिए) ऑनलाइन भुगतान करें, या काम पूरा होने पर नकद देना चुनें।';

  @override
  String get faqRefundQ => 'पैसे वापसी (रिफ़ंड) कैसे होती है?';

  @override
  String get faqRefundA =>
      'ऑनलाइन भुगतान वापस होने पर पैसे उसी तरीके से लौटते हैं जिससे आपने भुगतान किया था; बैंक में दिखने में कुछ कामकाजी दिन लग सकते हैं। फिर बुकिंग पर \"पैसे वापस हो गए\" दिखता है। भुगतान की हुई बुकिंग में समस्या हो तो उसे दर्ज करें, Alakh सपोर्ट उसे देखेगी।';

  @override
  String get faqPickupQ => 'पिकअप और ड्रॉप कैसे काम करता है?';

  @override
  String get faqPickupA =>
      'बुक करते समय \"पिकअप और ड्रॉप\" चुनें, पता चुनें और बताएँ कि क्या ले जाना है। सामान ले जाकर दुकान पर ठीक किया जाता है और वापस पहुँचाया जाता है। \"बुकिंग\" में हर कदम और वापसी का अनुमानित समय दिखता है।';

  @override
  String get faqHomeQ => 'घर पर सेवा कैसे मिलती है?';

  @override
  String get faqHomeA =>
      'बुक करते समय \"मेरे घर पर\" चुनें और सेव किया हुआ पता चुनें। आपके चुने समय पर प्रोफ़ेशनल आएगा, और रास्ते में होने पर आप \"बुकिंग\" से उसे लाइव देख सकते हैं। घर आने का शुल्क हो तो पक्का करने से पहले दिखता है।';

  @override
  String get faqReviewQ => 'दुकान को रेटिंग या समीक्षा कैसे दें?';

  @override
  String get faqReviewA =>
      'बुकिंग पूरी होने के बाद \"बुकिंग\" में उस पर \"रेटिंग दें\" दबाएँ। समीक्षा में आपका पहला नाम और उपनाम का पहला अक्षर दिखता है, और उस पर \"पुष्ट बुकिंग\" लिखा होता है।';

  @override
  String get faqProblemQ => 'बुकिंग में कुछ गड़बड़ हुई। क्या करूँ?';

  @override
  String get faqProblemA =>
      'बुकिंग पर \"समस्या बताएँ\" दबाएँ, या नीचे \"बुकिंग से जुड़ी समस्या बताएँ\" चुनें। Alakh सपोर्ट हर शिकायत देखती है और आपसे संपर्क करती है।';

  @override
  String get faqProfileQ => 'अपना नाम या पते कैसे बदलें?';

  @override
  String get faqProfileA =>
      'प्रोफ़ाइल में नाम के लिए \"प्रोफ़ाइल बदलें\" और पतों के लिए \"सेव किए गए पते\" इस्तेमाल करें। साइन-इन नंबर ऐप में नहीं बदला जा सकता; इसके लिए Alakh सपोर्ट से संपर्क करें।';

  @override
  String get faqSessionsQ =>
      'साइन आउट कैसे करें, या दूसरे फ़ोन से साइन आउट कैसे करें?';

  @override
  String get faqSessionsA =>
      'इस फ़ोन से साइन आउट करने के लिए प्रोफ़ाइल में \"लॉग आउट करें\" दबाएँ। बाकी सभी डिवाइस से साइन आउट करने के लिए (जैसे फ़ोन खो जाने पर) साइन-इन स्क्रीन पर \"पासवर्ड भूल गए?\" से नया पासवर्ड बनाएँ: बाकी सभी डिवाइस से साइन आउट हो जाएगा। Alakh सपोर्ट भी मदद कर सकती है।';

  @override
  String get faqDeleteQ => 'अपना खाता कैसे हटाएँ?';

  @override
  String get faqDeleteA =>
      'प्रोफ़ाइल में \"मेरा खाता हटाएँ\" दबाएँ। आपकी प्रोफ़ाइल, सेव किए गए पते और साइन-इन हटा दिए जाते हैं; पुरानी बुकिंग और भुगतान दुकानों के रिकॉर्ड के लिए आपके नाम के बिना रखे जाते हैं।';

  @override
  String get chatTitle => 'दुकान से चैट';

  @override
  String get chatOpen => 'चैट';

  @override
  String chatUnread(int count) {
    return 'चैट, $count नए संदेश';
  }

  @override
  String get chatLoading => 'संदेश लोड हो रहे हैं…';

  @override
  String get chatEmpty =>
      'अभी कोई संदेश नहीं। इस बुकिंग के बारे में दुकान से कुछ भी पूछें।';

  @override
  String get chatHint => 'संदेश लिखें';

  @override
  String get chatLoadEarlier => 'पुराने संदेश देखें';

  @override
  String get chatShop => 'दुकान';

  @override
  String get chatRead => 'पढ़ लिया गया';

  @override
  String get chatSent => 'भेजा गया';

  @override
  String get chatFlaggedHint =>
      'आपकी सुरक्षा के लिए संपर्क जानकारी छिपाई गई है';

  @override
  String get chatClosed => 'यह चैट बंद हो गई है। आप इसे अब भी पढ़ सकते हैं।';

  @override
  String chatClosedSince(String when) {
    return 'यह चैट $when बंद हो गई। आप इसे अब भी पढ़ सकते हैं।';
  }

  @override
  String chatOpenUntil(String when) {
    return 'आप $when तक संदेश भेज सकते हैं';
  }

  @override
  String get chatCallShop => 'दुकान को कॉल करें';

  @override
  String get chatCallPlaced => 'दुकान से जोड़ने के लिए हम आपको कॉल कर रहे हैं।';

  @override
  String get bookingDetailsTitle => 'बुकिंग की जानकारी';

  @override
  String get viewInvoice => 'इनवॉइस देखें';

  @override
  String get invoiceTitle => 'इनवॉइस';

  @override
  String get invoiceLoading => 'इनवॉइस लोड हो रहा है…';

  @override
  String get paymentPartlyRefunded => 'कुछ पैसे वापस हुए';

  @override
  String get cancelPolicy =>
      'बुकिंग से 2 घंटे पहले तक रद्द करना मुफ़्त है। उसके बाद रद्द करने का शुल्क लग सकता है।';

  @override
  String get cancelPolicyLate =>
      'आपकी बुकिंग में 2 घंटे से कम समय बचा है, इसलिए रद्द करने का शुल्क लग सकता है।';

  @override
  String get termsRequired => 'कृपया शर्तें और गोपनीयता नीति स्वीकार करें';

  @override
  String get termsAgree => 'मैं सहमत हूँ:';

  @override
  String get termsOfService => 'सेवा की शर्तें';

  @override
  String get termsAnd => 'और';

  @override
  String get privacyPolicy => 'गोपनीयता नीति';

  @override
  String get legalSection => 'कानूनी जानकारी';

  @override
  String get refundPolicy => 'रिफ़ंड नीति';

  @override
  String get grievanceOfficer => 'शिकायत निवारण';

  @override
  String get downloadMyData => 'मेरा डेटा डाउनलोड करें';

  @override
  String get dataExportNone => 'अपने खाते, बुकिंग और भुगतान की कॉपी पाएँ';

  @override
  String dataExportPending(String day) {
    return 'अनुरोध: $day। हम इसे तैयार कर रहे हैं।';
  }

  @override
  String get dataExportReady => 'तैयार है। डाउनलोड करने के लिए दबाएँ।';

  @override
  String get dataExportDeclined => 'आपका पिछला अनुरोध अस्वीकार हुआ।';

  @override
  String get dataExportQuestion => 'अपने डेटा की कॉपी चाहिए?';

  @override
  String get dataExportBody =>
      'हम आपके खाते, बुकिंग और भुगतान की एक फ़ाइल तैयार करेंगे। डाउनलोड के लिए तैयार होने पर यहाँ दिखेगा।';

  @override
  String get dataExportRequest => 'अनुरोध करें';

  @override
  String get dataExportRequested =>
      'अनुरोध भेज दिया। हम आपका डेटा तैयार करेंगे।';

  @override
  String get view => 'देखें';

  @override
  String get locationWhyTitle => 'आपकी लोकेशन इस्तेमाल करें?';

  @override
  String get locationWhyEta =>
      'आपका प्रोवाइडर कितनी दूर है और कब पहुँचेगा, यह दिखाने के लिए AlakhService को ऐप खुला रहने पर आपकी लोकेशन चाहिए। यह दुकान के साथ शेयर नहीं की जाती।';

  @override
  String get locationWhySharing =>
      'काम चलने के दौरान आपकी लोकेशन उस काम के ग्राहक के साथ शेयर होती है ताकि वे आपको आते देख सकें। काम खत्म होने पर शेयर करना बंद हो जाता है।';

  @override
  String get continueLabel => 'आगे बढ़ें';

  @override
  String get markAllRead => 'सभी पढ़े हुए करें';

  @override
  String get noNotifications => 'अभी कोई सूचना नहीं';

  @override
  String get noNotificationsBody =>
      'बुकिंग अपडेट, भुगतान की रसीदें और कतार की सूचनाएँ यहाँ दिखेंगी।';

  @override
  String get checkConnection =>
      'अपना इंटरनेट कनेक्शन जाँचें और फिर कोशिश करें।';

  @override
  String get timeNow => 'अभी';

  @override
  String hoursAgo(int count) {
    return '$count घंटे पहले';
  }

  @override
  String daysAgo(int count) {
    return '$count दिन पहले';
  }

  @override
  String get paymentTitle => 'भुगतान';

  @override
  String get paymentMethod => 'भुगतान का तरीका';

  @override
  String get payMethodUpi => 'UPI';

  @override
  String get payMethodUpiHint => 'GPay, PhonePe, Paytm या कोई भी UPI ऐप';

  @override
  String get payMethodCard => 'क्रेडिट / डेबिट कार्ड';

  @override
  String get payMethodNetbanking => 'नेट बैंकिंग';

  @override
  String get payMethodCash => 'नकद भुगतान करें';

  @override
  String get payMethodCashHint => 'काम पूरा होने पर अपने प्रोवाइडर को दें';

  @override
  String get paymentCancelled =>
      'भुगतान रद्द हुआ। आपसे कोई पैसा नहीं लिया गया।';

  @override
  String paymentPaidAmount(String amount) {
    return '$amount का भुगतान हो गया।';
  }

  @override
  String paymentCashBody(String amount) {
    return 'काम पूरा होने पर अपने प्रोवाइडर को $amount नकद दें।';
  }

  @override
  String paymentConfirmingBody(String amount) {
    return '$amount के भुगतान की पुष्टि हो रही है। जल्द ही यह भुगतान हो गया दिखेगा।';
  }

  @override
  String get paymentSuccessful => 'भुगतान सफल';

  @override
  String get paymentCashNoted => 'नकद भुगतान दर्ज हुआ';

  @override
  String get paymentRecorded => 'भुगतान दर्ज हुआ';

  @override
  String get paymentSecured =>
      'Razorpay द्वारा सुरक्षित। हम आपका कार्ड या UPI PIN कभी नहीं देखते।';

  @override
  String payInCashButton(String amount) {
    return 'मैं $amount नकद दूँगा/दूँगी';
  }

  @override
  String get amountToPay => 'देय राशि';

  @override
  String get bookingLabel => 'बुकिंग';

  @override
  String get queueLeaveQuestion => 'कतार छोड़ें?';

  @override
  String get queueLeaveBody =>
      'आपकी जगह चली जाएगी। फिर से जुड़ने पर आप कतार में सबसे पीछे होंगे।';

  @override
  String get queueStay => 'कतार में रहें';

  @override
  String get queueLeave => 'छोड़ें';

  @override
  String get queueLeft => 'आपने कतार छोड़ दी';

  @override
  String get queueNoLonger => 'अब आप इस कतार में नहीं हैं। आने के लिए धन्यवाद!';

  @override
  String get queueYourTurn => 'आपकी बारी है!';

  @override
  String get queueGoToCounter => 'कृपया अभी काउंटर पर जाएँ।';

  @override
  String queuePositionSemantics(int position) {
    return 'आपका नंबर: $position';
  }

  @override
  String get queueYourPosition => 'आपका नंबर';

  @override
  String get queueEstimatedWait => 'अनुमानित इंतज़ार';

  @override
  String queueExpectedAround(String time) {
    return 'लगभग $time पर';
  }

  @override
  String get queueWeWillNotify =>
      'आपकी बारी आने से पहले हम आपको सूचना देंगे, इसलिए यहाँ इंतज़ार करने की ज़रूरत नहीं।';

  @override
  String get queueLeaveButton => 'कतार छोड़ें';

  @override
  String get queueWaitUnknown => 'अभी उपलब्ध नहीं';

  @override
  String get queueYoureNext => 'अगली बारी आपकी';

  @override
  String queueWaitMinutes(int minutes) {
    return '$minutes मिनट';
  }

  @override
  String queueAhead(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'आपसे आगे $count लोग',
      one: 'आपसे आगे 1 व्यक्ति',
      zero: 'आपसे आगे कोई नहीं',
    );
    return '$_temp0';
  }

  @override
  String get travelDrive => 'गाड़ी से जाएँ';

  @override
  String get travelDriveHint => 'अपनी कार या बाइक: रास्ते की पूरी जानकारी';

  @override
  String get travelTransit => 'सार्वजनिक परिवहन';

  @override
  String get travelTransitHint => 'बस, मेट्रो और ट्रेन के रूट और समय';

  @override
  String get travelWalk => 'पैदल';

  @override
  String get travelWalkHint => 'पैदल रास्ता';

  @override
  String get travelUber => 'Uber बुक करें';

  @override
  String get travelUberHint => 'दुकान को ड्रॉप-ऑफ़ बनाकर Uber खोलता है';

  @override
  String get travelRideApp => 'Ola, Rapido या कोई और राइड ऐप';

  @override
  String get travelRideAppHint => 'ड्रॉप-ऑफ़ के लिए पता कॉपी करें';

  @override
  String get travelAddressCopied =>
      'पता कॉपी हो गया। इसे Ola, Rapido या किसी भी राइड ऐप में ड्रॉप-ऑफ़ के रूप में पेस्ट करें।';

  @override
  String travelCouldNotOpen(String option) {
    return '$option नहीं खुल सका';
  }

  @override
  String get travelNoAddress =>
      'इस दुकान ने अभी अपना पता नहीं जोड़ा है। रास्ते के लिए उनसे संपर्क करें।';

  @override
  String get rescheduleBooking => 'समय बदलें';

  @override
  String get rescheduleTitle => 'बुकिंग का समय बदलें';

  @override
  String rescheduleCurrent(String when) {
    return 'अभी $when के लिए बुक है';
  }

  @override
  String rescheduleRule(int count) {
    return 'बुकिंग शुरू होने से 2 घंटे पहले तक आप समय बदल सकते हैं। बचे हुए बदलाव: $count।';
  }

  @override
  String get rescheduleConfirm => 'नया समय पक्का करें';

  @override
  String get rescheduling => 'समय बदला जा रहा है…';

  @override
  String bookingRescheduled(String when) {
    return 'बुकिंग $when पर कर दी गई';
  }

  @override
  String get bookAgain => 'फिर से बुक करें';

  @override
  String get saveShop => 'दुकान सेव करें';

  @override
  String get unsaveShop => 'सेव की गई दुकानों से हटाएँ';

  @override
  String get shopSaved => 'दुकान सेव हो गई';

  @override
  String get shopUnsaved => 'सेव की गई दुकानों से हटाई गई';

  @override
  String get savedShops => 'सेव की गई दुकानें';

  @override
  String get noSavedShops =>
      'अभी कोई दुकान सेव नहीं है। किसी सेवा पर दिल वाले बटन को दबाकर उसकी दुकान सेव करें।';

  @override
  String get shopNoServices =>
      'इस दुकान में अभी बुक करने के लिए कोई सेवा नहीं है।';

  @override
  String get tipAdd => 'टिप दें';

  @override
  String get tipTitle => 'अपने प्रोफ़ेशनल को टिप दें';

  @override
  String get tipBody =>
      'आपकी पूरी टिप उस प्रोफ़ेशनल को जाती है जिसने आपकी सेवा की। भुगतान ऑनलाइन होता है।';

  @override
  String get tipOther => 'दूसरी रकम (₹)';

  @override
  String get tipRange => '₹10 से ₹2,000 तक डालें';

  @override
  String tipPay(String amount) {
    return '$amount टिप दें';
  }

  @override
  String tipThanks(String amount) {
    return 'आपने $amount की टिप दी। धन्यवाद!';
  }

  @override
  String get rewardsTitle => 'रिवॉर्ड';

  @override
  String pointsBalance(int count) {
    return '$count पॉइंट';
  }

  @override
  String pointsWorth(String amount) {
    return 'अगली बुकिंग पर $amount की छूट';
  }

  @override
  String pointsRules(String earn, String percent) {
    return 'हर ₹100 के भुगतान पर $earn पॉइंट पाएँ। पॉइंट से बुकिंग का $percent% तक भुगतान हो सकता है।';
  }

  @override
  String get referralTitle => 'दोस्तों को बुलाएँ';

  @override
  String referralBody(String bonus) {
    return 'अपना कोड शेयर करें। दोस्त की पहली बुकिंग पूरी होने पर आप दोनों को $bonus पॉइंट मिलेंगे।';
  }

  @override
  String get referralCopy => 'कोड कॉपी करें';

  @override
  String get referralCopied => 'कोड कॉपी हो गया';

  @override
  String get referralShare => 'WhatsApp पर शेयर करें';

  @override
  String referralShareText(String code, String bonus) {
    return 'मेरे कोड $code से AlakhService पर सैलून और सेवाएँ बुक करें: आपकी पहली बुकिंग के बाद हम दोनों को $bonus पॉइंट मिलेंगे।';
  }

  @override
  String referralFriends(int rewarded, int pending) {
    return '$rewarded दोस्तों ने बुक किया · $pending ने अभी नहीं';
  }

  @override
  String get referralEnterTitle => 'क्या किसी दोस्त का कोड है?';

  @override
  String get referralCodeLabel => 'रेफ़रल कोड';

  @override
  String get pointsHistory => 'पॉइंट का इतिहास';

  @override
  String get pointsEarned => 'बुकिंग पर मिले';

  @override
  String get pointsSpent => 'बुकिंग में इस्तेमाल';

  @override
  String get pointsReturned => 'वापस मिले (बुकिंग रद्द)';

  @override
  String get pointsReferral => 'रेफ़रल बोनस';

  @override
  String get pointsTakenBack => 'वापस लिए गए (रिफ़ंड)';

  @override
  String get usePoints => 'मेरे पॉइंट इस्तेमाल करें';

  @override
  String usePointsSaving(String amount, int points) {
    return '$amount बचाएँ · $points पॉइंट उपलब्ध';
  }

  @override
  String get pointsLine => 'पॉइंट';

  @override
  String pointsUsed(String amount) {
    return 'इस्तेमाल हुए पॉइंट: $amount';
  }

  @override
  String get packagesTitle => 'पैकेज';

  @override
  String packageTerms(int visits, int days) {
    return '$visits विज़िट · $days दिन तक मान्य';
  }

  @override
  String packageSaving(String amount) {
    return '$amount की बचत';
  }

  @override
  String packageBuy(String amount) {
    return '$amount में खरीदें';
  }

  @override
  String packageBought(String name) {
    return '$name तैयार है। बुक करते समय इसे चुनें।';
  }

  @override
  String get myPackages => 'मेरे पैकेज';

  @override
  String get noPackages =>
      'अभी कोई पैकेज नहीं है। जिन सेवाओं में पैकेज है, वे उनके पेज पर दिखते हैं।';

  @override
  String packageVisitsLeft(int left, int total) {
    return '$total में से $left विज़िट बाकी';
  }

  @override
  String packageValidUntil(String date) {
    return '$date तक मान्य';
  }

  @override
  String get packageRefunded => 'रिफ़ंड हो गया';

  @override
  String get packageUsedUp => 'इस्तेमाल हो चुका या समय खत्म';

  @override
  String get usePackage => 'मेरा पैकेज इस्तेमाल करें';

  @override
  String usePackageLeft(String name, int left) {
    return '$name · $left विज़िट बाकी';
  }

  @override
  String get packageLine => 'पैकेज विज़िट';

  @override
  String get waitlistJoin => 'कोई समय खाली हो तो बताएँ';

  @override
  String get waitlistJoined => 'इस दिन कोई समय खाली होने पर हम आपको बताएँगे।';

  @override
  String get whoQuestion => 'आप किससे करवाना चाहेंगे?';

  @override
  String get anyProfessional => 'कोई भी';

  @override
  String get professionalNote =>
      'दुकान आपकी चुनी हुई व्यक्ति देने की पूरी कोशिश करती है।';

  @override
  String askedFor(String name) {
    return 'आपने $name को चुना';
  }

  @override
  String get liveQueueTitle => 'दुकान पर लाइव कतार';

  @override
  String liveQueueWait(String time) {
    return 'लगभग $time इंतज़ार';
  }

  @override
  String liveQueueBeingServed(int count) {
    return 'अभी सेवा में: $count';
  }

  @override
  String liveQueueRunningLate(int minutes) {
    return 'दुकान लगभग $minutes मिनट देरी से चल रही है';
  }

  @override
  String get liveQueueGoIn => 'कृपया अभी दुकान के काउंटर पर जाएँ।';

  @override
  String get liveQueueInProgress => 'आपकी सेवा चल रही है';

  @override
  String liveQueueShort(int position, String wait) {
    return 'कतार में #$position · $wait';
  }

  @override
  String liveQueueBetween(String from, String to) {
    return '$from से $to के बीच अपेक्षित';
  }

  @override
  String liveQueueWith(String name) {
    return '$name के साथ';
  }

  @override
  String get liveQueueCheckIn => 'मैं आ गया/गई हूँ';

  @override
  String get liveQueueCheckedIn => 'आपका चेक-इन हो गया है';

  @override
  String get liveQueueCheckInNeeded =>
      'आपका समय निकल गया है। पहुँचने पर चेक-इन करें, आप फिर से कतार में आ जाएँगे।';

  @override
  String get liveQueueUnservable =>
      'दुकान आज इसे नहीं कर पाएगी। कृपया दुकान से संपर्क करें या किसी और दिन बुक करें।';

  @override
  String get liveQueueStaffAway =>
      'आपके चुने हुए प्रोफ़ेशनल आज उपलब्ध नहीं हैं, इसलिए कोई और आपकी सेवा करेगा।';

  @override
  String get joinLineNow => 'अभी आज की कतार में जुड़ें';

  @override
  String get joinLineNote =>
      'बुकिंग समय की ज़रूरत नहीं: आपको तुरंत जगह और इंतज़ार का समय मिलेगा।';

  @override
  String get joinLineDone => 'आप कतार में हैं';

  @override
  String joinLineDoneBody(int position, String time) {
    return 'कतार में #$position, लगभग $time बजे अपेक्षित।';
  }

  @override
  String get joinLineSeeBookings => 'मेरी बुकिंग देखें';

  @override
  String get navShopLine => 'मेरी दुकान';

  @override
  String get shopLineTitle => 'आज की कतार';

  @override
  String get shopLineEmpty => 'अभी कतार में कोई नहीं है।';

  @override
  String shopLineWaiting(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count इंतज़ार में',
      one: '1 इंतज़ार में',
      zero: 'कोई इंतज़ार में नहीं',
    );
    return '$_temp0';
  }

  @override
  String get shopLineTeam => 'आज की टीम';

  @override
  String get shopLineFree => 'खाली';

  @override
  String shopLineServing(String name) {
    return '$name की सेवा';
  }

  @override
  String shopLineOnBreak(String time) {
    return '$time तक ब्रेक पर';
  }

  @override
  String get shopLineOffToday => 'आज छुट्टी';

  @override
  String get shopLineNext => 'अगला ग्राहक';

  @override
  String get shopLineDone => 'हो गया';

  @override
  String get shopLineBreak => '15 मिनट ब्रेक';

  @override
  String get shopLineOff => 'आज छुट्टी';

  @override
  String get shopLineBack => 'वापस';

  @override
  String get shopLineStart => 'शुरू करें';

  @override
  String get shopLineNoShow => 'नहीं आए';

  @override
  String get shopLineCheckIn => 'चेक-इन';

  @override
  String get shopLineNow => 'अभी';

  @override
  String get shopLineWalkIn => 'बिना बुकिंग';

  @override
  String get shopLineAddWalkIn => 'बिना बुकिंग ग्राहक जोड़ें';

  @override
  String get shopLineWalkInName => 'बुलाने के लिए नाम';

  @override
  String get shopLineService => 'सेवा';

  @override
  String get shopLineAdd => 'जोड़ें';

  @override
  String shopLineAdded(String name, int position) {
    return '$name कतार में #$position पर हैं';
  }

  @override
  String shopLineLate(int minutes) {
    return '$minutes मिनट देर';
  }

  @override
  String get homeArrivalTitle => 'आपकी होम विज़िट';

  @override
  String homeArrivalAround(String time) {
    return 'आपके प्रोफ़ेशनल लगभग $time बजे पहुँचेंगे';
  }

  @override
  String homeArrivalBetween(String from, String to) {
    return '$from से $to के बीच';
  }

  @override
  String homeArrivalOnTheWay(String time) {
    return 'रास्ते में हैं, लगभग $time बजे पहुँचेंगे';
  }

  @override
  String get homeArrivalHere => 'आपके प्रोफ़ेशनल आपके पास हैं';

  @override
  String homeArrivalBefore(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'आपसे पहले $count विज़िट',
      one: 'आपसे पहले 1 विज़िट',
      zero: 'आप उनकी पहली विज़िट हैं',
    );
    return '$_temp0';
  }

  @override
  String homeArrivalLate(int minutes) {
    return 'आपके बुक किए समय से लगभग $minutes मिनट देर';
  }

  @override
  String get registerWhy => 'आप क्यों जुड़ रहे हैं?';

  @override
  String get registerAsCustomer => 'मुझे सेवाएँ बुक करनी हैं';

  @override
  String get registerAsCustomerHelp =>
      'सैलून, इलेक्ट्रीशियन, डॉक्टर और बहुत कुछ खोजें';

  @override
  String get registerAsProvider => 'मुझे अपनी सेवाएँ देनी हैं';

  @override
  String get registerAsProviderHelp =>
      'अपनी दुकान या अपने काम के लिए बुकिंग पाएँ';

  @override
  String get locationWhyBusiness =>
      'आपकी लोकेशन से आपका काम मैप पर दिखता है, ताकि पास के ग्राहक आपको ढूँढ सकें। यह एक बार सेव होती है, ट्रैक नहीं होती।';

  @override
  String get ownerOfferServices => 'अपनी सेवाएँ दें';

  @override
  String get ownerSetupTitle => 'अपना काम जोड़ें';

  @override
  String ownerStepOf(int step, int total) {
    return 'चरण $step, कुल $total';
  }

  @override
  String get ownerStepBusiness => 'आपके काम के बारे में';

  @override
  String get ownerStepServices => 'आप क्या सेवा देते हैं?';

  @override
  String get ownerStepHours => 'आप कब काम करते हैं?';

  @override
  String get ownerBusinessName => 'आपका नाम या दुकान का नाम';

  @override
  String get ownerBusinessNameHelp =>
      'ग्राहक यही देखेंगे। अकेले काम करते हैं तो अपना नाम लिखें।';

  @override
  String get ownerCategory => 'काम का प्रकार';

  @override
  String get ownerWhereDoYouWork => 'आप काम कहाँ करते हैं?';

  @override
  String get ownerAtMyShop => 'मेरी दुकान पर';

  @override
  String get ownerAtCustomersHome => 'ग्राहक के घर पर';

  @override
  String get ownerChooseWhere => 'काम की कम से कम एक जगह चुनें।';

  @override
  String get ownerCity => 'शहर';

  @override
  String get ownerShopAddress => 'दुकान का पता';

  @override
  String get ownerAreaYouServe => 'आपका कार्य क्षेत्र (वैकल्पिक)';

  @override
  String get ownerPhone =>
      'दुकान का फ़ोन (केवल Alakh सहायता के लिए; ग्राहकों को नहीं दिखता)';

  @override
  String get ownerUseLocation => 'मेरी मौजूदा लोकेशन लें';

  @override
  String get ownerLocationSaved => 'लोकेशन जुड़ गई';

  @override
  String get ownerLocationFailed =>
      'लोकेशन नहीं मिली। आप इसके बिना आगे बढ़ सकते हैं।';

  @override
  String get ownerRequired => 'कृपया इसे भरें';

  @override
  String get ownerEnterNumber => 'संख्या लिखें';

  @override
  String get ownerServicesHelp =>
      'जो ग्राहक बुक कर सकें, वह जोड़ें। बाद में और जोड़ सकते हैं।';

  @override
  String get ownerServiceName => 'सेवा का नाम';

  @override
  String get ownerServiceNameHint => 'जैसे हेयरकट, पंखा मरम्मत';

  @override
  String get ownerPrice => 'कीमत';

  @override
  String get ownerMinutes => 'कितने मिनट लगते हैं';

  @override
  String get ownerAddAnotherService => 'एक और सेवा जोड़ें';

  @override
  String get ownerOpenDays => 'काम के दिन';

  @override
  String get ownerOpensAt => 'से';

  @override
  String get ownerClosesAt => 'तक';

  @override
  String get ownerHoursInvalid =>
      'कम से कम एक दिन चुनें, और समाप्ति का समय शुरू के बाद का रखें।';

  @override
  String get ownerFinishSetup => 'सेव करके आगे बढ़ें';

  @override
  String get ownerVerificationTitle => 'सत्यापन और भुगतान';

  @override
  String get ownerStatusApproved =>
      'आपका काम सत्यापित है और ग्राहक बुक कर सकते हैं।';

  @override
  String ownerStatusRejected(String reason) {
    return 'आपके विवरण में बदलाव चाहिए: $reason';
  }

  @override
  String get ownerStatusInReview =>
      'हम आपके विवरण जाँच रहे हैं। इसके बाद ग्राहक बुक कर सकेंगे।';

  @override
  String get ownerStatusNotSubmitted =>
      'इन विवरणों की जाँच के बाद ग्राहक आपको ढूँढ और बुक कर सकेंगे।';

  @override
  String get ownerBannerFinish => 'सत्यापन पूरा करें, ताकि ग्राहक बुक कर सकें';

  @override
  String get ownerAboutYou => 'आपके बारे में';

  @override
  String get ownerLegalName => 'PAN पर लिखा नाम';

  @override
  String get ownerLegalNameHelp =>
      'आपका नाम, या PAN कंपनी का हो तो कंपनी का नाम।';

  @override
  String get ownerLegalAddress => 'आपका पता (वैकल्पिक)';

  @override
  String get ownerGstin => 'GSTIN (वैकल्पिक)';

  @override
  String get ownerGstinHelp => 'सिर्फ़ तब, जब आपका व्यवसाय GST में पंजीकृत हो।';

  @override
  String get ownerDocuments => 'दस्तावेज़';

  @override
  String get ownerDocPan => 'PAN कार्ड';

  @override
  String get ownerDocGst => 'GST प्रमाणपत्र';

  @override
  String get ownerDocAadhaar => 'आधार कार्ड';

  @override
  String get ownerDocShopPhoto => 'दुकान या काम की फ़ोटो';

  @override
  String get ownerUploaded => 'जुड़ गया';

  @override
  String get ownerNeeded => 'ज़रूरी';

  @override
  String get ownerOptional => 'वैकल्पिक';

  @override
  String get ownerReplace => 'बदलें';

  @override
  String get ownerAddPhoto => 'जोड़ें';

  @override
  String get ownerTakePhoto => 'फ़ोटो खींचें';

  @override
  String get ownerChoosePhoto => 'गैलरी से चुनें';

  @override
  String get ownerPhotoFailed => 'वह फ़ोटो नहीं खुली। कृपया फिर कोशिश करें।';

  @override
  String get ownerPanNeeded => 'कृपया अपने PAN कार्ड की फ़ोटो जोड़ें।';

  @override
  String get ownerGstNeeded =>
      'आपने GSTIN दिया है, इसलिए GST प्रमाणपत्र की फ़ोटो जोड़ें।';

  @override
  String get ownerPayouts => 'आपका पैसा कहाँ भेजें?';

  @override
  String get ownerPayoutsHelp =>
      'ऑनलाइन भुगतान वाली बुकिंग के लिए। इसे बाद में भी जोड़ सकते हैं।';

  @override
  String get ownerUpi => 'UPI';

  @override
  String get ownerBankAccount => 'बैंक खाता';

  @override
  String get ownerUpiId => 'UPI आईडी';

  @override
  String get ownerAccountName => 'खाताधारक का नाम';

  @override
  String get ownerAccountNumber => 'खाता संख्या';

  @override
  String get ownerIfsc => 'IFSC कोड';

  @override
  String ownerPayoutSaved(String account) {
    return 'सेव है: $account। बदलने के लिए नीचे भरें।';
  }

  @override
  String get ownerSubmit => 'सत्यापन के लिए भेजें';

  @override
  String get ownerSubmitAgain => 'फिर से भेजें';

  @override
  String get ownerSubmitted =>
      'हम आपके विवरण जाँचकर नतीजा बताएँगे। सत्यापन के बाद ग्राहक आपको बुक कर सकेंगे।';

  @override
  String get ownerDetailsSaved => 'विवरण सेव हो गए';

  @override
  String get ownerDoItLater => 'बाद में करें';

  @override
  String ownerNewRequests(int count) {
    return 'नए अनुरोध ($count)';
  }

  @override
  String get ownerNoRequests =>
      'अभी कोई नया अनुरोध नहीं। वे यहाँ अपने आप दिखेंगे।';

  @override
  String get ownerComingUp => 'आगे का काम';

  @override
  String get ownerNothingAhead => 'अभी कुछ बुक नहीं है।';

  @override
  String get ownerManage => 'प्रबंधन';

  @override
  String get ownerLiveLine => 'आज की लाइव लाइन';

  @override
  String get ownerMyServices => 'मेरी सेवाएँ';

  @override
  String get ownerOpeningHours => 'काम के घंटे';

  @override
  String get ownerAccept => 'स्वीकार करें';

  @override
  String get ownerDecline => 'मना करें';

  @override
  String get ownerDeclineTitle => 'यह बुकिंग मना करें?';

  @override
  String get ownerCancelTitle => 'यह बुकिंग रद्द करें?';

  @override
  String get ownerCancelBooking => 'बुकिंग रद्द करें';

  @override
  String get ownerRefundNote =>
      'ग्राहक को बताया जाएगा और ऑनलाइन दिया पैसा वापस मिलेगा।';

  @override
  String get ownerReasonLabel => 'कारण (ग्राहक इसे देखेंगे)';

  @override
  String get ownerDefaultReason => 'इस समय उपलब्ध नहीं';

  @override
  String get ownerCustomerArrived => 'ग्राहक आ गया';

  @override
  String get ownerGoMyself => 'यह काम मुझे करना है';

  @override
  String get ownerOnTheWay => 'रास्ते में हूँ';

  @override
  String get ownerOnTheWayToCollect => 'सामान लेने निकल गए';

  @override
  String get ownerPickedUp => 'सामान ले लिया';

  @override
  String get ownerStartWork => 'काम शुरू करें';

  @override
  String get ownerStartService => 'सेवा शुरू करें';

  @override
  String get ownerSendBack => 'वापस भेजें';

  @override
  String get ownerDelivered => 'पहुँचा दिया';

  @override
  String get ownerComplete => 'पूरा हुआ';

  @override
  String get ownerMessage => 'संदेश';

  @override
  String get ownerAService => 'सेवा';

  @override
  String get ownerHomeVisit => 'घर पर सेवा';

  @override
  String get ownerPickupDrop => 'पिकअप और ड्रॉप';

  @override
  String get ownerAddService => 'सेवा जोड़ें';

  @override
  String get ownerNoServices =>
      'अभी कुछ नहीं। जो ग्राहक बुक कर सकें, वह जोड़ें।';

  @override
  String ownerMinutesShort(int minutes) {
    return '$minutes मिनट';
  }

  @override
  String get ownerHoursSimplified =>
      'आपके सेव घंटों में ब्रेक हैं या दिन के अनुसार अलग हैं। यहाँ सेव करने पर एक ही समय लागू होगा।';

  @override
  String get categorySalon => 'सैलून';

  @override
  String get categoryBeauty => 'ब्यूटी पार्लर';

  @override
  String get categorySpa => 'स्पा';

  @override
  String get categoryClinic => 'डॉक्टर / क्लिनिक';

  @override
  String get categoryVehicleRepair => 'कार और बाइक मरम्मत';

  @override
  String get categoryElectronicsRepair => 'लैपटॉप और फ़ोन मरम्मत';

  @override
  String get categoryApplianceRepair => 'AC और उपकरण मरम्मत';

  @override
  String get categoryCleaning => 'सफ़ाई';

  @override
  String get categoryPlumbing => 'प्लंबिंग';

  @override
  String get categoryElectrical => 'बिजली का काम';

  @override
  String get categoryRepair => 'अन्य मरम्मत';

  @override
  String get categoryOffice => 'ऑफ़िस / अपॉइंटमेंट';

  @override
  String get categoryOther => 'अन्य';

  @override
  String get loginJoinAsProvider => 'दुकान है या सेवा देते हैं? यहाँ जुड़ें';

  @override
  String get modeSwitchToBusiness => 'मेरे काम पर जाएँ';

  @override
  String get modeSwitchToBooking => 'सेवाएँ बुक करने पर जाएँ';

  @override
  String get statusPendingHelp =>
      'दुकान को आपका अनुरोध मिल गया है और उसे स्वीकार करना है। हम आपको बताएँगे। समय पर जवाब न मिलने पर अनुरोध रद्द हो जाएगा।';

  @override
  String get statusCancelledHelp =>
      'जो भी रिफ़ंड बनता है, वह 5–7 कार्यदिवसों में आपके खाते में आ जाएगा।';

  @override
  String cancelledBecause(String reason) {
    return 'कारण: $reason';
  }

  @override
  String get ownerNeedsYourAnswer => 'आपके जवाब का इंतज़ार';

  @override
  String get ownerPaid => 'भुगतान हो गया';

  @override
  String get ownerNotPaid => 'अभी भुगतान नहीं';

  @override
  String get ownerRefunded => 'पैसा वापस';

  @override
  String get ownerPartlyRefunded => 'कुछ पैसा वापस';

  @override
  String get ownerBeforeSending => 'भेजने से पहले ज़रूरी है:';

  @override
  String get ownerSubmittedTitle => 'सत्यापन के लिए भेज दिया';

  @override
  String get allServices => 'सभी सेवाएँ';

  @override
  String get ownerTapToAdd => 'जोड़ने के लिए छुएँ, या खुद लिखें:';

  @override
  String servicesShowingType(String type) {
    return 'दिखा रहे हैं: $type';
  }

  @override
  String get groupBeauty => 'सौंदर्य और ग्रूमिंग';

  @override
  String get groupHealth => 'स्वास्थ्य और देखभाल';

  @override
  String get groupHomeRepairs => 'घर की मरम्मत';

  @override
  String get groupHomeHelp => 'घर के काम में मदद';

  @override
  String get groupVehicles => 'गाड़ियाँ';

  @override
  String get groupLearning => 'पढ़ाई और फ़िटनेस';

  @override
  String get groupEvents => 'कार्यक्रम और समारोह';

  @override
  String get groupOther => 'अन्य सेवाएँ';

  @override
  String get typeMehndi => 'मेहंदी कलाकार';

  @override
  String get typeTailoring => 'दर्ज़ी';

  @override
  String get typeDentist => 'दाँतों के डॉक्टर';

  @override
  String get typePhysiotherapy => 'फ़िज़ियोथेरेपी';

  @override
  String get typeHomeNursing => 'घर पर नर्स';

  @override
  String get typeLabTests => 'लैब जाँच';

  @override
  String get typePetCare => 'पालतू जानवरों की देखभाल';

  @override
  String get typeCarpentry => 'बढ़ई';

  @override
  String get typeWaterPurifier => 'RO और वॉटर प्यूरीफ़ायर';

  @override
  String get typePainting => 'पेंटर';

  @override
  String get typePestControl => 'कीट नियंत्रण';

  @override
  String get typeDomesticHelp => 'घरेलू सहायक';

  @override
  String get typeCook => 'रसोइया';

  @override
  String get typeCareGiver => 'बुज़ुर्ग और बच्चों की देखभाल';

  @override
  String get typeLaundry => 'कपड़े धोना और इस्त्री';

  @override
  String get typeGardening => 'माली';

  @override
  String get typePackersMovers => 'पैकर्स और मूवर्स';

  @override
  String get typeCarWash => 'कार और बाइक धुलाई';

  @override
  String get typeDriver => 'ड्राइवर';

  @override
  String get typeTutor => 'ट्यूटर';

  @override
  String get typeFitness => 'योग और फ़िटनेस';

  @override
  String get typeMusicDance => 'संगीत और नृत्य कक्षाएँ';

  @override
  String get typePhotography => 'फ़ोटोग्राफ़र';

  @override
  String get typeCatering => 'कैटरर';

  @override
  String get typeEventDecor => 'डेकोरेटर';

  @override
  String get typePriest => 'पंडित और पूजा';

  @override
  String get typeTaxLegal => 'टैक्स और कानूनी मदद';

  @override
  String get typeConstruction => 'निर्माण और राजमिस्त्री';

  @override
  String get typeWelding => 'वेल्डिंग और फ़ैब्रिकेशन';

  @override
  String get typeInterior => 'इंटीरियर और फ़ॉल्स सीलिंग';

  @override
  String get typeSolar => 'सोलर और इन्वर्टर';

  @override
  String get typeSecurityGuard => 'सिक्योरिटी गार्ड';

  @override
  String get ownerChooseType => 'अपना काम चुनें';

  @override
  String get ownerSearchType =>
      'खोजें: इलेक्ट्रीशियन, डॉक्टर, एसी, राजमिस्त्री...';

  @override
  String get ownerPickServices =>
      'आप जो भी काम करते हैं, उन सब पर टैप करें। बाद में बदल सकते हैं।';

  @override
  String get ownerSelectAll => 'सभी चुनें';

  @override
  String get ownerClearAll => 'सभी हटाएँ';

  @override
  String get ownerSamePrice => 'सबके लिए सामान्य दाम (₹)';

  @override
  String get ownerSamePriceHelp =>
      'यह हर सेवा में भर जाएगा। नीचे किसी को भी बदल सकते हैं।';

  @override
  String get ownerPickOneService => 'कम से कम एक सेवा चुनें।';

  @override
  String get ownerChoosePdf => 'PDF फ़ाइल चुनें';

  @override
  String get ownerAddFile => 'जोड़ें';

  @override
  String get ownerDocumentsHelp =>
      'साफ़ फ़ोटो या PDF। फ़ाइल 5 MB तक हो सकती है।';

  @override
  String ownerDocNeeded(String document) {
    return 'कृपया जोड़ें: $document';
  }

  @override
  String get ownerReports => 'रिपोर्ट और मुनाफ़ा';

  @override
  String get reportDaily => 'रोज़ाना';

  @override
  String get reportWeekly => 'साप्ताहिक';

  @override
  String get reportMonthly => 'मासिक';

  @override
  String get reportYearly => 'वार्षिक';

  @override
  String get reportYearlyHelp => 'अप्रैल से मार्च, भारत का वित्त वर्ष';

  @override
  String get reportProfit => 'मुनाफ़ा';

  @override
  String get reportLoss => 'घाटा';

  @override
  String reportUp(String percent) {
    return 'पिछली अवधि से $percent% ज़्यादा';
  }

  @override
  String reportDown(String percent) {
    return 'पिछली अवधि से $percent% कम';
  }

  @override
  String reportBookingsDone(int count) {
    return '$count बुकिंग पूरी हुईं';
  }

  @override
  String get reportCustomersPaid => 'ग्राहकों ने दिया';

  @override
  String get reportCash => 'नकद मिला';

  @override
  String get reportOnline => 'ऑनलाइन मिला';

  @override
  String get reportCommission => 'कमीशन और GST';

  @override
  String get reportEarned => 'बुकिंग से आपकी कमाई';

  @override
  String get reportOtherIncome => 'अन्य आय';

  @override
  String get reportExpenses => 'खर्च';

  @override
  String get reportTips => 'टिप (मुनाफ़े में नहीं)';

  @override
  String get reportAddExpense => 'खर्च जोड़ें';

  @override
  String get reportAddIncome => 'आय जोड़ें';

  @override
  String get reportRecordedOnly =>
      'मुनाफ़े में सिर्फ़ यहाँ दर्ज रकम गिनी जाती है। सही आँकड़े के लिए अपने खर्च और बाहर की आय जोड़ें।';

  @override
  String get reportBreakdown => 'तारीख़ के अनुसार मुनाफ़ा';

  @override
  String get reportEntries => 'आपने जो जोड़ा';

  @override
  String get reportRemoveEntry => 'हटाएँ';

  @override
  String get reportSendNow => 'यह रिपोर्ट अभी भेजें';

  @override
  String reportSentTo(String channels) {
    return 'भेजी गई: $channels';
  }

  @override
  String get reportSentAppOnly =>
      'यह आपकी सूचनाओं में है। ईमेल और WhatsApp सेट नहीं हैं या बंद हैं।';

  @override
  String get reportAmount => 'रकम';

  @override
  String get reportNote => 'नोट (ज़रूरी नहीं)';

  @override
  String get reportSettingsTitle => 'रिपोर्ट सेटिंग';

  @override
  String get reportWhich => 'कौन सी रिपोर्ट';

  @override
  String get reportWhere => 'कहाँ भेजें';

  @override
  String get reportEmail => 'ईमेल';

  @override
  String get reportWhatsApp => 'WhatsApp';

  @override
  String get reportWhatsAppConsent =>
      'इसे चालू करके आप अपने नंबर पर WhatsApp से रिपोर्ट पाने के लिए सहमत होते हैं। इसे कभी भी बंद कर सकते हैं।';

  @override
  String get entryMaterials => 'सामान';

  @override
  String get entrySpareParts => 'स्पेयर पार्ट्स';

  @override
  String get entryTravel => 'आना-जाना और ईंधन';

  @override
  String get entryRent => 'किराया';

  @override
  String get entryStaff => 'स्टाफ़ का वेतन';

  @override
  String get entryTools => 'औज़ार';

  @override
  String get entryBills => 'बिल';

  @override
  String get entryMarketing => 'विज्ञापन';

  @override
  String get entryOutsideWork => 'ऐप के बाहर का काम';

  @override
  String get entryOther => 'अन्य';

  @override
  String get ownerDaysOff => 'छुट्टी के दिन';

  @override
  String get ownerDaysOffHelp =>
      'इन दिनों ग्राहक बुक नहीं कर सकते। जो बुकिंग पहले से हैं वे बनी रहेंगी, उन्हें आप खुद रद्द करें या बदलें।';

  @override
  String get ownerOffToday => 'आज छुट्टी';

  @override
  String get ownerOffTomorrow => 'कल छुट्टी';

  @override
  String get ownerOffPick => 'तारीख़ चुनें';

  @override
  String get ownerNoDaysOff => 'आगे कोई छुट्टी नहीं है।';

  @override
  String get ownerReviews => 'ग्राहकों की समीक्षाएँ';

  @override
  String get ownerNoReviews =>
      'अभी कोई समीक्षा नहीं। काम पूरा होने पर ग्राहक की रेटिंग यहाँ दिखेगी।';

  @override
  String get ownerReply => 'जवाब दें';

  @override
  String get ownerEditReply => 'जवाब बदलें';

  @override
  String get ownerReplyHelp => 'आपका जवाब सभी पढ़ सकते हैं।';

  @override
  String get ownerCustomers => 'मेरे ग्राहक';

  @override
  String get ownerNoCustomers =>
      'पहली बुकिंग पूरी होने पर ग्राहक यहाँ दिखेंगे।';

  @override
  String ownerCustomersSummary(int total, int back) {
    return '$total ग्राहक, $back दोबारा आए';
  }

  @override
  String ownerCustomerLine(int visits, String date) {
    return '$visits बार आए, पिछली बार $date';
  }

  @override
  String get ownerShare => 'अपना व्यवसाय शेयर करें';

  @override
  String get ownerShareHelp =>
      'इसे अपने ग्राहकों और ग्रुप में भेजें। वे लिंक से सीधे आपको बुक कर सकते हैं।';

  @override
  String ownerShareMessage(String name, String link) {
    return 'AlakhService पर $name को बुक करें: $link';
  }

  @override
  String get ownerShareWhatsApp => 'WhatsApp पर शेयर करें';

  @override
  String get ownerShareCopy => 'संदेश कॉपी करें';

  @override
  String get ownerShareCopied => 'कॉपी हो गया। इसे कहीं भी पेस्ट कर सकते हैं।';

  @override
  String get ownerShareFailed =>
      'WhatsApp नहीं खुला। इसकी जगह संदेश कॉपी करें।';

  @override
  String get ownerShareNotYet =>
      'व्यवसाय मंज़ूर होने पर आप अपना लिंक शेयर कर सकते हैं।';

  @override
  String get extraTitle => 'अतिरिक्त शुल्क की मंज़ूरी';

  @override
  String extraLine(String amount, String reason) {
    return '$amount और: $reason';
  }

  @override
  String extraNewTotal(String total) {
    return 'मंज़ूर करने पर नया कुल: $total';
  }

  @override
  String get extraHelp =>
      'दाम तभी बदलेगा जब आप मंज़ूर करेंगे। मना करने पर दाम वही रहेगा।';

  @override
  String get extraApprove => 'मंज़ूर करें';

  @override
  String get extraDecline => 'मना करें';

  @override
  String extraConfirmTitle(String amount) {
    return '$amount और देने हैं?';
  }

  @override
  String get extraConfirmBody => 'यह आपकी बुकिंग के दाम में जुड़ जाएगा।';

  @override
  String get extraConfirmYes => 'हाँ, मंज़ूर है';

  @override
  String extraIncluded(String amount) {
    return 'इसमें आपका मंज़ूर किया $amount अतिरिक्त शामिल है';
  }

  @override
  String get extraAdd => 'अतिरिक्त शुल्क जोड़ें';

  @override
  String get extraOwnerHelp =>
      'दाम बदलने से पहले ग्राहक को ऐप में इसे मंज़ूर करना होगा।';

  @override
  String get extraHowMuch => 'कितना और';

  @override
  String get extraChooseReason => 'कृपया चुनें कि यह किसके लिए है।';

  @override
  String get extraReasonParts => 'स्पेयर पार्ट्स';

  @override
  String get extraReasonWork => 'अतिरिक्त काम';

  @override
  String get extraReasonMaterial => 'सामान';

  @override
  String get extraReasonOther => 'कुछ और';

  @override
  String get extraSend => 'ग्राहक को भेजें';

  @override
  String extraWaiting(String amount, String reason) {
    return 'ग्राहक के जवाब का इंतज़ार: $amount और ($reason)';
  }

  @override
  String get extraTakeBack => 'वापस लें';

  @override
  String get profileHelp =>
      'बुक करने से पहले ग्राहक इसे देखते हैं। इससे उन्हें आपको चुनने में मदद मिलती है।';

  @override
  String get profileYearsLabel => 'कितने साल का अनुभव';

  @override
  String get profileLanguagesLabel => 'आप कौन सी भाषाएँ बोलते हैं';

  @override
  String get profileAboutLabel => 'आपके बारे में (ज़रूरी नहीं)';

  @override
  String get profileAboutHelp =>
      'अपना फ़ोन नंबर न लिखें: वह ग्राहकों से छिपा दिया जाएगा।';

  @override
  String get profileSaved => 'सेव हो गया। ग्राहक इसे देख सकते हैं।';

  @override
  String get profilePhotosTitle => 'आपके काम की फ़ोटो';

  @override
  String get profilePhotosHelp =>
      'पूरे हुए काम दिखाएँ। ग्राहकों के चेहरे या दस्तावेज़ न दिखाएँ। हम फ़ोटो से जगह की जानकारी हटा देते हैं।';

  @override
  String get profileAddPhoto => 'फ़ोटो जोड़ें';

  @override
  String get profileAboutTitle => 'इस प्रदाता के बारे में';

  @override
  String profileYears(int years) {
    return '$years साल का अनुभव';
  }
}
