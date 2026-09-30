"""Local, pretrained NLLB-200 inference for an academic NLP mini-project."""

import gc
import logging
import re
from contextlib import asynccontextmanager
from threading import Lock, Thread

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field


# ============================================================
# Configuration and supported languages
# ============================================================

MODEL_NAME = "facebook/nllb-200-distilled-600M"
MAX_TEXT_CHARACTERS = 2000
MAX_INPUT_LENGTH = 512
MAX_NEW_TOKENS = 512
ALLOWED_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]

# The browser gets its language options from this single authoritative mapping.
SUPPORTED_LANGUAGES = {
    "English": "eng_Latn",
    "Marathi": "mar_Deva",
    "Hindi": "hin_Deva",
    "Bengali": "ben_Beng",
    "Gujarati": "guj_Gujr",
    "Kannada": "kan_Knda",
    "Malayalam": "mal_Mlym",
    "Punjabi": "pan_Guru",
    "Tamil": "tam_Taml",
    "Telugu": "tel_Telu",
    "French": "fra_Latn",
    "German": "deu_Latn",
    "Spanish": "spa_Latn",
    "Italian": "ita_Latn",
    "Portuguese": "por_Latn",
    "Russian": "rus_Cyrl",
    "Ukrainian": "ukr_Cyrl",
    "Arabic": "arb_Arab",
    "Hebrew": "heb_Hebr",
    "Persian": "pes_Arab",
    "Chinese": "zho_Hans",
    "Japanese": "jpn_Jpan",
    "Korean": "kor_Hang",
    "Turkish": "tur_Latn",
    "Dutch": "nld_Latn",
    "Polish": "pol_Latn",
    "Greek": "ell_Grek",
    "Swedish": "swe_Latn",
    "Danish": "dan_Latn",
    "Finnish": "fin_Latn",
    "Czech": "ces_Latn",
}

logger = logging.getLogger("uvicorn.error")
# Heavy dependencies are imported by the background loader. The API can still
# explain installation/loading failures and serve language choices immediately.
torch = None
DEVICE = None
tokenizer = None
translation_model = None
model_status = "loading"
model_message = "The translation model is loading. Please try again shortly."
inference_lock = Lock()


# ============================================================
# NLLB model loading and translation
# ============================================================

def get_language_token_id(model_tokenizer, language_code: str) -> int:
    """Verify both the language/script format and the actual tokenizer token."""
    if not re.fullmatch(r"[a-z]{3}_[A-Z][a-z]{3}", language_code):
        raise ValueError(f"Invalid NLLB language code: {language_code}")

    language_token_id = model_tokenizer.convert_tokens_to_ids(language_code)
    if (
        language_token_id is None
        or language_token_id == model_tokenizer.unk_token_id
        or model_tokenizer.convert_ids_to_tokens(language_token_id) != language_code
    ):
        raise ValueError(f"The tokenizer does not support {language_code}")
    return language_token_id


def release_unused_memory() -> None:
    """Run after an exception handler so its traceback no longer owns tensors."""
    gc.collect()
    if torch is not None and DEVICE is not None and DEVICE.type == "cuda":
        try:
            torch.cuda.empty_cache()
        except RuntimeError:
            # Preserve the original, friendly error even if the CUDA context failed.
            logger.exception("Unable to release the unused CUDA memory cache")


def is_memory_error(exception: Exception) -> bool:
    return isinstance(exception, MemoryError) or (
        torch is not None and isinstance(exception, torch.cuda.OutOfMemoryError)
    )


