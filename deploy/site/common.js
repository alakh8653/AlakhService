// Shared by the site's forms. The API is reached on this same domain (Caddy forwards a few auth paths).
'use strict';

window.alakh = {
  /** POST JSON to the API; resolves to {ok, status, body}. */
  async post(path, data) {
    let resp;
    try {
      resp = await fetch('/api/v1' + path, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      });
    } catch (e) {
      return { ok: false, status: 0, body: { detail: 'Could not reach AlakhService. Check your connection and try again.' } };
    }
    let body = {};
    try {
      body = await resp.json();
    } catch (e) {
      body = {};
    }
    return { ok: resp.ok, status: resp.status, body };
  },

  /** A readable message from an API error body (FastAPI gives a string or a list of problems). */
  message(result, fallback) {
    if (result.status === 429) return 'Too many attempts. Please wait a few minutes and try again.';
    const detail = result.body && result.body.detail;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail) && detail.length && detail[0].msg) return detail[0].msg.replace(/^Value error, /, '');
    return fallback;
  },

  /** An email as typed, or a phone number in +91XXXXXXXXXX form. */
  normaliseIdentifier(raw) {
    const value = raw.trim();
    if (value.includes('@')) return value.toLowerCase();
    const digits = value.replace(/[^\d+]/g, '');
    if (/^\+\d{8,15}$/.test(digits)) return digits;
    const local = digits.replace(/^0+/, '');
    if (/^[6-9]\d{9}$/.test(local)) return '+91' + local;
    if (/^91[6-9]\d{9}$/.test(local)) return '+' + local;
    return value;
  },

  setStatus(el, text, kind) {
    el.textContent = text;
    el.className = 'status' + (kind ? ' ' + kind : '');
  },
};
