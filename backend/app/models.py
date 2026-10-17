"""Imports every model so `Base.metadata` is complete (used by create_all, Alembic and tests)."""

from app.accounting import models as accounting  # noqa: F401
from app.audit import models as audit  # noqa: F401
from app.core.db import Base  # noqa: F401
from app.modules.auth import models as auth  # noqa: F401
from app.modules.deliveries import models as deliveries  # noqa: F401
from app.modules.expenses import models as expenses  # noqa: F401
from app.modules.invoices import models as invoices  # noqa: F401
from app.modules.labour import models as labour  # noqa: F401
from app.modules.masters import models as masters  # noqa: F401
from app.modules.payments import models as payments  # noqa: F401
from app.modules.purchases import models as purchases  # noqa: F401
from app.modules.rentals import models as rentals  # noqa: F401
from app.modules.stock import models as stock  # noqa: F401
