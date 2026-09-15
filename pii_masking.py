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
    _Pattern(
        "BANK_ACCOUNT",
        r"(?i)\b(?:số\s*tài\s*khoản|stk|account\s*(?:no|number)?|bank\s*account)[\s:._-]{0,10}([0-9][0-9\s.-]{7,18}[0-9])\b",
        1.0,
    ),
    _Pattern(
        "VN_CCCD",
        r"(?<!\w)0\d{2}(?:[01][4-9][0-9]|[23](?:0[0-9]|1[0-2]))\d{6}(?!\w)",
        1.0,
    ),
    _Pattern(
        "PHONE_NUMBER",
        r"(?<!\w)(?:(?:\+84|84|0)(?:3|5|7|8|9)[0-9]{8}|(?:\+8\.4|8\.4|0)(?:3|5|7|8|9)[0-9]{8})(?!\w)",
        1.0,
    ),
    _Pattern(
        "EMAIL_ADDRESS",
        r"(?i)(?<![\w.\-])([\w.\-]{0,25}@(?:(?:(?:outlook|tuta|tutanota|juno|lycos|mailfence|netcourrier|qq|yahoo|gmail|icloud|me|mac|hotmail|live|msn|aol|mail|zoho|rediffmail|hushmail|gmx|protonmail|yandex|mail2world)\.com)|proton\.me|mailbox\.org|posteo\.de|(?:[\w\-]+\.)?edu\.vn))",
        1.0,
    ),
    _Pattern(
        "ADDRESS",
        r"(?i)\b(?:địa\s*chỉ|dia\s*chi|address|trụ\s*sở|tru\s*so|nơi\s*cư\s*trú)[\s:._-]{0,10}([^\n.;]{8,160}(?:tp\.?\s*hcm|hồ\s*chí\s*minh|ha\s*noi|hà\s*nội|đà\s*nẵng|da\s*nang|tỉnh|thành\s*phố|quận|huyện|phường|xã)[^\n.;]*)",
        1.0,
    ),
    # ponytail: regex names only when contract labels identify parties; use NER if unlabeled names must be masked.
    _Pattern(
        "PERSON_NAME",
        r"(?i)\b(?:bên\s*[ab]|người\s*lao\s*động|người\s*đại\s*diện|đại\s*diện|ông|bà|anh|chị)[\s:._-]{0,10}([A-ZÀ-ỸĐ][a-zà-ỹđ]+(?:\s+(?:[A-ZÀ-ỸĐ][a-zà-ỹđ]+|[A-ZÀ-ỸĐ])){1,4})\b",
        0.8,
    ),
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
    # ponytail: unlabeled person-name masking needs an NER model, out of MVP scope.
    print("pii-masking self-check passed")