def load_translation_model() -> None:
    """Download once, then use Hugging Face's local cache on subsequent starts."""
    global torch, DEVICE, tokenizer, translation_model, model_status, model_message

    loaded_model = None
    loaded_tokenizer = None
    try:
        import torch
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

        DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        model_dtype = torch.float16 if DEVICE.type == "cuda" else torch.float32
        logger.info("Loading %s on %s", MODEL_NAME, DEVICE)
        # The slow tokenizer uses SentencePiece directly for multilingual subwords.
        loaded_tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, use_fast=False)
        for language_code in SUPPORTED_LANGUAGES.values():
            get_language_token_id(loaded_tokenizer, language_code)

        # These are pretrained weights: this project performs inference, not training.
        # Half precision reduces GPU memory use; CPU inference uses full precision.
        loaded_model = AutoModelForSeq2SeqLM.from_pretrained(
            MODEL_NAME,
            dtype=model_dtype,
        )
        loaded_model.to(DEVICE)
        loaded_model.eval()

        # Publish ready only after both objects have been completely initialized.
        tokenizer = loaded_tokenizer
        translation_model = loaded_model
        model_message = "The translation model is ready."
        model_status = "ready"
        logger.info("Translation model is ready on %s", DEVICE)
    except Exception as exception:
        if is_memory_error(exception):
            logger.exception("Memory was exhausted while loading NLLB")
            model_message = (
                "There is not enough memory to load the translation model. "
                "Close other applications and restart the backend."
            )
        else:
            logger.exception("Unable to load the NLLB model")
            model_message = (
                "The translation model could not be loaded. Check the backend "
                "logs, installed dependencies, available memory, and the "
                "first-download internet connection, then restart the backend."
            )
        model_status = "error"

    if model_status == "error":
        # A failed .to(cuda) can leave a partially moved model holding GPU memory.
        loaded_model = None
        loaded_tokenizer = None
        release_unused_memory()


def translate_text(input_text: str, source_code: str, target_code: str) -> str:
    """Tokenize, generate target tokens autoregressively, and decode them."""
    # src_lang is mutable, so the route holds inference_lock around this whole flow.
    get_language_token_id(tokenizer, source_code)
    target_language_token_id = get_language_token_id(tokenizer, target_code)
    tokenizer.src_lang = source_code

    # Tokenization converts text into multilingual SentencePiece subword IDs.
    # Never silently drop input: the model was trained on <=512-token sequences.
    model_inputs = tokenizer(input_text, return_tensors="pt", truncation=False)
    input_token_count = model_inputs["input_ids"].shape[-1]
    if input_token_count > MAX_INPUT_LENGTH:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Text is too long for the model",
                "message": (
                    f"This text uses {input_token_count} tokens. Please shorten it "
                    f"to {MAX_INPUT_LENGTH} tokens or fewer and try again."
                ),
            },
        )
    model_inputs = model_inputs.to(DEVICE)

    # The Transformer encoder uses attention to represent the source context.
    # Its decoder generates a translation one token at a time (autoregression).
    # forced_bos_token_id starts the decoder in the requested target language.
    # no_grad avoids building a training gradient graph during inference.
    with torch.no_grad():
        generated_tokens = translation_model.generate(
            **model_inputs,
            forced_bos_token_id=target_language_token_id,
            max_new_tokens=MAX_NEW_TOKENS,
            do_sample=False,
            num_beams=1,
            # Detect budget exhaustion instead of returning an incomplete sentence.
            forced_eos_token_id=None,
        )

    if generated_tokens[0, -1].item() != tokenizer.eos_token_id:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Translation is too long",
                "message": "Please translate a shorter passage so the full result can fit.",
            },
        )

    translation_result = tokenizer.batch_decode(
        generated_tokens, skip_special_tokens=True
    )[0].strip()
    if not translation_result:
        raise RuntimeError("NLLB returned an empty translation")
    return translation_result


# ============================================================
# API schemas, lifecycle, and validation
# ============================================================

class TranslationRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    text: str = Field(min_length=1, max_length=MAX_TEXT_CHARACTERS)
    source_language: str = Field(min_length=1, max_length=50)
    target_language: str = Field(min_length=1, max_length=50)


class TranslationResponse(BaseModel):
    translation: str
    source_language: str
    target_language: str


@asynccontextmanager
async def lifespan(application: FastAPI):
    # Keep /languages and model status responsive during the initial model download.
    model_loader = Thread(target=load_translation_model, daemon=True)
    model_loader.start()
    yield


