"""Business event -> Dr/Cr mapping (ARCHITECTURE.md section 5). Pure functions, no DB writes.

Adding a feature means adding a rule here; reports never change.
"""

from decimal import Decimal

from app.accounting.chart import EXPENSE_CATEGORY_CODE, Chart, Code
from app.accounting.posting import Line, cr, dr


def purchase(chart: Chart, supplier_account: int, total: Decimal) -> list[Line]:
    return [dr(chart.id(Code.INVENTORY), total), cr(supplier_account, total)]


def delivery(
    chart: Chart,
    customer_account: int,
    *,
    sale: Decimal,
    freight: Decimal,
    cost: Decimal,
    vehicle_id: int | None,
) -> list[Line]:
    return [
        dr(customer_account, sale + freight),
        cr(chart.id(Code.SALES), sale),
        cr(chart.id(Code.FREIGHT), freight, vehicle_id),
        dr(chart.id(Code.COGS), cost),
        cr(chart.id(Code.INVENTORY), cost),
    ]


def rental(chart: Chart, customer_account: int, amount: Decimal, vehicle_id: int) -> list[Line]:
    return [dr(customer_account, amount), cr(chart.id(Code.RENT), amount, vehicle_id)]


def payment_in(money_account: int, counterparty_account: int, amount: Decimal) -> list[Line]:
    return [dr(money_account, amount), cr(counterparty_account, amount)]


def payment_out(money_account: int, counterparty_account: int, amount: Decimal) -> list[Line]:
    return [dr(counterparty_account, amount), cr(money_account, amount)]


def expense(chart: Chart, category: str, amount: Decimal, vehicle_id: int | None, paid_from_account: int) -> list[Line]:
    return [
        dr(chart.id(EXPENSE_CATEGORY_CODE[category]), amount, vehicle_id),
        cr(paid_from_account, amount),
    ]


def labour_wage(chart: Chart, staff_account: int, amount: Decimal, vehicle_id: int | None) -> list[Line]:
    return [dr(chart.id(Code.LABOUR_WAGES), amount, vehicle_id), cr(staff_account, amount)]


def salary(
    chart: Chart,
    staff_account: int,
    gross: Decimal,
    deductions: Decimal,
    vehicle_id: int | None,
    *,
    expense_code: str = Code.SALARY,
) -> list[Line]:
    """Wage accrual. `gross` = 0 posts only the deduction (daily labour already accrued per day)."""
    expense = chart.id(expense_code)
    return [
        dr(expense, gross, vehicle_id),
        cr(staff_account, gross),
        # Deductions (fines, absences) reduce what we owe and what the wage cost us.
        dr(staff_account, deductions),
        cr(expense, deductions, vehicle_id),
    ]


def stock_adjustment(chart: Chart, value: Decimal) -> list[Line]:
    """value > 0: stock found (gain). value < 0: shortage / wastage (loss)."""
    amount = abs(value)
    if value < 0:
        return [dr(chart.id(Code.STOCK_LOSS), amount), cr(chart.id(Code.INVENTORY), amount)]
    return [dr(chart.id(Code.INVENTORY), amount), cr(chart.id(Code.STOCK_LOSS), amount)]


def opening_balance(chart: Chart, account_id: int, amount: Decimal, side: str) -> list[Line]:
    equity = chart.id(Code.OPENING_EQUITY)
    if side == "dr":
        return [dr(account_id, amount), cr(equity, amount)]
    return [dr(equity, amount), cr(account_id, amount)]


def opening_stock(chart: Chart, value: Decimal) -> list[Line]:
    return [dr(chart.id(Code.INVENTORY), value), cr(chart.id(Code.OPENING_EQUITY), value)]


def invoice_tax(chart: Chart, customer_account: int, tax: Decimal) -> list[Line]:
    return [dr(customer_account, tax), cr(chart.id(Code.OUTPUT_TAX), tax)]
