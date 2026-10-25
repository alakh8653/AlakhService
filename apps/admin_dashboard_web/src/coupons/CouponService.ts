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

/** The last moment of [date] ("yyyy-MM-dd") in India, so a coupon "expiring 15 Nov" works all that day. */
export function endOfDayIst(date: string): string {
  return new Date(`${date}T23:59:59.999+05:30`).toISOString();
}

/** Whether the coupon can still be used right now. */
export function couponState(c: Coupon, now: Date = new Date()): 'active' | 'expired' | 'used_up' | 'inactive' {
  if (!c.isActive) return 'inactive';
  if (c.validTo && new Date(c.validTo) < now) return 'expired';
  if (c.maxUses !== null && c.usesCount >= c.maxUses) return 'used_up';
  return 'active';
}

/** Creates a promo code customers can enter when booking (each customer may use it once). */
export async function createCoupon(c: NewCoupon): Promise<Coupon> {
  const { data } = await adminApiClient.post<CouponRecord>('/coupons', {
    code: c.code.trim().toUpperCase(),
    discount_pct: c.discountPct / 100,
    max_uses: c.maxUses ?? null,
    valid_to: c.validTo ? endOfDayIst(c.validTo) : null,
  });
  return toCoupon(data);
}