app = FastAPI(
    title="AI-Powered Translation Studio API",
    description="Local pretrained NLLB-200 translation for an academic NLP project.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.exception_handler(RequestValidationError)
async def handle_invalid_request(request: Request, exception: RequestValidationError):
    """Use a consistent error shape without reflecting submitted text or internals."""
    validation_errors = exception.errors()
    first_error = validation_errors[0] if validation_errors else {}
    field_name = str(first_error.get("loc", ["request"])[-1])
    error_type = first_error.get("type", "")

    if field_name == "text" and error_type == "string_too_long":
        message = f"Text must contain at most {MAX_TEXT_CHARACTERS} characters."
    elif field_name == "text" and error_type == "string_too_short":
        message = "Please enter some text to translate."
    else:
        message = (
            "Send a JSON object with text, source_language, and target_language "
            "as non-empty strings, with no additional fields."
        )

    return JSONResponse(
        status_code=400,
        content={"detail": {"error": "Invalid request", "message": message}},
    )


def validate_language_pair(source_language: str, target_language: str) -> None:
    for language_name in (source_language, target_language):
        if language_name not in SUPPORTED_LANGUAGES:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "Unsupported language",
                    "message": f"'{language_name}' is not supported.",
                },
            )
    if source_language == target_language:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Invalid language pair",
                "message": "Source and target languages must be different.",
            },
        )


# ============================================================
# API routes
# ============================================================

@app.get("/")
def get_api_information():
    return {
        "message": "AI-Powered Translation Studio API",
        "model": MODEL_NAME,
        "model_status": model_status,
        "model_message": model_message,
        "device": DEVICE.type if DEVICE is not None else "pending",
        "max_text_characters": MAX_TEXT_CHARACTERS,
        "max_input_tokens": MAX_INPUT_LENGTH,
    }


@app.get("/languages")
def get_supported_languages():
    return {
        "languages": [
            {"name": language_name, "code": language_code}
            for language_name, language_code in SUPPORTED_LANGUAGES.items()
        ]
    }


@app.post("/translate", response_model=TranslationResponse)
def translate(translation_request: TranslationRequest):
    input_text = translation_request.text.strip()
    if not input_text:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Empty text",
                "message": "Please enter some text to translate.",
            },
        )
    validate_language_pair(
        translation_request.source_language, translation_request.target_language
    )
    if model_status != "ready" or tokenizer is None or translation_model is None:
        raise HTTPException(
            status_code=503,
            detail={"error": "Model unavailable", "message": model_message},
            headers={"Retry-After": "10"},
        )

    # One inference at a time protects tokenizer.src_lang and limits memory use.
    # Reject concurrent work promptly rather than queueing expensive GPU requests.
    if not inference_lock.acquire(blocking=False):
        raise HTTPException(
            status_code=503,
            detail={
                "error": "Translation server is busy",
                "message": "Another translation is running. Please try again shortly.",
            },
            headers={"Retry-After": "3"},
        )

    memory_exhausted = False
    try:
        translation_result = translate_text(
            input_text,
            SUPPORTED_LANGUAGES[translation_request.source_language],
            SUPPORTED_LANGUAGES[translation_request.target_language],
        )
        return TranslationResponse(
            translation=translation_result,
            source_language=translation_request.source_language,
            target_language=translation_request.target_language,
        )
    except HTTPException:
        raise
    except Exception as exception:
        memory_exhausted = is_memory_error(exception)
        if memory_exhausted:
            logger.exception("Memory was exhausted during translation")
            translation_error = HTTPException(
                status_code=503,
                detail={
                    "error": "Insufficient memory",
                    "message": (
                        "There is not enough memory to translate this text. "
                        "Try a shorter passage or close other applications."
                    ),
                },
            )
        else:
            logger.exception("NLLB translation failed")
            translation_error = HTTPException(
                status_code=500,
                detail={
                    "error": "Translation failed",
                    "message": "Translation failed. Please try again.",
                },
            )
    finally:
        if memory_exhausted:
            release_unused_memory()
        inference_lock.release()

    # Raising outside the handler avoids retaining the model's failure traceback.
    raise translation_error
