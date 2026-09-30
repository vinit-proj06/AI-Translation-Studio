import { ChevronDown } from 'lucide-react';

export default function LanguageSelect({ value, onChange, languages, label, disabled }) {
  return (
    <div className="relative border-b-2 border-stone-800">
      <select
        aria-label={label}
        className="language-select w-full appearance-none bg-transparent px-12 py-5 text-center text-base font-medium outline-none sm:text-lg"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        disabled={disabled}
      >
        {languages.length === 0 && <option value="">Select language</option>}
        {languages.map((language) => (
          <option key={language.name} value={language.name}>{language.name}</option>
        ))}
      </select>
      <ChevronDown
        aria-hidden="true"
        size={21}
        strokeWidth={2}
        className="pointer-events-none absolute top-1/2 right-5 -translate-y-1/2"
      />
    </div>
  );
}
