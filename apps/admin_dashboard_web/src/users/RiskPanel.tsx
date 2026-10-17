import { useEffect, useState } from 'react';
import { format } from 'date-fns';
import { X } from 'lucide-react';
import { getRiskHistory, type RiskLevel, type RiskProfile, type RiskSignal } from './RiskService';

const LEVELS: Record<RiskLevel, { label: string; className: string }> = {
  LOW: { label: 'Low', className: 'bg-green-100 text-green-800' },
  MEDIUM: { label: 'Medium', className: 'bg-yellow-100 text-yellow-800' },
  HIGH: { label: 'High', className: 'bg-orange-100 text-orange-800' },
  CRITICAL: { label: 'Critical', className: 'bg-red-100 text-red-800' },
};

export function RiskBadge({ level }: { level: RiskLevel }) {
  const { label, className } = LEVELS[level] ?? LEVELS.HIGH;
  return <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${className}`}>{label}</span>;
}

const signalName = (type: string) => type.replace(/_/g, ' ');

/** A user's risk score and their recent signals, newest first. */
export default function RiskPanel({ name, profile, onClose }: { name: string; profile: RiskProfile; onClose: () => void }) {
  const [signals, setSignals] = useState<RiskSignal[] | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let current = true;
    setSignals(null);
    setError(false);
    getRiskHistory(profile.userId)
      .then((s) => {
        if (current) setSignals(s);
      })
      .catch(() => {
        if (current) setError(true);
      });
    return () => {
      current = false;
    };
  }, [profile.userId]);

  return (
    <section aria-label={`Risk signals for ${name}`} className="bg-white rounded-2xl shadow p-6 space-y-3">
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Risk · {name}</h2>
          <p className="text-sm text-gray-600 flex items-center gap-2">
            <RiskBadge level={profile.level} />
            score {profile.score.toFixed(2)} · {profile.riskEvents} risk / {profile.safeEvents} safe events
          </p>
        </div>
        <button type="button" aria-label="Close" onClick={onClose} className="p-1 text-gray-500 hover:text-gray-900">
          <X size={18} />
        </button>
      </div>
      {error && <p className="text-sm text-red-600">Could not load signals.</p>}
      {!error && signals === null && <p className="text-gray-400 text-sm">Loading…</p>}
      {signals?.length === 0 && <p className="text-gray-400 text-sm">No signals recorded.</p>}
      {signals && signals.length > 0 && (
        <ul className="divide-y divide-gray-100 text-sm">
          {signals.map((s) => (
            <li key={s.id} className="flex justify-between py-2">
              <span className="capitalize">{signalName(s.type)}</span>
              <span className="text-gray-500">
                {s.value > 0 ? `${s.value.toFixed(1)} · ` : ''}
                {format(new Date(s.createdAt), 'MMM d, yyyy HH:mm')}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
