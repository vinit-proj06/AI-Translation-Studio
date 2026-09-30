import { ArrowRightLeft } from 'lucide-react';

export default function SwapButton({ onClick, disabled }) {
  return (
    <button
      type="button"
      aria-label="Swap languages and texts"
      title="Swap languages and texts"
      className="swap-button mx-auto flex h-12 w-12 items-center justify-center rounded-full hover:bg-stone-100 disabled:cursor-not-allowed disabled:opacity-35"
      onClick={onClick}
      disabled={disabled}
    >
      <ArrowRightLeft aria-hidden="true" size={29} strokeWidth={1.5} className="rotate-90 md:rotate-0" />
    </button>
  );
}
