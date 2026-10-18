import { beforeEach, describe, expect, it, vi } from 'vitest';
import apiClient from '../apiClient';
import { createService, createShop, createStaffMember, getServices, getShopForOwner, updateService, updateShop } from '../shopService';
import { register } from '../authService';
import { formatMoney, toMinorUnits } from '../format';
import { toAuthTokens } from '../tokens';

vi.mock('../apiClient', () => ({
  default: { get: vi.fn(), put: vi.fn(), post: vi.fn() },
}));

const api = vi.mocked(apiClient);

const apiShop = {
  id: 's1',
  owner_id: 'u1',
  name: 'Asha Salon',
  category: 'salon',
  description: null,
  city: 'Pune',
  address: '1 MG Road',
  phone: null,
  email: null,
  rating_avg: 4.2,
  rating_count: 7,
  is_active: true,
  is_verified: false,
  created_at: '2026-01-01T00:00:00Z',
};

describe('shopService', () => {
  beforeEach(() => vi.clearAllMocks());

  it('finds the owner’s shop and returns null when there is none', async () => {
    api.get.mockResolvedValueOnce({ data: [apiShop] }).mockResolvedValueOnce({ data: [] });

    const shop = await getShopForOwner('u1', 'token');
    expect(api.get).toHaveBeenCalledWith('/shops', {
      params: { owner_id: 'u1' },
      headers: { Authorization: 'Bearer token' },
    });
    expect(shop).toMatchObject({ id: 's1', ownerId: 'u1', ratingAvg: 4.2, isVerified: false });
    expect(await getShopForOwner('u2')).toBeNull();
  });

  it('updates the shop with PUT', async () => {
    api.put.mockResolvedValue({ data: { ...apiShop, name: 'New name' } });
    const shop = await updateShop('s1', { name: 'New name', phone: null });
    expect(api.put).toHaveBeenCalledWith('/shops/s1', { name: 'New name', phone: null });
    expect(shop.name).toBe('New name');
  });

  it('lists inactive services too and sends only changed fields', async () => {
    api.get.mockResolvedValue({ data: [] });
    await getServices('s1');
    expect(api.get).toHaveBeenCalledWith('/services', {
      params: { shop_id: 's1', include_inactive: true, limit: 200 },
    });

    api.put.mockResolvedValue({
      data: { id: 'svc1', shop_id: 's1', category_id: null, name: 'Cut', description: null, price_cents: 50000, duration_minutes: 30, is_active: false, created_at: '' },
    });
    const service = await updateService('svc1', { isActive: false });
    expect(api.put).toHaveBeenCalledWith('/services/svc1', { is_active: false });
    expect(service).toMatchObject({ priceCents: 50000, isActive: false });
  });

  it('saves how a service is delivered and its fees', async () => {
    const listing = {
      id: 'svc9',
      category_id: null,
      shop_id: 's1',
      name: 'AC repair',
      description: null,
      price_cents: 79900,
      duration_minutes: 60,
      is_active: true,
      created_at: '2026-01-01T00:00:00Z',
      service_modes: ['AT_HOME', 'PICKUP_DROP'],
      home_visit_fee_cents: 9900,
      pickup_fee_cents: 19900,
    };
    api.post.mockResolvedValueOnce({ data: listing });
    const created = await createService('s1', {
      name: 'AC repair',
      priceCents: 79900,
      durationMinutes: 60,
      serviceModes: ['AT_HOME', 'PICKUP_DROP'],
      homeVisitFeeCents: 9900,
      pickupFeeCents: 19900,
    });
    expect(api.post).toHaveBeenCalledWith('/services', expect.objectContaining({
      service_modes: ['AT_HOME', 'PICKUP_DROP'],
      home_visit_fee_cents: 9900,
      pickup_fee_cents: 19900,
    }));
    expect(created).toMatchObject({ serviceModes: ['AT_HOME', 'PICKUP_DROP'], homeVisitFeeCents: 9900, pickupFeeCents: 19900 });

    // Older listings without modes are at the shop only.
    const { service_modes: _m, home_visit_fee_cents: _h, pickup_fee_cents: _p, ...old } = listing;
    void _m; void _h; void _p;
    api.get.mockResolvedValueOnce({ data: [old] });
    expect((await getServices('s1'))[0]).toMatchObject({ serviceModes: ['AT_SHOP'], homeVisitFeeCents: 0, pickupFeeCents: 0 });
  });

  it('creates staff with empty contact fields as null', async () => {
    api.post.mockResolvedValue({
      data: { id: 'st1', shop_id: 's1', user_id: null, name: 'Ravi', email: null, phone: null, role: 'stylist', service_ids: [], is_active: true, created_at: '' },
    });
    const member = await createStaffMember('s1', { name: 'Ravi', email: '', phone: '', role: 'stylist' });
    expect(api.post).toHaveBeenCalledWith('/staff', {
      shop_id: 's1', name: 'Ravi', email: null, phone: null, role: 'stylist', user_id: null, service_ids: [],
    });
    expect(member).toMatchObject({ id: 'st1', serviceIds: [], isActive: true });
  });
});

describe('helpers', () => {
  it('formats paise as rupees and back', () => {
    expect(formatMoney(49900)).toBe('₹499');
    expect(formatMoney(49950)).toBe('₹499.50');
    expect(formatMoney(12000000)).toBe('₹1,20,000');
    expect(toMinorUnits(499.99)).toBe(49999);
  });

  it('maps auth_service tokens', () => {
    expect(toAuthTokens({ access_token: 'a', refresh_token: 'r', token_type: 'bearer', expires_in: 900 }, 1_000)).toEqual({
      accessToken: 'a',
      refreshToken: 'r',
      expiresAt: 901_000,
    });
  });

  it('opens the owner\'s shop with trimmed details and drops empty fields', async () => {
    api.post.mockResolvedValueOnce({ data: apiShop });
    const shop = await createShop('u1', { name: ' Asha Salon ', category: 'Salon', city: 'Pune', address: ' ', phone: '' });
    expect(api.post).toHaveBeenCalledWith('/shops', {
      owner_id: 'u1',
      name: 'Asha Salon',
      category: 'salon',
      city: 'Pune',
      address: undefined,
      phone: undefined,
      description: undefined,
    });
    expect(shop.id).toBe('s1');
  });

  it('registers an owner account', async () => {
    api.post.mockResolvedValueOnce({
      data: { id: 'u9', email: 'asha@example.com', phone: null, full_name: 'Asha', is_active: true, is_verified: false, role: 'user' },
    });
    const user = await register({ name: ' Asha ', email: 'Asha@Example.com', phone: '', password: 'Passw0rd!' });
    expect(api.post).toHaveBeenLastCalledWith('/auth/register', {
      full_name: 'Asha',
      email: 'asha@example.com',
      password: 'Passw0rd!',
    });
    expect(user.id).toBe('u9');
  });
});
