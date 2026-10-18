import { useEffect, useState } from 'react';
import { searchAccounts, type Account } from './UserService';

// One lookup per id for the whole session: names change rarely and pages show the same people again.
const cache = new Map<string, Promise<Account | null>>();

/** The account with this id, or null if there is none (auth_service's search also matches exact ids). */
export function lookupAccount(id: string): Promise<Account | null> {
  let found = cache.get(id);
  if (!found) {
    found = searchAccounts(id, 5)
      .then((list) => list.find((a) => a.id === id) ?? null)
      .catch(() => {
        cache.delete(id); // try again next time
        return null;
      });
    cache.set(id, found);
  }
  return found;
}

export function clearAccountCache(): void {
  cache.clear();
}

/**
 * Accounts for [ids], keyed by id, filled in as lookups finish. Ids that are not accounts
 * (or could not be looked up) stay missing, so callers fall back to showing the id.
 */
export function useAccounts(ids: (string | null | undefined)[]): Record<string, Account> {
  const key = [...new Set(ids.filter((i): i is string => !!i))].sort().join(',');
  const [accounts, setAccounts] = useState<Record<string, Account>>({});

  useEffect(() => {
    if (!key) return;
    let current = true;
    for (const id of key.split(',')) {
      void lookupAccount(id).then((account) => {
        if (current && account) setAccounts((prev) => (prev[id] ? prev : { ...prev, [id]: account }));
      });
    }
    return () => {
      current = false;
    };
  }, [key]);

  return accounts;
}
