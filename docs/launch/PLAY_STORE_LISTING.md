# Play Store listing (draft)

Everything Google Play Console asks for when you publish the Android app, ready to paste. Replace the
`[brackets]`. The texts match what the app really does today; keep them true when the app changes,
because Google checks the listing against the app.

- **Package name:** `com.alakhservice.alakh_service`. Permanent after the first upload.
- **Category:** Lifestyle (or "Local & services" if your console offers it)
- **Contact email:** `[support@yourdomain.in]` (shown publicly)
- **Privacy policy URL:** `https://[yourdomain.in]/privacy`
- **Account deletion URL:** `https://[yourdomain.in]/delete-account`

## Store listing: English

**App name** (30 characters max)

```
AlakhService: Book Local Pros
```

**Short description** (80 characters max)

```
Book salons, repairs and home services near you. Pay safely, track live.
```

**Full description** (4000 characters max)

```
AlakhService helps you book trusted local shops and professionals: salons and spas, AC and
appliance repair, electricians, plumbers, laptop and phone repair, cleaning and many more.

BOOK THE WAY THAT SUITS YOU
• Visit the shop, have a professional come to your home, or use pickup and drop
• See only the times a shop really has free, from its opening hours
• Join a shop's line on the day and see your place and expected wait, live

PAY SAFELY
• Pay online with UPI, cards or net banking through Razorpay, or pay at the shop
• Get a GST invoice for every online payment
• Cancel in time and your money comes back automatically

KNOW WHAT'S HAPPENING
• Live tracking when a professional is on the way
• Booking reminders and updates as notifications
• Chat with the shop inside the app

YOUR PRIVACY IS PROTECTED
• Shops see only your first name and initial, never your phone number or email
• Phone numbers and emails typed into chat are hidden automatically
• Delete your account at any time, from the app or our website

MORE
• Ratings and reviews from real customers who completed a booking
• Prepaid visit packages, tips for good service and reward points
• English and Hindi, light and dark themes

FOR SHOP OWNERS AND PROFESSIONALS
Run your business from the same app: accept bookings, set your hours, manage your queue, chat with
customers and see your earnings and payouts.

Questions? Write to [support@yourdomain.in].
```

## Store listing: Hindi (हिन्दी)

**App name**

```
AlakhService: लोकल सेवाएँ
```

**Short description**

```
पास के सैलून, रिपेयर और घर की सेवाएँ बुक करें। सुरक्षित भुगतान, लाइव ट्रैकिंग।
```

**Full description**

```
AlakhService से भरोसेमंद लोकल दुकानें और प्रोफ़ेशनल बुक करें: सैलून और स्पा, AC और उपकरण रिपेयर,
इलेक्ट्रीशियन, प्लंबर, लैपटॉप और फ़ोन रिपेयर, सफ़ाई और बहुत कुछ।

अपने तरीके से बुक करें
• दुकान पर जाएँ, प्रोफ़ेशनल को घर बुलाएँ, या पिकअप और ड्रॉप चुनें
• केवल वही समय दिखते हैं जब दुकान सच में खाली है
• उसी दिन दुकान की लाइन में जुड़ें और अपनी जगह व इंतज़ार का समय लाइव देखें

सुरक्षित भुगतान
• Razorpay से UPI, कार्ड या नेट बैंकिंग से ऑनलाइन भुगतान करें, या दुकान पर भुगतान करें
• हर ऑनलाइन भुगतान का GST इनवॉइस
• समय पर रद्द करने पर पैसा अपने-आप वापस

हर अपडेट आपके पास
• प्रोफ़ेशनल के रास्ते में होने पर लाइव ट्रैकिंग
• बुकिंग रिमाइंडर और अपडेट नोटिफ़िकेशन से
• ऐप के अंदर दुकान से चैट

आपकी प्राइवेसी सुरक्षित
• दुकानों को केवल आपका पहला नाम और नाम का पहला अक्षर दिखता है, फ़ोन नंबर या ईमेल कभी नहीं
• चैट में लिखे फ़ोन नंबर और ईमेल अपने-आप छिप जाते हैं
• ऐप या वेबसाइट से कभी भी अपना अकाउंट डिलीट करें

दुकान मालिकों और प्रोफ़ेशनल के लिए
उसी ऐप से अपना काम चलाएँ: बुकिंग स्वीकार करें, समय तय करें, लाइन संभालें, ग्राहकों से चैट करें और
अपनी कमाई व भुगतान देखें।

सवाल? [support@yourdomain.in] पर लिखें।
```

