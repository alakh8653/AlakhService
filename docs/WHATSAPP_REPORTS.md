# Reports by WhatsApp

Providers can get their daily, weekly, monthly and yearly reports on WhatsApp. It stays off until you set
it up, and each provider turns it on in the app, which records their consent. Email works as soon as
`SMTP_HOST` is set.

## What you need

1. A MSG91 account with KYC done. Until then MSG91 may replace messages with demo text.
2. A phone number connected as your WhatsApp Business number in MSG91's panel.
3. This template, submitted in MSG91's panel and approved by WhatsApp, in the **Utility** category:

   ```
   Hello {{1}}, your AlakhService report for {{2}} is ready.
   Bookings completed: {{3}}
   Earned: {{4}}
   Expenses: {{5}}
   Profit: {{6}}
   Open the app for the full details.
   ```

   Keep it to figures. WhatsApp can move a template with offers in it to the dearer Marketing category.

4. These settings on notification_service:

   ```
   MSG91_AUTH_KEY=...
   MSG91_WHATSAPP_NUMBER=91XXXXXXXXXX
   MSG91_WHATSAPP_TEMPLATE_REPORT=<template name>
   MSG91_WHATSAPP_NAMESPACE=<namespace, if MSG91 shows one>
   MSG91_WHATSAPP_LANGUAGE=en
   ```

## Before you rely on it

**Send one real message first.** The request format in `app/channels/whatsapp.py` was written from memory,
because MSG91's API page could not be confirmed. Check it against MSG91's current API docs. If only the address
differs, set `MSG91_WHATSAPP_API_URL`.

WhatsApp charges per message delivered. Check MSG91's and Meta's current India rates, since published figures
disagree. With every provider on daily reports the cost grows quickly, so consider leaving daily reports to email.
