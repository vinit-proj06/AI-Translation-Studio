import LanguageSelect from './LanguageSelect';
import { MAX_TEXT_CHARACTERS } from '../api';

export default function TranslationBox({
  language,
  setLanguage,
  languages,
  text,
  setText,
  readOnly = false,
  placeholder,
  disabled = false,
}) {
  const panelLabel = readOnly ? 'Translation' : 'Source text';
  const characterCount = Array.from(text).length;

  const isTextTooLong = !readOnly && characterCount > MAX_TEXT_CHARACTERS;

  return (
    <section className="translation-panel min-w-0 overflow-hidden rounded-3xl border-2 border-stone-800" aria-label={panelLabel}>
      <LanguageSelect
        value={language}
        onChange={setLanguage}
        languages={languages}
        label={readOnly ? 'Target language' : 'Source language'}
        disabled={disabled || languages.length === 0}
      />
      <div className="flex h-60 flex-col sm:h-64">
        <textarea
          aria-label={panelLabel}
          aria-describedby={readOnly ? undefined : 'character-count'}
          aria-invalid={isTextTooLong || undefined}
          className="min-h-0 w-full flex-1 resize-none border-0 bg-transparent px-6 pt-7 pb-3 text-base leading-relaxed outline-none placeholder:text-stone-500 sm:text-lg"
          value={text}
          onChange={readOnly ? undefined : (event) => setText(event.target.value)}
          readOnly={readOnly || disabled}
          placeholder={placeholder}
          dir="auto"
          spellCheck={!readOnly}
        />
        <div className="flex h-9 shrink-0 items-start justify-end px-6 text-xs tabular-nums text-stone-500">
          {!readOnly && (
            <span id="character-count" className={isTextTooLong ? 'text-red-700' : undefined} aria-label={`${characterCount} of ${MAX_TEXT_CHARACTERS} characters`}>
              {characterCount.toLocaleString()} / {MAX_TEXT_CHARACTERS.toLocaleString()}
            </span>
          )}
        </div>
      </div>
    </section>
  );
}
