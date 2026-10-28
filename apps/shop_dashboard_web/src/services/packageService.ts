import apiClient from './apiClient';

// Prepaid packages the shop sells (payment_service): visits of one service paid for upfront. The shop
// earns each visit's share of the price, less commission, as that booking is completed.

export interface ServicePackage {
  id: string;
  shopId: string;
  serviceId: string;
  name: string;
  visits: number;
  priceCents: number;
  validDays: number;
  isActive: boolean;
}

export interface PackageInput {
  serviceId: string;
  name: string;
  visits: number;
  priceCents: number;
  validDays: number;
}

interface PackageRecord {
  id: string;
  shop_id: string;
  service_id: string;
  name: string;
  visits: number;
  price_cents: number;
  valid_days: number;
  is_active: boolean;
}

const toPackage = (r: PackageRecord): ServicePackage => ({
  id: r.id,
  shopId: r.shop_id,
  serviceId: r.service_id,
  name: r.name,
  visits: r.visits,
  priceCents: r.price_cents,
  validDays: r.valid_days,
  isActive: r.is_active,
});

/** All of the shop's packages, those no longer on sale included. */
export async function getPackages(shopId: string): Promise<ServicePackage[]> {
  const { data } = await apiClient.get<PackageRecord[]>(`/packages/shop/${encodeURIComponent(shopId)}`);
  return data.map(toPackage);
}

export async function createPackage(shopId: string, input: PackageInput): Promise<ServicePackage> {
  const { data } = await apiClient.post<PackageRecord>('/packages', {
    shop_id: shopId,
    service_id: input.serviceId,
    name: input.name.trim(),
    visits: input.visits,
    price_cents: input.priceCents,
    valid_days: input.validDays,
  });
  return toPackage(data);
}

/** Puts a package on sale or takes it off; customers who bought it keep their visits. */
export async function setPackageActive(id: string, isActive: boolean): Promise<ServicePackage> {
  const { data } = await apiClient.patch<PackageRecord>(`/packages/${encodeURIComponent(id)}`, { is_active: isActive });
  return toPackage(data);
}
