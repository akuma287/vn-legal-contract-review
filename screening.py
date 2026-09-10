"""Preliminary Vietnamese labor-contract screening. No legal verdicts."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

DEFAULT_RULE_PACK = Path(__file__).with_name("rules") / "labor_code_2019.json"


def load_rule_pack(path: str | Path = DEFAULT_RULE_PACK) -> dict[str, Any]:
    """Load and minimally validate the versioned, local legal rule pack."""
    with Path(path).open(encoding="utf-8") as handle:
        rule_pack = json.load(handle)

    required = {"rule_pack_version", "source", "disclaimer", "required_content_rules", "duration_rule"}
    missing = required.difference(rule_pack)
    if missing:
        raise ValueError(f"Rule pack thiếu trường: {', '.join(sorted(missing))}")
    return rule_pack


def _finding(rule: dict[str, Any], evidence: str) -> dict[str, Any]:
    return {
        "id": rule["id"],
        "severity": "review",
        "title": rule["title"],
        "evidence": evidence,
        "legal_basis": rule["legal_basis"],
        "missing_facts": rule.get("missing_facts", []),
        "recommendation": rule["recommendation"],
    }


def screen_text(text: str, rule_pack: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return evidence-oriented review findings for contract text.

    Keyword matches are intentionally weak signals. Missing matches require review,
    not a conclusion that a contract violates or complies with law.
    """
    if not text or not text.strip():
        raise ValueError("Không có nội dung hợp đồng để rà soát.")

    rule_pack = rule_pack or load_rule_pack()
    normalized = text.casefold()
    findings: list[dict[str, Any]] = []

    for rule in rule_pack["required_content_rules"]:
        if not any(keyword.casefold() in normalized for keyword in rule["keywords"]):
            findings.append(
                _finding(
                    rule,
                    "Không tìm thấy dấu hiệu rõ ràng của nội dung này trong văn bản đã trích xuất.",
                )
            )

    duration_match = re.search(r"(?:thời hạn[^\n,.]{0,60}?|xác định thời hạn\s+)(\d{1,3})\s*tháng", normalized)
    if duration_match and int(duration_match.group(1)) > 36:
        months = duration_match.group(1)
        findings.append(
            _finding(
                rule_pack["duration_rule"],
                f"Phát hiện thời hạn {months} tháng. Cần kiểm tra loại hợp đồng và ngoại lệ áp dụng.",
            )
        )

    return {
        "disclaimer": rule_pack["disclaimer"],
        "rule_pack_version": rule_pack["rule_pack_version"],
        "source": rule_pack["source"],
        "findings": findings,
    }


if __name__ == "__main__":
    sample = "Hợp đồng lao động. Công việc: Kế toán. Thời hạn: 48 tháng."
    assert any(item["id"] == "BLLD2019-ART20-FIXED-TERM" for item in screen_text(sample)["findings"])
    print("screening self-check passed")
