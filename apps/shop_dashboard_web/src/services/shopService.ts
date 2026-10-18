import apiClient from './apiClient';
import type { OpenInterval, Service, ServiceMode, Shop, ShopHours, StaffMember } from '../types';

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
  latitude?: number | null;
  longitude?: number | null;
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
    latitude: data.latitude ?? null,
    longitude: data.longitude ?? null,
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
  latitude?: number | null;
  longitude?: number | null;
}

export interface NewShop {
  name: string;
  category: string;
  city?: string;
  address?: string;
  phone?: string;
  description?: string;
}

/** Opens the signed-in owner's shop. An owner has one shop; the server refuses a second. */
export async function createShop(ownerId: string, shop: NewShop): Promise<Shop> {
  const optional = (v?: string) => (v && v.trim() ? v.trim() : undefined);
  const { data } = await apiClient.post<ShopResponse>('/shops', {
    owner_id: ownerId,
    name: shop.name.trim(),
    category: shop.category.trim().toLowerCase(),
    city: optional(shop.city),
    address: optional(shop.address),
    phone: optional(shop.phone),
    description: optional(shop.description),
  });
  return toShop(data);
}

export async function updateShop(id: string, update: ShopUpdate): Promise<Shop> {
  const { data } = await apiClient.put<ShopResponse>(`/shops/${id}`, update);
  return toShop(data);
}

// ── Opening hours, holidays and capacity (shop_service) ──────────────────────

interface ShopHoursResponse {
  configured: boolean;
  timezone: string;
  weekly: { day: number; intervals: OpenInterval[] }[];
  holidays: { date: string; note: string | null }[];
  capacity: number;
  capacity_override: number | null;
  active_staff: number;
  updated_at: string | null;
}

export function toShopHours(data: ShopHoursResponse): ShopHours {
  const weekly: OpenInterval[][] = Array.from({ length: 7 }, () => []);
  for (const d of data.weekly) weekly[d.day] = d.intervals.map(({ start, end }) => ({ start, end }));
  return {
    configured: data.configured,
    timezone: data.timezone,
    weekly,
    holidays: data.holidays,
    capacity: data.capacity,
    capacityOverride: data.capacity_override,
    activeStaff: data.active_staff,
    updatedAt: data.updated_at,
  };
}

export async function getShopHours(shopId: string): Promise<ShopHours> {
  const { data } = await apiClient.get<ShopHoursResponse>(`/shops/${shopId}/hours`);
  return toShopHours(data);
}

/** Replaces the whole week: `weekly[0]` is Monday, an empty day is closed. */
export async function saveWeeklyHours(shopId: string, weekly: OpenInterval[][]): Promise<ShopHours> {
  const { data } = await apiClient.put<ShopHoursResponse>(`/shops/${shopId}/hours`, {
    weekly: weekly.map((intervals, day) => ({ day, intervals })),
  });
  return toShopHours(data);
}

/** null goes back to one customer per active staff member. */
export async function saveCapacity(shopId: string, capacity: number | null): Promise<ShopHours> {
  const { data } = await apiClient.put<ShopHoursResponse>(`/shops/${shopId}/capacity`, { capacity });
  return toShopHours(data);
}

export async function addHoliday(shopId: string, date: string, note: string): Promise<ShopHours> {
  const { data } = await apiClient.post<ShopHoursResponse>(`/shops/${shopId}/holidays`, {
    date,
    note: note.trim() || null,
  });
  return toShopHours(data);
}

export async function removeHoliday(shopId: string, date: string): Promise<void> {
  await apiClient.delete(`/shops/${shopId}/holidays/${date}`);
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
  service_modes?: ServiceMode[];
  home_visit_fee_cents?: number;
  pickup_fee_cents?: number;
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
    serviceModes: data.service_modes ?? ['AT_SHOP'],
    homeVisitFeeCents: data.home_visit_fee_cents ?? 0,
    pickupFeeCents: data.pickup_fee_cents ?? 0,
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
  serviceModes?: ServiceMode[];
  homeVisitFeeCents?: number;
  pickupFeeCents?: number;
}

const modeFields = (input: Partial<ServiceInput>) => {
  const body: Record<string, unknown> = {};
  if (input.serviceModes !== undefined) body.service_modes = input.serviceModes;
  if (input.homeVisitFeeCents !== undefined) body.home_visit_fee_cents = input.homeVisitFeeCents;
  if (input.pickupFeeCents !== undefined) body.pickup_fee_cents = input.pickupFeeCents;
  return body;
};

export async function createService(shopId: string, input: ServiceInput): Promise<Service> {
  const { data } = await apiClient.post<ServiceResponse>('/services', {
    shop_id: shopId,
    name: input.name,
    description: input.description ?? null,
    price_cents: input.priceCents,
    duration_minutes: input.durationMinutes ?? null,
    ...modeFields(input),
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
  Object.assign(body, modeFields(update));
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
