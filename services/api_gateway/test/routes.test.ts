import { describe, expect, it } from 'vitest';
import { findRoute, isUpload, requiredAccess, upstreamPath } from '../src/routes.js';

describe('route table', () => {
  it('matches the longest prefix on whole path segments', () => {
    expect(findRoute('/api/v1/auth/login')?.access).toBe('public');
    expect(findRoute('/api/v1/auth/me')?.upstream).toBe('auth');
    expect(requiredAccess(findRoute('/api/v1/auth/me')!, 'GET')).toBe('user');
    expect(findRoute('/api/v1/authx')).toBeUndefined();
    expect(findRoute('/api/v1/admin/disputes/7')?.upstream).toBe('dispute');
    expect(findRoute('/api/v1/admin/users')?.upstream).toBe('admin');
  });

  it('rewrites admin dashboard paths onto the owning service', () => {
    const route = findRoute('/api/v1/admin/audit-logs/42')!;
    expect(upstreamPath(route, '/api/v1/admin/audit-logs/42')).toBe('/api/v1/audit-logs/42');
    const plain = findRoute('/api/v1/bookings/1')!;
    expect(upstreamPath(plain, '/api/v1/bookings/1')).toBe('/api/v1/bookings/1');
  });

  it('opens shop reviews to read, takes an account to write and an admin to moderate', () => {
    const reviews = findRoute('/api/v1/shops/s1/reviews')!;
    expect(reviews.upstream).toBe('shop');
    expect(requiredAccess(reviews, 'GET')).toBe('public');
    expect(requiredAccess(findRoute('/api/v1/shops/ratings')!, 'GET')).toBe('public');
    expect(requiredAccess(findRoute('/api/v1/shops/s1/reviews/r1/reply')!, 'PUT')).toBe('user');
    expect(requiredAccess(findRoute('/api/v1/shops/s1/reviews/r1/report')!, 'POST')).toBe('user');
    expect(requiredAccess(findRoute('/api/v1/shops/s1/rating')!, 'POST')).toBe('user');

    const moderation = findRoute('/api/v1/reviews/reported')!;
    expect(moderation.upstream).toBe('shop');
    expect(requiredAccess(moderation, 'GET')).toBe('admin');
    expect(requiredAccess(findRoute('/api/v1/reviews/r1/visibility')!, 'PUT')).toBe('admin');
    const viaAdmin = findRoute('/api/v1/admin/reviews/r1/visibility')!;
    expect(viaAdmin.upstream).toBe('shop');
    expect(upstreamPath(viaAdmin, '/api/v1/admin/reviews/r1/visibility')).toBe('/api/v1/reviews/r1/visibility');
  });

  it('sends booking chat to booking_service for signed-in users and its moderation to admins only', () => {
    const chat = findRoute('/api/v1/bookings/b1/messages')!;
    expect(chat.upstream).toBe('booking');
    expect(requiredAccess(chat, 'POST')).toBe('user');
    expect(requiredAccess(findRoute('/api/v1/bookings/b1/call')!, 'POST')).toBe('user');

    const moderation = findRoute('/api/v1/chat-moderation/flagged')!;
    expect(moderation.upstream).toBe('booking');
    expect(requiredAccess(moderation, 'GET')).toBe('admin');
    const viaAdmin = findRoute('/api/v1/admin/chat/repeat-offenders')!;
    expect(requiredAccess(viaAdmin, 'GET')).toBe('admin');
    expect(viaAdmin.upstream).toBe('booking');
    expect(upstreamPath(viaAdmin, '/api/v1/admin/chat/repeat-offenders')).toBe('/api/v1/chat-moderation/repeat-offenders');
  });

  it('sends shop earnings, payouts and invoices to payment_service, and payout admin to admins only', () => {
    const earnings = findRoute('/api/v1/payments/shops/s1/earnings')!;
    expect(earnings.upstream).toBe('payment');
    expect(requiredAccess(earnings, 'GET')).toBe('user');
    expect(requiredAccess(findRoute('/api/v1/payments/p1/invoice')!, 'GET')).toBe('user');

    const payouts = findRoute('/api/v1/admin/payments/payouts/export.csv')!;
    expect(payouts.upstream).toBe('payment');
    expect(requiredAccess(payouts, 'GET')).toBe('admin');
    expect(upstreamPath(payouts, '/api/v1/admin/payments/payouts/export.csv')).toBe(
      '/api/v1/admin/payments/payouts/export.csv',
    );
    expect(requiredAccess(findRoute('/api/v1/admin/payments/commission/s1')!, 'PUT')).toBe('admin');
    // Internal routes are never reachable through the gateway.
    expect(findRoute('/internal/payments/booking/b1/cancelled')).toBeUndefined();
  });

  it('sends shop onboarding review to shop_service for admins only, and KYC documents to signed-in owners', () => {
    const queue = findRoute('/api/v1/admin/shops/review-queue')!;
    expect(queue.upstream).toBe('shop');
    expect(requiredAccess(queue, 'GET')).toBe('admin');
    expect(upstreamPath(queue, '/api/v1/admin/shops/s1/approve')).toBe('/api/v1/admin/shops/s1/approve');
    expect(findRoute('/api/v1/admin/shopsx')?.upstream).toBe('admin');

    const docs = findRoute('/api/v1/shops/s1/documents/upload')!;
    expect(docs.upstream).toBe('shop');
    expect(requiredAccess(docs, 'POST')).toBe('user');
    expect(requiredAccess(findRoute('/api/v1/shops/s1/payout-details')!, 'PUT')).toBe('user');
    expect(requiredAccess(findRoute('/api/v1/shops/s1/submit-for-review')!, 'POST')).toBe('user');
  });

  it('allows a larger body only on upload routes', () => {
    expect(isUpload('/api/v1/users/me/avatar')).toBe(true);
    expect(isUpload('/api/v1/shops/s1/documents/upload')).toBe(true);
    expect(isUpload('/api/v1/shops/s1/documents')).toBe(false);
    expect(isUpload('/api/v1/shops/s1/x/documents/upload')).toBe(false);
    expect(isUpload('/api/v1/bookings')).toBe(false);
  });

  it('opens the legal links and code-based account deletion without an account', () => {
    const legal = findRoute('/api/v1/legal/current')!;
    expect(legal.upstream).toBe('auth');
    expect(requiredAccess(legal, 'GET')).toBe('public');
    expect(requiredAccess(legal, 'POST')).toBe('user');
    const byCode = findRoute('/api/v1/auth/delete-account/otp')!;
    expect(requiredAccess(byCode, 'POST')).toBe('public');
    // Deleting with a password still needs the person signed in.
    expect(requiredAccess(findRoute('/api/v1/auth/delete-account')!, 'POST')).toBe('user');
  });

  it('only opens read-only methods on browse routes', () => {
    const route = findRoute('/api/v1/categories')!;
    expect(requiredAccess(route, 'GET')).toBe('public');
    expect(requiredAccess(route, 'POST')).toBe('user');
  });
});
