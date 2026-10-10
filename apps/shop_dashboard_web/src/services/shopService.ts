import apiClient from './apiClient';
import type { Service, Shop, StaffMember } from '../types';

// ── Shops (shop_service) ─────────────────────────────────────────────────────

interface ShopResponse {
  id: string;
  owner_id: string;
  name: string;
  category: string;
  description: string | null;
  city: string | null;
  address: string | null;
  phone: string | null;
  email: string | null;
  rating_avg: number;
  rating_count: number;
  is_active: boolean;
  is_verified: boolean;
  created_at: string;
}

export function toShop(data: ShopResponse): Shop {
  return {
    id: data.id,
    ownerId: data.owner_id,
    name: data.name,
    category: data.category,
    description: data.description,
    city: data.city,
    address: data.address,
    phone: data.phone,
    email: data.email,
    ratingAvg: data.rating_avg,
    ratingCount: data.rating_count,
    isActive: data.is_active,
    isVerified: data.is_verified,
    createdAt: data.created_at,
  };
}

/** The shop owned by `ownerId`, or null when the account has none. */
export async function getShopForOwner(ownerId: string, accessToken?: string): Promise<Shop | null> {
  const { data } = await apiClient.get<ShopResponse[]>('/shops', {
    params: { owner_id: ownerId },
    headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : undefined,
  });
  return data.length > 0 ? toShop(data[0]) : null;
}

export interface ShopUpdate {
  name?: string;
  category?: string;
  description?: string | null;
  city?: string | null;
  address?: string | null;
  phone?: string | null;
  email?: string | null;
}

export async function updateShop(id: string, update: ShopUpdate): Promise<Shop> {
  const { data } = await apiClient.put<ShopResponse>(`/shops/${id}`, update);
  return toShop(data);
}

// ── Services (service_catalog_service) ───────────────────────────────────────

interface ServiceResponse {
  id: string;
  category_id: string | null;
  shop_id: string;
  name: string;
  description: string | null;
  price_cents: number;
  duration_minutes: number | null;
  is_active: boolean;
  created_at: string;
}

export function toService(data: ServiceResponse): Service {
  return {
    id: data.id,
    shopId: data.shop_id,
    categoryId: data.category_id,
    name: data.name,
    description: data.description,
    priceCents: data.price_cents,
    durationMinutes: data.duration_minutes,
    isActive: data.is_active,
    createdAt: data.created_at,
  };
}

export async function getServices(shopId: string): Promise<Service[]> {
  const { data } = await apiClient.get<ServiceResponse[]>('/services', {
    params: { shop_id: shopId, include_inactive: true, limit: 200 },
  });
  return data.map(toService);
}

export interface ServiceInput {
  name: string;
  description?: string | null;
  priceCents: number;
  durationMinutes?: number | null;
}

export async function createService(shopId: string, input: ServiceInput): Promise<Service> {
  const { data } = await apiClient.post<ServiceResponse>('/services', {
    shop_id: shopId,
    name: input.name,
    description: input.description ?? null,
    price_cents: input.priceCents,
    duration_minutes: input.durationMinutes ?? null,
  });
  return toService(data);
}

export async function updateService(
  id: string,
  update: Partial<ServiceInput> & { isActive?: boolean },
): Promise<Service> {
  const body: Record<string, unknown> = {};
  if (update.name !== undefined) body.name = update.name;
  if (update.description !== undefined) body.description = update.description;
  if (update.priceCents !== undefined) body.price_cents = update.priceCents;
  if (update.durationMinutes !== undefined) body.duration_minutes = update.durationMinutes;
  if (update.isActive !== undefined) body.is_active = update.isActive;
  const { data } = await apiClient.put<ServiceResponse>(`/services/${id}`, body);
  return toService(data);
}

// ── Staff (shop_service) ─────────────────────────────────────────────────────

interface StaffResponse {
  id: string;
  shop_id: string;
  user_id: string | null;
  name: string;
  email: string | null;
  phone: string | null;
  role: string;
  service_ids: string[];
  is_active: boolean;
  created_at: string;
}

export function toStaffMember(data: StaffResponse): StaffMember {
  return {
    id: data.id,
    shopId: data.shop_id,
    userId: data.user_id,
    name: data.name,
    email: data.email,
    phone: data.phone,
    role: data.role,
    serviceIds: data.service_ids,
    isActive: data.is_active,
    createdAt: data.created_at,
  };
}

export async function getStaff(shopId: string): Promise<StaffMember[]> {
  const { data } = await apiClient.get<StaffResponse[]>('/staff', {
    params: { shop_id: shopId, include_inactive: true },
  });
  return data.map(toStaffMember);
}

export interface StaffInput {
  name: string;
  email?: string | null;
  phone?: string | null;
  role?: string;
  userId?: string | null;
  serviceIds?: string[];
}

export async function createStaffMember(shopId: string, input: StaffInput): Promise<StaffMember> {
  const { data } = await apiClient.post<StaffResponse>('/staff', {
    shop_id: shopId,
    name: input.name,
    email: input.email || null,
    phone: input.phone || null,
    role: input.role ?? 'staff',
    user_id: input.userId || null,
    service_ids: input.serviceIds ?? [],
  });
  return toStaffMember(data);
}

export async function updateStaffMember(
  id: string,
  update: Partial<StaffInput> & { isActive?: boolean },
): Promise<StaffMember> {
  const body: Record<string, unknown> = {};
  if (update.name !== undefined) body.name = update.name;
  if (update.email !== undefined) body.email = update.email || null;
  if (update.phone !== undefined) body.phone = update.phone || null;
  if (update.role !== undefined) body.role = update.role;
  if (update.userId !== undefined) body.user_id = update.userId || null;
  if (update.serviceIds !== undefined) body.service_ids = update.serviceIds;
  if (update.isActive !== undefined) body.is_active = update.isActive;
  const { data } = await apiClient.put<StaffResponse>(`/staff/${id}`, body);
  return toStaffMember(data);
}
