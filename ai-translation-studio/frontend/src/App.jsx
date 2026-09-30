import { useEffect, useRef, useState } from 'react';
import Header from './components/Header';
import TranslationBox from './components/TranslationBox';
import SwapButton from './components/SwapButton';
import TranslateButton from './components/TranslateButton';
import { loadSupportedLanguages, translateText, MAX_TEXT_CHARACTERS } from './api';

export default function App() {
  const [supportedLanguages, setSupportedLanguages] = useState([]);
  const [sourceLanguage, setSourceLanguage] = useState('');
  const [targetLanguage, setTargetLanguage] = useState('');
  const [inputText, setInputText] = useState('');
  const [translatedText, setTranslatedText] = useState('');
  const [isTranslating, setIsTranslating] = useState(false);
  const [isLoadingLanguages, setIsLoadingLanguages] = useState(true);
  const [languageError, setLanguageError] = useState('');
  const [errorMessage, setErrorMessage] = useState('');
  const [languageLoadAttempt, setLanguageLoadAttempt] = useState(0);
  const translationController = useRef(null);

  useEffect(() => {
    const languageController = new AbortController();

    async function fetchLanguages() {
      setIsLoadingLanguages(true);
      setLanguageError('');
      try {
        const languages = await loadSupportedLanguages(languageController.signal);
        if (languageController.signal.aborted) return;
        setSupportedLanguages(languages);
        const initialSource = languages.find((language) => language.name === 'English')?.name || languages[0].name;
        const initialTarget = languages.find((language) => language.name === 'Marathi' && language.name !== initialSource)?.name
          || languages.find((language) => language.name !== initialSource).name;
        setSourceLanguage(initialSource);
        setTargetLanguage(initialTarget);
      } catch (error) {
        if (error.name !== 'AbortError') setLanguageError(error.message);
      } finally {
        if (!languageController.signal.aborted) setIsLoadingLanguages(false);
      }
    }

    fetchLanguages();
    return () => languageController.abort();
  }, [languageLoadAttempt]);

  useEffect(() => () => translationController.current?.abort(), []);

  function clearTranslationError() {
    setErrorMessage('');
  }

  function handleSourceLanguageChange(language) {
    setSourceLanguage(language);
    setTranslatedText('');
    clearTranslationError();
  }

  function handleTargetLanguageChange(language) {
    setTargetLanguage(language);
    setTranslatedText('');
    clearTranslationError();
  }

  function handleInputChange(nextText) {
    setInputText(nextText);
    setTranslatedText('');
    // Match Python's character count and preserve pasted text so users can edit it.
    setErrorMessage(Array.from(nextText).length > MAX_TEXT_CHARACTERS
      ? `Please use ${MAX_TEXT_CHARACTERS.toLocaleString()} characters or fewer.`
      : '');
  }

  function handleSwap() {
    if (translationController.current) return;
    setSourceLanguage(targetLanguage);
    setTargetLanguage(sourceLanguage);
    setInputText(translatedText);
    setTranslatedText(inputText);
    clearTranslationError();
  }

  async function handleTranslate(event) {
    event.preventDefault();
    // A ref guards duplicate submissions immediately, before React re-renders.
    if (translationController.current || isLoadingLanguages || languageError) return;
    clearTranslationError();

    if (!inputText.trim()) {
      setErrorMessage('Please enter some text to translate.');
      return;
    }
    if (Array.from(inputText).length > MAX_TEXT_CHARACTERS) {
      setErrorMessage(`Please use ${MAX_TEXT_CHARACTERS.toLocaleString()} characters or fewer.`);
      return;
    }
    if (sourceLanguage === targetLanguage) {
      setErrorMessage('Source and target languages must be different.');
      return;
    }

    const requestController = new AbortController();
    translationController.current = requestController;
    setIsTranslating(true);
    try {
      const translationResult = await translateText(
        inputText, sourceLanguage, targetLanguage, requestController.signal,
      );
      if (!requestController.signal.aborted) setTranslatedText(translationResult);
    } catch (error) {
      if (error.name !== 'AbortError') setErrorMessage(error.message);
    } finally {
      translationController.current = null;
      if (!requestController.signal.aborted) setIsTranslating(false);
    }
  }

  const areLanguagesUnavailable = isLoadingLanguages || supportedLanguages.length === 0;

  return (
    <main className="flex min-h-dvh items-center justify-center p-4 sm:p-8 lg:p-12">
      <div className="studio-frame w-full max-w-6xl rounded-[2rem] border-2 border-stone-800 bg-white px-5 pt-8 pb-5 sm:px-10 sm:pt-11 sm:pb-7 lg:px-16 lg:pt-14 lg:pb-8">
        <Header />
        <form onSubmit={handleTranslate} aria-label="Translation studio" aria-busy={isTranslating}>
          <div className="translation-grid grid min-w-0 grid-cols-1 items-center gap-2 md:grid-cols-[minmax(0,1fr)_4rem_minmax(0,1fr)] md:gap-2">
            <TranslationBox
              language={sourceLanguage}
              setLanguage={handleSourceLanguageChange}
              languages={supportedLanguages}
              text={inputText}
              setText={handleInputChange}
              placeholder="Enter your text..."
              disabled={isTranslating || areLanguagesUnavailable}
            />
            <SwapButton onClick={handleSwap} disabled={isTranslating || areLanguagesUnavailable} />
            <TranslationBox
              language={targetLanguage}
              setLanguage={handleTargetLanguageChange}
              languages={supportedLanguages}
              text={translatedText}
              readOnly
              placeholder="Translation..."
              disabled={isTranslating || areLanguagesUnavailable}
            />
          </div>
          <div className="mt-8 flex justify-center sm:mt-10">
            <TranslateButton isTranslating={isTranslating} disabled={areLanguagesUnavailable} />
          </div>
          <div className="mt-4 min-h-6 text-center text-sm leading-6" aria-live="polite" aria-atomic="true">
            {isLoadingLanguages && <p className="text-stone-500">Loading languages...</p>}
            {(errorMessage || languageError) && (
              <p className="text-red-700" role="alert">
                {languageError || errorMessage}
                {languageError && (
                  <button type="button" className="ml-2 rounded underline underline-offset-4" onClick={() => setLanguageLoadAttempt((attempt) => attempt + 1)}>
                    Retry
                  </button>
                )}
              </p>
            )}
            {isTranslating && <span className="sr-only">Translation in progress.</span>}
            {!isTranslating && translatedText && !errorMessage && <span className="sr-only">Translation complete.</span>}
          </div>
        </form>
      </div>
    </main>
  );
}
