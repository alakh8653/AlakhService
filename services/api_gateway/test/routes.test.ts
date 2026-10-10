import { describe, expect, it } from 'vitest';
import { findRoute, requiredAccess, upstreamPath } from '../src/routes.js';

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

  it('only opens read-only methods on browse routes', () => {
    const route = findRoute('/api/v1/catalog/categories')!;
    expect(requiredAccess(route, 'GET')).toBe('public');
    expect(requiredAccess(route, 'POST')).toBe('user');
  });
});
