import os
import time
from google.genai import types
from dotenv import load_dotenv
import json
from google import genai
from PIL import Image, UnidentifiedImageError
import io
import hashlib

RECEIPT_CACHE = {}

load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=API_KEY)

# Списък с модели по ред на приоритет (ако първият е претоварен, пробва втория)
MODELS_TO_TRY = ["gemini-3.5-flash-lite", "gemini-3.5-flash"]

CATEGORIES = [
    "Храна и супермаркет",
    "Ресторанти и кафенета",
    "Транспорт и гориво",
    "Битови сметки и наем",
    "Забавление и свободно време",
    "Здраве и аптека",
    "Пазаруване и дрехи",
    "Други"
]

client = genai.Client(
    api_key=API_KEY,
    http_options=types.HttpOptions(timeout=25000)
)

def generate_with_fallback(contents):
    """Опитва да извика AI модела; ако сървърът е претоварен (503), пробва резервен модел."""
    last_error = None
    for model_name in MODELS_TO_TRY:
        try:
            return client.models.generate_content(
                model=model_name,
                contents=contents
            )
        except Exception as e:
            print(f"Моделът {model_name} не успя ({e}), пробваме следващия...")
            last_error = e
    raise last_error

def categorize_expense(title: str) -> str:
    """Задача 3: Определя категория само по името на разхода."""
    prompt = f"""
    Определи най-подходящата категория за следния разход: "{title}".
    Избери ТОЧНО ЕДНА категория от този списък: {", ".join(CATEGORIES)}.
    Върни само името на категорията, без никакъв друг текст.
    """
    try:
        response = generate_with_fallback(prompt)
        category = response.text.strip()
        return category if category in CATEGORIES else "Други"
    except Exception as e:
        print(f"Грешка при категоризация: {e}")
        return "Други"

def analyze_receipt(image_bytes: bytes) -> dict:
    """Извлича магазин, сума, дата и категория от снимка на касова бележка."""
    image_hash = hashlib.sha256(image_bytes).hexdigest()
    if image_hash in RECEIPT_CACHE:
        print("[OCR] Върнато от кеша за 0.01 сек.")
        return RECEIPT_CACHE[image_hash]
    
    if not API_KEY:
        raise RuntimeError("Липсва GEMINI_API_KEY в .env файла на сървъра.")

    t0 = time.time()

    # 1. Валидация + смаляване и компресия до лек JPEG (~100 KB вместо 5 MB)
    try:
        image = Image.open(io.BytesIO(image_bytes))
        image.verify()
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        image.thumbnail((1024, 1024))

        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=75, optimize=True)
        compressed_bytes = buffer.getvalue()
    except UnidentifiedImageError:
        raise ValueError("Каченият файл не е валидно изображение.")
    except Exception:
        raise ValueError("Изображението е повредено или не може да бъде прочетено.")

    image_part = types.Part.from_bytes(data=compressed_bytes, mime_type="image/jpeg")

    prompt = (
        f'Извлечи от касовата бележка JSON с ключове: '
        f'"title" (магазин), "amount" (крайна сума като число), '
        f'"date" (YYYY-MM-DD, по подразбиране "2026-11-25"), '
        f'"category" (ТОЧНО една от: {", ".join(CATEGORIES)}).'
    )

    # 2. Бърза заявка в директен JSON режим
    last_error = None
    for model_name in MODELS_TO_TRY:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=[image_part, prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1,
                ),
            )
            result = json.loads(response.text)
            RECEIPT_CACHE[image_hash] = result
            print(f"[OCR] Модел {model_name} отговори за {time.time() - t0:.2f} сек.")
            return result
        except Exception as e:
            last_error = str(e)
            print(f"[OCR] {model_name} не успя за {time.time() - t0:.2f} сек.: {e}")
            continue

    error_text = (last_error or "").lower()
    if "api_key" in error_text or "401" in error_text or "403" in error_text:
        raise RuntimeError("Невалиден или блокиран API ключ за Gemini.")
    if any(code in error_text for code in ("503", "504", "unavailable", "deadline", "429")):
        raise RuntimeError("AI услугата е временно претоварена. Опитай отново след малко.")
    raise ValueError("Не успяхме да разчетем касовата бележка. Опитай с по-ясна снимка.")
if __name__ == "__main__":
    test_title = "Бензиностанция ЕКО"
    result = categorize_expense(test_title)
    print(f"Разход: {test_title} | Категория: {result}")