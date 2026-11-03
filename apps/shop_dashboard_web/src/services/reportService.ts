import apiClient from './apiClient';

// A shop's profit and loss (payment_service): rupees, with weeks, months and financial years in India time.

export type Period = 'daily' | 'weekly' | 'monthly' | 'yearly';
export type EntryKind = 'EXPENSE' | 'INCOME';

export const EXPENSE_CATEGORIES: { value: string; label: string }[] = [
  { value: 'MATERIALS', label: 'Materials' },
  { value: 'SPARE_PARTS', label: 'Spare parts' },
  { value: 'TRAVEL', label: 'Travel and fuel' },
  { value: 'RENT', label: 'Rent' },
  { value: 'STAFF', label: 'Staff pay' },
  { value: 'TOOLS', label: 'Tools' },
  { value: 'BILLS', label: 'Bills' },
  { value: 'MARKETING', label: 'Advertising' },
  { value: 'OTHER', label: 'Other' },
];
export const INCOME_CATEGORIES: { value: string; label: string }[] = [
  { value: 'OUTSIDE_WORK', label: 'Work outside the app' },
  { value: 'OTHER', label: 'Other' },
];

export const categoryLabel = (value: string) =>
  [...EXPENSE_CATEGORIES, ...INCOME_CATEGORIES].find((c) => c.value === value)?.label ?? value;

export interface ShopReport {
  label: string;
  from: string;
  to: string;
  bookings: number;
  gross: number;
  cash: number;
  online: number;
  commission: number;
  gst: number;
  earned: number;
  other_income: number;
  expenses: number;
  profit: number;
  tips: number;
  profit_change_percent: number | null;
  expenses_by_category: { category: string; amount: number }[];
  breakdown: { label: string; earned: number; expenses: number; profit: number }[];
  note: string;
}

export interface CashEntry {
  id: string;
  kind: EntryKind;
  category: string;
  amount: number;
  on_date: string;
  note: string | null;
}

export interface ReportSettings {
  daily: boolean;
  weekly: boolean;
  monthly: boolean;
  yearly: boolean;
  email: boolean;
  whatsapp: boolean;
}

const base = (shopId: string) => `/payments/shops/${encodeURIComponent(shopId)}`;

export async function getReport(shopId: string, period: Period): Promise<ShopReport> {
  const { data } = await apiClient.get<ShopReport>(`${base(shopId)}/report`, { params: { period } });
  return data;
}

export async function getEntries(shopId: string, from: string, to: string): Promise<CashEntry[]> {
  const { data } = await apiClient.get<CashEntry[]>(`${base(shopId)}/cash-entries`, { params: { from, to } });
  return data;
}

export async function addEntry(
  shopId: string,
  entry: { kind: EntryKind; category: string; amount: number; note?: string },
): Promise<CashEntry> {
  const { data } = await apiClient.post<CashEntry>(`${base(shopId)}/cash-entries`, entry);
  return data;
}

export async function removeEntry(shopId: string, id: string): Promise<void> {
  await apiClient.delete(`${base(shopId)}/cash-entries/${encodeURIComponent(id)}`);
}

export async function sendReportNow(shopId: string, period: Period): Promise<string[]> {
  const { data } = await apiClient.post<{ sent_to: string[] }>(`${base(shopId)}/report/send`, null, { params: { period } });
  return data.sent_to;
}

export async function getReportSettings(shopId: string): Promise<ReportSettings> {
  const { data } = await apiClient.get<ReportSettings>(`${base(shopId)}/report-settings`);
  return data;
}

export async function saveReportSettings(shopId: string, settings: ReportSettings): Promise<ReportSettings> {
  const { data } = await apiClient.put<ReportSettings>(`${base(shopId)}/report-settings`, settings);
  return data;
}

/** The whole report as a file, for the owner's records or their accountant. */
export async function downloadReport(shopId: string, period: Period): Promise<Blob> {
  const { data } = await apiClient.get<Blob>(`${base(shopId)}/report.csv`, { params: { period }, responseType: 'blob' });
  return data;
}
