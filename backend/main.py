from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import database as database
import ai_service as ai_service
import re

app = FastAPI(title="SpendWise AI API")
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB

# Позволяваме на Frontend-а на колежката ти да се свързва с Backend-а (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

database.init_db()

class ExpenseCreate(BaseModel):
    title: str
    amount: float
    date: str  # формат '2026-11-16'
    category: Optional[str] = None  # Ако не е подадена, AI ще я определи сам!

class BudgetCreate(BaseModel):
    month: str  # формат '2026-11'
    limit_amount: float


@app.get("/")
def home():
    return {"message": "SpendWise AI Backend работи успешно!"}

@app.get("/expenses")
def read_expenses():
    """Връща всички разходи от базата данни."""
    return database.get_all_expenses()

@app.post("/expenses")
def create_expense(expense: ExpenseCreate):
    """Приема ръчен разход. Ако няма избрана категория, AI я определя автоматично."""
    category = expense.category
    if not category or category.strip() == "":
        category = ai_service.categorize_expense(expense.title)
        
    new_id = database.add_expense(
        title=expense.title,
        amount=expense.amount,
        category=category,
        date=expense.date,
        source="manual"
    )
    return {
        "status": "success",
        "id": new_id,
        "category": category
    }

@app.post("/scan-receipt")
async def scan_receipt(file: UploadFile = File(...)):
    """Приема снимка на касова бележка, валидира я, извлича данните с AI/OCR и записва разхода."""
    # 1. Проверка на типа на файла
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=400,
            detail="Неподдържан формат. Качи изображение (JPG, PNG, WEBP)."
        )

    # 2. Еднократно четене на файла и проверка за празен / твърде голям файл
    contents = await file.read()
    if not contents:
        raise HTTPException(
            status_code=400,
            detail="Каченият файл е празен."
        )

    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="Файлът е твърде голям. Максималният позволен размер е 5 MB."
        )

    # 3. AI/OCR анализ с ясни HTTP грешки
    try:
        receipt_data = ai_service.analyze_receipt(contents)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Неочаквана грешка при сканиране: {str(e)}")

    # 4. Безопасен запис в базата с резервни стойности по подразбиране
    try:
        new_id = database.add_expense(
            title=receipt_data.get("title", "Неизвестен магазин"),
            amount=float(receipt_data.get("amount", 0.0)),
            category=receipt_data.get("category", "Други"),
            date=receipt_data.get("date", "2026-11-16"),
            source="receipt"
        )
        return {
            "status": "success",
            "id": new_id,
            "extracted_data": receipt_data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Грешка при запис в базата: {str(e)}")

@app.post("/budget")
def update_budget(budget: BudgetCreate):
    """Задава месечен бюджет."""
    database.set_budget(budget.month, budget.limit_amount)
    return database.get_budget_status(budget.month)

@app.get("/budget/{month}")
def read_budget_status(month: str):
    """Връща статуса на бюджета и статистиката по категории за графиките."""
    status = database.get_budget_status(month)
    categories = database.get_category_stats(month)
    return {
        "budget": status,
        "categories": categories
    }

@app.delete("/expenses/{expense_id}")
def delete_expense(expense_id: int):
    deleted = database.delete_expense(expense_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Expense not found")
    return {"status": "deleted", "id": expense_id}

@app.get("/analytics/periods")
def get_analytics_by_period(group_by: str = "day", month: Optional[str] = None):
    """Връща разпределение на разходите по дни, седмици или месеци."""
    if group_by not in ("day", "week", "month"):
        raise HTTPException(
            status_code=400,
            detail="Невалиден период. Използвай 'day', 'week' или 'month'."
        )
    if month and not re.match(r"^\d{4}-(0[1-9]|1[0-2])$", month):
        raise HTTPException(
            status_code=400,
            detail="Невалиден формат за месец. Използвай ГГГГ-ММ (напр. 2026-11)."
        )

    periods = database.get_period_stats(group_by=group_by, month=month)
    total_amount = round(sum(p["total"] for p in periods), 2)

    return {
        "group_by": group_by,
        "month": month,
        "total_amount": total_amount,
        "periods": periods
    }


@app.get("/insights/{month}")
def get_spending_insights(month: str):
    """Връща статистики за навиците и AI съвети за конкретен месец."""
    if not re.match(r"^\d{4}-(0[1-9]|1[0-2])$", month):
        raise HTTPException(
            status_code=400,
            detail="Невалиден формат за месец. Използвай ГГГГ-ММ (напр. 2026-11)."
        )

    habits_data = database.get_month_habits_data(month)
    ai_insights = ai_service.generate_spending_insights(habits_data)

    return {
        "stats": habits_data,
        "ai_insights": ai_insights
    }