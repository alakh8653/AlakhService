import adminApiClient from '../apiClient';

export type RiskLevel = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';

export interface RiskProfile {
  userId: string;
  score: number;
  level: RiskLevel;
  riskEvents: number;
  safeEvents: number;
  lastUpdated: string;
}

export interface RiskSignal {
  id: string;
  type: string;
  value: number;
  createdAt: string;
}

interface ProfileRecord {
  user_id: string;
  risk_score: number;
  risk_level: RiskLevel;
  risk_events: number;
  safe_events: number;
  last_updated: string;
}

interface SignalRecord {
  id: string;
  signal_type: string;
  value: number;
  created_at: string;
}

// trust_risk_service accepts at most this many ids per lookup.
const MAX_IDS = 200;

/**
 * Risk profiles for [userIds], keyed by user id, in one call (trust_risk_service, admins only).
 * A user with no signals yet has no profile and is simply missing from the result.
 */
export async function getRiskLevels(userIds: string[]): Promise<Record<string, RiskProfile>> {
  const ids = [...new Set(userIds)].slice(0, MAX_IDS);
  if (ids.length === 0) return {};
  const { data } = await adminApiClient.post<ProfileRecord[]>('/risk/levels', { user_ids: ids });
  return Object.fromEntries(
    data.map((r) => [
      r.user_id,
      {
        userId: r.user_id,
        score: r.risk_score,
        level: r.risk_level,
        riskEvents: r.risk_events,
        safeEvents: r.safe_events,
        lastUpdated: r.last_updated,
      },
    ]),
  );
}

/** The user's most recent signals, newest first. */
export async function getRiskHistory(userId: string, limit = 20): Promise<RiskSignal[]> {
  const { data } = await adminApiClient.get<SignalRecord[]>(`/risk/${encodeURIComponent(userId)}/history`, {
    params: { limit },
  });
  return data.map((s) => ({ id: s.id, type: s.signal_type, value: s.value, createdAt: s.created_at }));
}
