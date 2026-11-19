import os
from dotenv import load_dotenv
import json
from google import genai
from PIL import Image
import io

load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=API_KEY)

# Списък с модели по ред на приоритет (ако първият е претоварен, пробва втория)
MODELS_TO_TRY = ["gemini-3.5-flash", "gemini-3.5-flash-lite"]

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
    """Задача 2 + 3: Извлича магазин, сума, дата и категория от снимка на касова бележка."""
    image = Image.open(io.BytesIO(image_bytes))
    
    prompt = f"""
    Ти си OCR система за четене на касови бележки. Анализирай тази касова бележка и извлечи:
    1. title: Име на магазина или търговеца (кратко и ясно, напр. "Lidl", "OMV", "Аптека Марешки").
    2. amount: Крайната обща сума за плащане като число (напр. 24.50).
    3. date: Датата от бележката във формат YYYY-MM-DD (ако не се чете ясно, използвай "2026-11-16").
    4. category: Избери най-подходящата категория ТОЧНО от този списък: {", ".join(CATEGORIES)}.

    Върни отговора САМО като валиден JSON обект с тези 4 ключа, без никакъв допълнителен текст и без markdown форматиране.
    """
    
    response = generate_with_fallback([image, prompt])
    raw_text = response.text.strip().removeprefix("```json").removesuffix("```").strip()
    return json.loads(raw_text)


if __name__ == "__main__":
    test_title = "Бензиностанция ЕКО"
    result = categorize_expense(test_title)
    print(f"Разход: {test_title} | Категория: {result}")