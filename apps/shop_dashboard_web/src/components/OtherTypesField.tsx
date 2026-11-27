import { useId } from 'react';
import { X } from 'lucide-react';
import { MAX_OTHER_TYPES, SHOP_CATEGORIES, categoryLabel } from '../services/categories';

interface OtherTypesFieldProps {
  /** The shop's main type, which cannot also be another one. */
  main: string;
  value: string[];
  onChange: (types: string[]) => void;
}

/** More types of work beside the main one: an electrician who is also a plumber is found under both. */
export default function OtherTypesField({ main, value, onChange }: OtherTypesFieldProps) {
  const id = useId();
  const chosen = value.filter((type) => type !== main);
  const left = SHOP_CATEGORIES.filter((c) => c.value !== main && !chosen.includes(c.value));

  return (
    <div>
      <label htmlFor={id} className="block text-sm font-medium text-gray-700 mb-1">
        Other types of work <span className="font-normal text-gray-500">(optional)</span>
      </label>
      {chosen.length > 0 && (
        <ul className="flex flex-wrap gap-1.5 mb-2">
          {chosen.map((type) => (
            <li key={type} className="flex items-center gap-1 text-sm bg-indigo-50 text-indigo-800 rounded-full pl-3 pr-1 py-0.5">
              {categoryLabel(type)}
              <button
                type="button"
                onClick={() => onChange(chosen.filter((t) => t !== type))}
                aria-label={`Remove ${categoryLabel(type)}`}
                className="p-1 rounded-full hover:bg-indigo-100"
              >
                <X size={14} aria-hidden />
              </button>
            </li>
          ))}
        </ul>
      )}
      {chosen.length < MAX_OTHER_TYPES && (
        <select
          id={id}
          value=""
          onChange={(e) => e.target.value && onChange([...chosen, e.target.value])}
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
        >
          <option value="">Add another type of work…</option>
          {left.map((c) => (
            <option key={c.value} value={c.value}>
              {c.label}
            </option>
          ))}
        </select>
      )}
      <p className="mt-1 text-xs text-gray-500">Customers find you under each one. Each may ask for its own documents.</p>
    </div>
  );
}
