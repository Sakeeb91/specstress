from .sort.case import CASE as _SORT
from .withdraw.case import CASE as _WITHDRAW
from .sanitize.case import CASE as _SANITIZE
from .money.case import CASE as _MONEY
from .jwt.case import CASE as _JWT


REGISTRY = {
    "sort": _SORT,
    "withdraw": _WITHDRAW,
    "sanitize": _SANITIZE,
    "money": _MONEY,
    "jwt": _JWT,
}
