from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import backend.database as database
import backend.ai_service as ai_service

app = FastAPI(title="SpendWise AI API")

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
    """Приема снимка на касова бележка, извлича данните с AI/OCR и записва разхода."""
    try:
        image_bytes = await file.read()
        receipt_data = ai_service.analyze_receipt(image_bytes)
        
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
        raise HTTPException(status_code=500, detail=f"Грешка при сканиране: {str(e)}")

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