from decimal import ROUND_HALF_UP, Decimal

TWO = Decimal("0.01")
THREE = Decimal("0.001")
FOUR = Decimal("0.0001")


def d(value) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


def money(value) -> Decimal:
    return d(value).quantize(TWO, rounding=ROUND_HALF_UP)


def qty(value) -> Decimal:
    return d(value).quantize(THREE, rounding=ROUND_HALF_UP)


def rate4(value) -> Decimal:
    return d(value).quantize(FOUR, rounding=ROUND_HALF_UP)
