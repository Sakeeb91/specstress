# Withdraw

**Function:** `withdraw(balance: int, amount: int) -> tuple[bool, int]`

**Intent:** Returns `(success, new_balance)`. The withdrawal succeeds if and only if
`amount > 0` and `amount <= balance`. On success, the returned balance equals
`balance - amount`. On failure, the returned balance equals `balance` unchanged.

**Why this demo:** Financial correctness is a classic place where weak specs (`new_balance
>= 0`) admit dangerous implementations such as silently capping negative withdrawals or
ignoring the amount entirely.
