interface FilterChipsProps<T extends string> {
  label: string;
  options: { value: T; label: string }[];
  value: T | undefined;
  onChange: (value: T | undefined) => void;
  allLabel?: string;
}

/** A row of mutually exclusive filters with an "All" choice; the current one is visibly and audibly pressed. */
export default function FilterChips<T extends string>({ label, options, value, onChange, allLabel = 'All' }: FilterChipsProps<T>) {
  const chip = (selected: boolean) =>
    `px-3 py-1.5 rounded-full text-sm font-medium border transition-colors ${
      selected ? 'bg-indigo-600 border-indigo-600 text-white' : 'bg-white border-gray-300 text-gray-700 hover:bg-gray-50'
    }`;
  return (
    <div role="group" aria-label={label} className="flex gap-2 flex-wrap">
      <button type="button" aria-pressed={value === undefined} onClick={() => onChange(undefined)} className={chip(value === undefined)}>
        {allLabel}
      </button>
      {options.map((o) => (
        <button key={o.value} type="button" aria-pressed={value === o.value} onClick={() => onChange(o.value)} className={chip(value === o.value)}>
          {o.label}
        </button>
      ))}
    </div>
  );
}
