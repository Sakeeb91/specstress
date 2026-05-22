from .sort.case import CASE as _SORT
from .withdraw.case import CASE as _WITHDRAW
from .sanitize.case import CASE as _SANITIZE


REGISTRY = {
    "sort": _SORT,
    "withdraw": _WITHDRAW,
    "sanitize": _SANITIZE,
}
