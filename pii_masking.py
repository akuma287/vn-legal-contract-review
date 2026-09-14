import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class _Pattern:
    entity: str
    regex: str
    score: float


# Patterns adapted from be-pii-masking (Vietnamese PII regexes for Presidio).
_PATTERNS: tuple[_Pattern, ...] = (
    _Pattern("TAX_ID", r"\b[0-9]{10}-[0-9]{3}\b", 0.9),
    _Pattern(
        "TAX_ID",
        r"(?i)\b(?:mst|mã\s*số\s*thuế|ma\s*so\s*thue|mã\s*thuế|ma\s*thue|tax\s*code|tax\s*id|tax|vat|đkkd|dkkd|msdn)[\s:._-]{0,10}([0-9]{10}(?:-[0-9]{3}|[0-9]{3})?)\b",
        1.0,
    ),
    _Pattern("VN_CCCD", r"\b(?:[0-9]{3}[0-7][0-9]{8})\b", 1.0),
    _Pattern(
        "PHONE_NUMBER",
        r"(?<!\d)(?:(?:\+84|84|0)[\s.-]*(?:[35789](?:[\s.-]*[0-9]){8}|2(?:[\s.-]*[0-9]){9}))(?!\d)",
        1.0,
    ),
    _Pattern("EMAIL_ADDRESS", r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", 1.0),
)


@dataclass
class PiiMaskingResult:
    masked_text: str
    findings: dict[str, int] = field(default_factory=dict)


def mask_pii(text: str) -> PiiMaskingResult:
    """Replace Vietnamese PII with numbered placeholders before any external send."""
    spans: list[tuple[int, int, str]] = []
    counters: dict[str, int] = {}
    for pattern in _PATTERNS:
        compiled = re.compile(pattern.regex)
        counter = counters.get(pattern.entity, 0)
        for match in compiled.finditer(text):
            if match.lastindex:
                value_start, value_end = match.start(1), match.end(1)
            else:
                value_start, value_end = match.span()
            overlapping = any(
                value_start < end and start < value_end for start, end, _ in spans
            )
            if overlapping:
                continue
            counter += 1
            counters[pattern.entity] = counter
            spans.append((value_start, value_end, f"{{{{{pattern.entity}_{counter}}}}}"))
    if not spans:
        return PiiMaskingResult(text, {})
    spans.sort()
    masked_parts: list[str] = []
    cursor = 0
    for start, end, placeholder in spans:
        masked_parts.append(text[cursor:start])
        masked_parts.append(placeholder)
        cursor = end
    masked_parts.append(text[cursor:])
    return PiiMaskingResult("".join(masked_parts), dict(counters))


if __name__ == "__main__":
    demo = (
        "Anh A, SĐT 0901234567, email nguyenvana@gmail.com, "
        "CCCD 079203001234, MST 0312345678-001, địa chỉ 12 Nguyễn Huệ, Q1, TP.HCM."
    )
    result = mask_pii(demo)
    print(result.masked_text)
    print(result.findings)
    assert "0901234567" not in result.masked_text
    assert "nguyenvana@gmail.com" not in result.masked_text
    assert "079203001234" not in result.masked_text
    assert "0312345678-001" not in result.masked_text
    # ponytail: no person-name masking — needs an NER model (DeBERTa), out of MVP scope.
    print("pii-masking self-check passed")
