"""Seller flow is intentionally removed; kept for import compatibility."""


def guide(*args, **kwargs):  # type: ignore[unused-argument]
    raise RuntimeError("Seller guidance flow has been removed; consumer mode only.")