## Graphics you need

| Asset | Size | Notes |
|---|---|---|
| App icon | 512 × 512 PNG | Export `apps/mobile_app/assets/branding/app_icon.png` at 512 px |
| Feature graphic | 1024 × 500 PNG/JPG | The brand colour (#5B52F0), the logo and one line, e.g. "Book local pros near you" |
| Phone screenshots | 2–8, 1080 × 1920 or larger | Home, a service with free times, booking, live tracking, chat, a GST invoice. Take them from a real phone with demo data, never with real customers' details |

## Data safety form

Answer **Yes** to "Does your app collect or share any of the required user data types?" Then:

| Data type | Collected | Shared | Why (purposes to tick) | Optional? |
|---|---|---|---|---|
| Personal info: name | Yes | No | App functionality, account management | Required |
| Personal info: email address | Yes | No | Account management, app functionality (sign-in, receipts) | Required for email sign-in |
| Personal info: phone number | Yes | No | Account management, app functionality (sign-in codes, booking updates by SMS) | Required for phone sign-in |
| Personal info: address | Yes | No | App functionality (home visits and pickups) | Optional |
| Financial info: purchase history | Yes | No | App functionality (bookings, invoices, refunds) | Required |
| Financial info: other (shop owners' bank account or UPI ID for payouts) | Yes | No | App functionality | Only for shop owners |
| Location: precise | Yes | No | App functionality (directions, live tracking of a professional on the way) | Optional (asked first, with a reason) |
| Messages: other in-app messages | Yes | No | App functionality (booking chat) | Optional |
| Photos and videos / Files and docs (shop owners' verification documents) | Yes | No | App functionality, fraud prevention | Only for shop owners |
| App activity: other user-generated content (reviews) | Yes | No | App functionality | Optional |
| Device or other IDs (notification token) | Yes | No | App functionality (notifications) | Required for notifications |

Then answer:

- **Is all data encrypted in transit?** Yes (HTTPS only).
- **Do you provide a way for users to request that their data be deleted?** Yes: in the app
  (Profile → Delete account) and at `https://[yourdomain.in]/delete-account`.
- **Payment card details:** not collected by the app. Razorpay's checkout handles them, so do not
  tick "Credit card" for your app. Razorpay is a payment processor acting for you, which Play does
  not count as "sharing".
- **Analytics or ads:** none. The app has no advertising or third-party analytics SDK.

## Other Play Console sections

- **App access:** reviewers need a login. Create a demo customer account (`[review@yourdomain.in]` /
  password) on the live server with one approved demo shop, and give those details here.
- **Ads:** No.
- **Content rating:** fill in the questionnaire honestly (no violence or gambling; users can chat
  with shops). The usual result is "Everyone" or "Teen" because of user communication.
- **Target audience:** 18 and over. Customers book and pay, and shop owners run a business.
- **News app:** No. **COVID-19 app:** No. **Government app:** No.
- **Financial features declaration:** the app takes payments for services through Razorpay; it is
  not a lender or a wallet.
- **Permissions declaration:** location is used only while the app is open (no background location).
- **Release:** start with **Internal testing**, then **Closed testing** with a few real shops and
  customers. Production only after the launch checklist (`LAUNCH_CHECKLIST.md`) is done.
