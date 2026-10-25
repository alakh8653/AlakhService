import apiClient from './apiClient';

// The public legal pages (https://{DOMAIN}/terms, /privacy, /refunds, /grievance, /delete-account) and
// the terms version an owner accepts when signing up. VITE_SITE_URL is the public site, e.g.
// https://alakhservice.in; without it the pages are taken to live on the dashboard's own origin.

const SITE_URL = ((import.meta.env.VITE_SITE_URL as string | undefined) || '').replace(/\/+$/, '');

/** The terms version this build shows; auth_service's /legal/current is preferred when it answers. */
export const TERMS_VERSION = (import.meta.env.VITE_TERMS_VERSION as string | undefined) || '2026-10';

export function siteUrl(): string {
  return SITE_URL || (typeof window !== 'undefined' ? window.location.origin : '');
}

export interface LegalLinks {
  termsVersion: string;
  termsUrl: string;
  privacyUrl: string;
  refundUrl: string;
  grievanceUrl: string;
  deleteAccountUrl: string;
}

export function defaultLegalLinks(): LegalLinks {
  const base = siteUrl();
  return {
    termsVersion: TERMS_VERSION,
    termsUrl: `${base}/terms`,
    privacyUrl: `${base}/privacy`,
    refundUrl: `${base}/refunds`,
    grievanceUrl: `${base}/grievance`,
    deleteAccountUrl: `${base}/delete-account`,
  };
}

interface LegalResponse {
  terms_version?: string;
  terms_url?: string;
  privacy_url?: string;
  refund_url?: string;
  grievance_url?: string;
}

const safeUrl = (value: string | undefined, fallback: string) => (value && /^https?:\/\//.test(value) ? value : fallback);

/** GET /legal/current (public); falls back to this build's links when it is unavailable. */
export async function getLegalLinks(): Promise<LegalLinks> {
  const fallback = defaultLegalLinks();
  try {
    const { data } = await apiClient.get<LegalResponse>('/legal/current', { timeout: 5000 });
    return {
      termsVersion: data.terms_version || fallback.termsVersion,
      termsUrl: safeUrl(data.terms_url, fallback.termsUrl),
      privacyUrl: safeUrl(data.privacy_url, fallback.privacyUrl),
      refundUrl: safeUrl(data.refund_url, fallback.refundUrl),
      grievanceUrl: safeUrl(data.grievance_url, fallback.grievanceUrl),
      deleteAccountUrl: fallback.deleteAccountUrl,
    };
  } catch {
    return fallback;
  }
}
