"""Feature 098: the {{ALLOCATION_THRESHOLD_NIS}} prompt placeholder, filled from
config.allocation_threshold_nis by both prompt paths - the Backbone's assembled
instructions and the legacy runtime constitution."""

ALLOCATION_THRESHOLD_PLACEHOLDER = "{{ALLOCATION_THRESHOLD_NIS}}"


def format_nis_amount(value: float) -> str:
    """5000 -> '5,000'; 12500 -> '12,500'; 5000.5 -> '5,000.5'."""
    if float(value).is_integer():
        return f"{int(value):,}"
    return f"{value:,.2f}".rstrip("0").rstrip(".")


def fill_allocation_threshold(content: str, threshold_nis: float) -> str:
    """Replace every placeholder with the formatted threshold. The value is the
    same on every call, so the filled text stays a byte-identical prefix and
    OpenAI's prompt caching is unaffected."""
    return content.replace(ALLOCATION_THRESHOLD_PLACEHOLDER, format_nis_amount(threshold_nis))
