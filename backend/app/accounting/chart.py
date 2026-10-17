"""System chart of accounts. Party/staff/money accounts are created on demand under group accounts."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.accounting.models import Account


class Code:
    CASH_BANK = "1000"
    INVENTORY = "1100"
    RECEIVABLES = "1200"
    PAYABLES = "2000"
    OUTPUT_TAX = "2100"
    STAFF_PAYABLE = "2200"
    OPENING_EQUITY = "3000"
    SALES = "4000"
    FREIGHT = "4100"
    RENT = "4200"
    COGS = "5000"
    DIESEL = "5100"
    REPAIR = "5110"
    TYRE = "5120"
    INSURANCE = "5130"
    TOLL = "5140"
    OFFICE = "5150"
    MISC = "5190"
    SALARY = "5200"
    LABOUR_WAGES = "5210"
    STOCK_LOSS = "5300"


SYSTEM_ACCOUNTS: list[tuple[str, str, str]] = [
    (Code.CASH_BANK, "Cash & Bank", "asset"),
    (Code.INVENTORY, "Inventory - Material", "asset"),
    (Code.RECEIVABLES, "Customers (Receivable)", "asset"),
    (Code.PAYABLES, "Suppliers (Payable)", "liability"),
    (Code.OUTPUT_TAX, "Output Tax Payable", "liability"),
    (Code.STAFF_PAYABLE, "Staff & Labour (Payable)", "liability"),
    (Code.OPENING_EQUITY, "Opening Balance Equity", "equity"),
    (Code.SALES, "Sales - Material", "income"),
    (Code.FREIGHT, "Income - Freight", "income"),
    (Code.RENT, "Income - Equipment Rent", "income"),
    (Code.COGS, "Cost of Goods Sold", "expense"),
    (Code.DIESEL, "Expense - Diesel", "expense"),
    (Code.REPAIR, "Expense - Repair", "expense"),
    (Code.TYRE, "Expense - Tyre", "expense"),
    (Code.INSURANCE, "Expense - Insurance", "expense"),
    (Code.TOLL, "Expense - Toll", "expense"),
    (Code.OFFICE, "Expense - Office", "expense"),
    (Code.MISC, "Expense - Miscellaneous", "expense"),
    (Code.SALARY, "Expense - Salary", "expense"),
    (Code.LABOUR_WAGES, "Expense - Labour Wages", "expense"),
    (Code.STOCK_LOSS, "Expense - Stock Loss", "expense"),
]

EXPENSE_CATEGORY_CODE = {
    "diesel": Code.DIESEL,
    "repair": Code.REPAIR,
    "tyre": Code.TYRE,
    "insurance": Code.INSURANCE,
    "toll": Code.TOLL,
    "office": Code.OFFICE,
    "misc": Code.MISC,
}


def ensure_chart(db: Session) -> None:
    """Idempotently create any missing system accounts."""
    existing = {c for (c,) in db.execute(select(Account.code))}
    for code, name, type_ in SYSTEM_ACCOUNTS:
        if code not in existing:
            db.add(Account(code=code, name=name, type=type_, is_system=True))
    db.flush()


class Chart:
    """code -> account id lookup, cached for the lifetime of one unit of work."""

    def __init__(self, db: Session):
        self._db = db
        self._cache: dict[str, int] = {}

    def id(self, code: str) -> int:
        if code not in self._cache:
            account_id = self._db.scalar(select(Account.id).where(Account.code == code))
            if account_id is None:
                ensure_chart(self._db)
                account_id = self._db.scalar(select(Account.id).where(Account.code == code))
            self._cache[code] = account_id
        return self._cache[code]


def create_sub_account(db: Session, *, prefix: str, ref_id: int, name: str, parent_code: str, type_: str) -> Account:
    parent = db.scalar(select(Account).where(Account.code == parent_code))
    account = Account(
        code=f"{prefix}{ref_id:05d}",
        name=name,
        type=type_,
        is_system=False,
        parent_id=parent.id if parent else None,
    )
    db.add(account)
    db.flush()
    return account
