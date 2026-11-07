import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { StaffMember, User } from '../../types';

const api = vi.hoisted(() => ({ createStaffMember: vi.fn(), getStaff: vi.fn() }));
vi.mock('../../services/shopService', () => api);

import { withOwnerOnTeam } from '../useStaff';

const owner: User = { id: 'u', name: 'Asha Rao', email: null, phone: null, role: 'shop_owner' };
const member = (over: Partial<StaffMember>): StaffMember => ({
  id: 'st', shopId: 's1', userId: null, name: 'Ravi', email: null, phone: null, role: 'staff', serviceIds: [],
  workingHours: null, isActive: true, createdAt: '', ...over,
});

beforeEach(() => {
  api.createStaffMember.mockReset();
});

describe('withOwnerOnTeam', () => {
  it('adds the owner, linked to their account, when they are not on the team', async () => {
    const asha = member({ id: 'st2', userId: 'u', name: 'Asha Rao', role: 'owner' });
    api.createStaffMember.mockResolvedValue(asha);
    const ravi = member({});
    expect(await withOwnerOnTeam('s1', owner, [ravi])).toEqual([ravi, asha]);
    expect(api.createStaffMember).toHaveBeenCalledWith('s1', { name: 'Asha Rao', role: 'owner', userId: 'u' });
  });

  it('keeps the team as it is when the owner is already on it, active or not', async () => {
    const off = [member({ userId: 'u', isActive: false })];
    expect(await withOwnerOnTeam('s1', owner, off)).toBe(off);
    expect(api.createStaffMember).not.toHaveBeenCalled();
  });

  it('asks only once when two pages open together', async () => {
    let finish: (m: StaffMember) => void = () => {};
    api.createStaffMember.mockReturnValue(new Promise<StaffMember>((r) => (finish = r)));
    const both = Promise.all([withOwnerOnTeam('s1', owner, []), withOwnerOnTeam('s1', owner, [])]);
    finish(member({ userId: 'u' }));
    const [a, b] = await both;
    expect(api.createStaffMember).toHaveBeenCalledTimes(1);
    expect(a).toHaveLength(1);
    expect(b).toHaveLength(1);
  });

  it('leaves the team unchanged when adding fails, so the page still works', async () => {
    api.createStaffMember.mockImplementation(async () => {
      throw new Error('offline');
    });
    expect(await withOwnerOnTeam('s1', owner, [])).toEqual([]);
  });
});
