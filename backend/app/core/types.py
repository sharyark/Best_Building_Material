"""Validated input types shared by the schemas (the same rules are mirrored in the frontend Zod schemas)."""

from decimal import Decimal
from typing import Annotated

from pydantic import Field

MoneyIn = Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=2)]
PositiveMoney = Annotated[Decimal, Field(gt=0, max_digits=14, decimal_places=2)]
PositiveQty = Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=3)]
QtyIn = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=3)]
