export const API_URL = 'http://localhost:8000';
export const MAX_TEXT_CHARACTERS = 2000;

async function requestApi(endpoint, options = {}) {
  let response;

  try {
    response = await fetch(`${API_URL}${endpoint}`, options);
  } catch (error) {
    if (error.name === 'AbortError') throw error;
    throw new Error('Unable to connect to the translation server. Check that the backend is running.');
  }

  let responseBody;
  try {
    responseBody = await response.json();
  } catch {
    throw new Error('The translation server returned an invalid response. Please try again.');
  }

  if (!responseBody || typeof responseBody !== 'object' || Array.isArray(responseBody)) {
    throw new Error('The translation server returned an invalid response. Please try again.');
  }

  if (!response.ok) {
    const serverMessage = responseBody.detail?.message;
    throw new Error(
      typeof serverMessage === 'string'
        ? serverMessage
        : 'Translation failed. Please try again.',
    );
  }

  return responseBody;
}

export async function loadSupportedLanguages(signal) {
  const responseBody = await requestApi('/languages', { signal });
  const supportedLanguages = responseBody.languages;

  if (
    !Array.isArray(supportedLanguages) ||
    supportedLanguages.length < 2 ||
    supportedLanguages.some((language) => (
      !language || typeof language.name !== 'string' || !language.name.trim()
    ))
  ) {
    throw new Error('Supported languages could not be loaded. Please try again.');
  }

  if (new Set(supportedLanguages.map((language) => language.name)).size !== supportedLanguages.length) {
    throw new Error('Supported languages could not be loaded. Please try again.');
  }

  return supportedLanguages;
}

export async function translateText(inputText, sourceLanguage, targetLanguage, signal) {
  const translationResponse = await requestApi('/translate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      text: inputText,
      source_language: sourceLanguage,
      target_language: targetLanguage,
    }),
    signal,
  });

  if (typeof translationResponse.translation !== 'string' || !translationResponse.translation.trim()) {
    throw new Error('The translation server returned an invalid translation. Please try again.');
  }

  return translationResponse.translation;
}
