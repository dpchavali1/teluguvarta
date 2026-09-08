"""Source adapter contract (§6.3) — fetch -> normalize -> validate -> emit.

Not wired into a scheduled worker yet (that's T08); this package only proves
the contract works end-to-end against real (fixture-recorded) source data.
"""
