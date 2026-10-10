import adminApiClient from '../apiClient';

export type SettlementStatus = 'pending' | 'processing' | 'completed' | 'failed';

export interface Settlement {
  id: string;
  shopId: string;
  shopName: string;
  amount: number;
  currency: string;
  status: SettlementStatus;
  periodStart: string;
  periodEnd: string;
  createdAt: string;
}

export interface PaginatedSettlements {
  data: Settlement[];
  total: number;
  page: number;
  totalPages: number;
}

export interface RevenuePoint {
  date: string;
  grossRevenue: number;
  platformFees: number;
  refunds: number;
}

export interface RevenueReport {
  currency: string;
  totalGross: number;
  totalFees: number;
  totalRefunds: number;
  series: RevenuePoint[];
}

export async function getSettlements(
  filters: { status?: SettlementStatus; page?: number; perPage?: number } = {},
): Promise<PaginatedSettlements> {
  const { data } = await adminApiClient.get<PaginatedSettlements>('/admin/finance/settlements', { params: filters });
  return data;
}

export async function getRevenueReport(params: { dateFrom?: string; dateTo?: string } = {}): Promise<RevenueReport> {
  const { data } = await adminApiClient.get<{ data: RevenueReport }>('/admin/finance/revenue', { params });
  return data.data;
}

export function formatMoney(amount: number, currency: string): string {
  return new Intl.NumberFormat('en-IN', { style: 'currency', currency }).format(amount);
}
