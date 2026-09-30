export default function TranslateButton({ isTranslating, disabled }) {
  return (
    <button
      type="submit"
      disabled={disabled || isTranslating}
      className="min-h-14 w-52 rounded-2xl border-2 border-stone-800 px-6 py-3 text-base font-medium hover:bg-stone-50 active:bg-stone-100 disabled:cursor-not-allowed disabled:opacity-50"
    >
      {isTranslating ? 'Translating...' : 'Translate'}
    </button>
  );
}
