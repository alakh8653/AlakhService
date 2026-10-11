import adminApiClient from '../apiClient';

export interface Coupon {
  id: string;
  code: string;
  /** Percent off, e.g. 10 (the API stores it as a fraction, 0.10). */
  discountPct: number;
  maxUses: number | null;
  usesCount: number;
  validFrom: string | null;
  validTo: string | null;
  isActive: boolean;
}

interface CouponRecord {
  id: string;
  code: string;
  discount_pct: number;
  max_uses: number | null;
  uses_count: number;
  valid_from: string | null;
  valid_to: string | null;
  is_active: boolean;
}

export const toCoupon = (r: CouponRecord): Coupon => ({
  id: r.id,
  code: r.code,
  discountPct: Math.round(r.discount_pct * 1000) / 10,
  maxUses: r.max_uses,
  usesCount: r.uses_count,
  validFrom: r.valid_from,
  validTo: r.valid_to,
  isActive: r.is_active,
});

export async function getCoupons(): Promise<Coupon[]> {
  const { data } = await adminApiClient.get<CouponRecord[]>('/coupons');
  return data.map(toCoupon);
}

export interface NewCoupon {
  code: string;
  discountPct: number;
  maxUses?: number | null;
  validTo?: string | null;
}

/** Creates a promo code customers can enter when booking (each customer may use it once). */
export async function createCoupon(c: NewCoupon): Promise<Coupon> {
  const { data } = await adminApiClient.post<CouponRecord>('/coupons', {
    code: c.code.trim().toUpperCase(),
    discount_pct: c.discountPct / 100,
    max_uses: c.maxUses ?? null,
    valid_to: c.validTo ? new Date(c.validTo).toISOString() : null,
  });
  return toCoupon(data);
}
