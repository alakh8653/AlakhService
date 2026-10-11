import adminApiClient from '../../apiClient';
import { createCoupon, getCoupons } from '../CouponService';

vi.mock('../../apiClient', () => ({ default: { get: vi.fn(), post: vi.fn() } }));
const get = vi.mocked(adminApiClient.get);
const post = vi.mocked(adminApiClient.post);

const record = {
  id: 'c1', code: 'DIWALI25', discount_pct: 0.25, max_uses: 100, uses_count: 3,
  valid_from: null, valid_to: '2026-11-15T00:00:00Z', is_active: true,
};

describe('CouponService', () => {
  it('lists coupons', async () => {
    get.mockResolvedValue({ data: [record] });
    expect((await getCoupons())[0]).toMatchObject({ code: 'DIWALI25', discountPct: 25, usesCount: 3 });
    expect(get).toHaveBeenCalledWith('/coupons');
  });

  it('creates a coupon with an upper-cased code', async () => {
    post.mockResolvedValue({ data: record });
    await createCoupon({ code: ' diwali25 ', discountPct: 25, maxUses: 100, validTo: '2026-11-15' });
    expect(post).toHaveBeenCalledWith('/coupons', {
      code: 'DIWALI25', discount_pct: 0.25, max_uses: 100, valid_to: new Date('2026-11-15').toISOString(),
    });
  });
});
