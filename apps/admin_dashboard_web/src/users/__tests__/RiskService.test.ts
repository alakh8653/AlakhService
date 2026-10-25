import adminApiClient from '../../apiClient';
import { getRiskHistory, getRiskLevels } from '../RiskService';

vi.mock('../../apiClient', () => ({ default: { get: vi.fn(), post: vi.fn() } }));
const get = vi.mocked(adminApiClient.get);
const post = vi.mocked(adminApiClient.post);

beforeEach(() => vi.clearAllMocks());

describe('RiskService', () => {
  it('looks up every user on the page in one call, keyed by user id', async () => {
    post.mockResolvedValue({
      data: [
        {
          id: 'p1',
          user_id: 'u1',
          risk_score: 0.31,
          risk_level: 'MEDIUM',
          risk_events: 2,
          safe_events: 1,
          ema_score: 0.1,
          last_updated: '2026-10-01T00:00:00Z',
        },
      ],
    });
    const levels = await getRiskLevels(['u1', 'u2', 'u1']);
    expect(post).toHaveBeenCalledWith('/risk/levels', { user_ids: ['u1', 'u2'] });
    expect(levels).toEqual({
      u1: { userId: 'u1', score: 0.31, level: 'MEDIUM', riskEvents: 2, safeEvents: 1, lastUpdated: '2026-10-01T00:00:00Z' },
    });
    // u2 has no profile yet: simply absent.
    expect(levels.u2).toBeUndefined();
  });

  it('makes no call for an empty page and sends at most 200 ids', async () => {
    expect(await getRiskLevels([])).toEqual({});
    expect(post).not.toHaveBeenCalled();

    post.mockResolvedValue({ data: [] });
    await getRiskLevels(Array.from({ length: 250 }, (_, i) => `u${i}`));
    expect((post.mock.calls[0][1] as { user_ids: string[] }).user_ids).toHaveLength(200);
  });

  it("loads a user's recent signals", async () => {
    get.mockResolvedValue({
      data: [{ id: 's1', user_id: 'u/1', signal_type: 'no_show', value: 0.5, created_at: '2026-10-02T10:00:00Z' }],
    });
    const signals = await getRiskHistory('u/1');
    expect(get).toHaveBeenCalledWith('/risk/u%2F1/history', { params: { limit: 20 } });
    expect(signals).toEqual([{ id: 's1', type: 'no_show', value: 0.5, createdAt: '2026-10-02T10:00:00Z' }]);
  });
});
