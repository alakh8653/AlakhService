import { useEffect, useState, type FormEvent } from 'react';
import { useToast } from '../components/Toast';
import { apiErrorMessage } from '../shared/apiError';
import { getCommission, setDefaultCommission, setShopCommission, type CommissionSettings } from './FinanceService';

/** A percentage typed by an admin, or null when it is not between 0 and 50. */
export function percentFrom(text: string): number | null {
  const value = Number(text.trim());
  if (!text.trim() || !Number.isFinite(value) || value < 0 || value > 50) return null;
  return Math.round(value * 100) / 100;
}

/** The platform's commission: the default for every shop, and shops with a rate of their own. */
export default function CommissionPanel() {
  const notify = useToast();
  const [settings, setSettings] = useState<CommissionSettings | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [shopId, setShopId] = useState('');
  const [shopPercent, setShopPercent] = useState('');
  const [defaultPercent, setDefaultPercent] = useState('');
  const [formError, setFormError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let current = true;
    setError(null);
    getCommission()
      .then((s) => {
        if (current) setSettings(s);
      })
      .catch(() => {
        if (current) setError('Could not load commission rates.');
      });
    return () => {
      current = false;
    };
  }, [reloadKey]);

  const save = async (action: () => Promise<void>, done: string): Promise<boolean> => {
    setSaving(true);
    setFormError(null);
    try {
      await action();
      notify(done);
      setReloadKey((k) => k + 1);
      return true;
    } catch (e) {
      setFormError(apiErrorMessage(e, 'Could not save the rate.'));
      return false;
    } finally {
      setSaving(false);
    }
  };

  const saveShop = (event: FormEvent) => {
    event.preventDefault();
    const percent = percentFrom(shopPercent);
    if (!shopId.trim() || percent === null) {
      setFormError('Enter a shop ID and a rate between 0 and 50%.');
      return;
    }
    void save(() => setShopCommission(shopId.trim(), percent), `Shop ${shopId.trim()} now pays ${percent}% commission.`).then((ok) => {
      if (!ok) return;
      setShopId('');
      setShopPercent('');
    });
  };

  const saveDefault = (event: FormEvent) => {
    event.preventDefault();
    const percent = percentFrom(defaultPercent);
    if (percent === null) {
      setFormError('Enter a rate between 0 and 50%.');
      return;
    }
    void save(() => setDefaultCommission(percent), `The default commission is now ${percent}%.`).then((ok) => ok && setDefaultPercent(''));
  };

  return (
    <section aria-labelledby="commission-title" className="space-y-3">
      <div>
        <h2 id="commission-title" className="text-lg font-semibold text-gray-900">
          Commission
        </h2>
        <p className="text-sm text-gray-600">A new rate applies to bookings completed from now on; earnings already recorded keep theirs.</p>
      </div>
      {error && (
        <p role="alert" className="text-sm text-red-700">
          {error}{' '}
          <button type="button" onClick={() => setReloadKey((k) => k + 1)} className="font-medium underline">
            Try again
          </button>
        </p>
      )}
      {settings && (
        <div className="bg-white rounded-xl shadow p-4 space-y-4 text-sm">
          <p>
            Default commission <strong>{settings.defaultPercent}%</strong> plus GST {settings.gstPercent}% on it
            {settings.defaultPercent !== settings.configuredDefaultPercent && (
              <>
                {' '}
                (configured {settings.configuredDefaultPercent}%,{' '}
                <button
                  type="button"
                  disabled={saving}
                  onClick={() => void save(() => setDefaultCommission(null), 'Back to the configured default.')}
                  className="text-indigo-700 underline"
                >
                  reset
                </button>
                )
              </>
            )}
            .
          </p>
          <form onSubmit={saveDefault} noValidate className="flex flex-wrap items-end gap-2">
            <label>
              <span className="block text-gray-700">New default (%)</span>
              <input
                type="number"
                step="0.01"
                min="0"
                max="50"
                value={defaultPercent}
                onChange={(e) => setDefaultPercent(e.target.value)}
                className="mt-1 w-28 border border-gray-300 rounded-lg px-3 py-1.5"
              />
            </label>
            <button type="submit" disabled={saving} className="border border-gray-300 px-3 py-1.5 rounded-lg font-medium hover:bg-gray-50 disabled:opacity-50">
              Set default
            </button>
          </form>

          <h3 className="font-semibold text-gray-900">Shops with their own rate</h3>
          {settings.overrides.length === 0 ? (
            <p className="text-gray-600">None. Every shop pays the default.</p>
          ) : (
            <ul className="divide-y divide-gray-100">
              {settings.overrides.map((o) => (
                <li key={o.shopId} className="flex items-center justify-between py-1.5">
                  <span className="font-mono text-xs break-all">{o.shopId}</span>
                  <span className="flex items-center gap-3">
                    <strong>{o.percent}%</strong>
                    <button
                      type="button"
                      disabled={saving}
                      onClick={() => void save(() => setShopCommission(o.shopId, null), `Shop ${o.shopId} pays the default again.`)}
                      className="text-indigo-700 hover:underline"
                      aria-label={`Remove the rate for shop ${o.shopId}`}
                    >
                      Remove
                    </button>
                  </span>
                </li>
              ))}
            </ul>
          )}
          <form onSubmit={saveShop} noValidate className="flex flex-wrap items-end gap-2">
            <label>
              <span className="block text-gray-700">Shop ID</span>
              <input value={shopId} onChange={(e) => setShopId(e.target.value)} className="mt-1 w-64 border border-gray-300 rounded-lg px-3 py-1.5" />
            </label>
            <label>
              <span className="block text-gray-700">Rate (%)</span>
              <input
                type="number"
                step="0.01"
                min="0"
                max="50"
                value={shopPercent}
                onChange={(e) => setShopPercent(e.target.value)}
                className="mt-1 w-28 border border-gray-300 rounded-lg px-3 py-1.5"
              />
            </label>
            <button type="submit" disabled={saving} className="bg-indigo-600 text-white px-3 py-1.5 rounded-lg font-medium hover:bg-indigo-700 disabled:opacity-50">
              Set shop rate
            </button>
          </form>
          {formError && (
            <p role="alert" className="text-red-700">
              {formError}
            </p>
          )}
        </div>
      )}
    </section>
  );
}
