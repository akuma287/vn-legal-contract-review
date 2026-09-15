"""Preliminary Vietnamese contract screening. No legal verdicts."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

RULES_DIR = Path(__file__).with_name("rules")
DEFAULT_RULE_PACK = RULES_DIR / "labor_code_2019.json"


def load_rule_pack(path: str | Path = DEFAULT_RULE_PACK) -> dict[str, Any]:
    """Load and minimally validate one local legal rule pack."""
    with Path(path).open(encoding="utf-8") as handle:
        rule_pack = json.load(handle)

    required = {"rule_pack_version", "source"}
    missing = required.difference(rule_pack)
    if missing:
        raise ValueError(f"Rule pack thiếu trường: {', '.join(sorted(missing))}")
    if not any(key in rule_pack for key in ("required_content_rules", "presence_review_rules", "duration_rule")):
        raise ValueError("Rule pack không có rule nào.")
    return rule_pack


def load_rule_packs(rules_dir: Path = RULES_DIR) -> list[dict[str, Any]]:
    """Load all curated local rule packs; base contract pack stays primary."""
    first = {"base_contract.json": 0, "labor_code_2019.json": 1}
    paths = sorted(rules_dir.glob("*.json"), key=lambda path: (first.get(path.name, 2), path.name))
    return [load_rule_pack(path) for path in paths]


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

    rule_packs = [rule_pack] if rule_pack else load_rule_packs()
    normalized = text.casefold()
    findings: list[dict[str, Any]] = []

    for pack in rule_packs:
        applies_when = pack.get("applies_when", [])
        if applies_when and not any(keyword.casefold() in normalized for keyword in applies_when):
            continue

        for rule in pack.get("required_content_rules", []):
            if not any(keyword.casefold() in normalized for keyword in rule["keywords"]):
                findings.append(
                    _finding(
                        rule,
                        "Không tìm thấy dấu hiệu rõ ràng của nội dung này trong văn bản đã trích xuất.",
                    )
                )

        for rule in pack.get("presence_review_rules", []):
            has_trigger = any(keyword.casefold() in normalized for keyword in rule["triggers"])
            has_required_detail = any(
                keyword.casefold() in normalized for keyword in rule["required_keywords"]
            )
            if has_trigger and not has_required_detail:
                findings.append(
                    _finding(
                        rule,
                        "Có dấu hiệu điều khoản thuộc nhóm này nhưng chưa thấy chi tiết cần đối chiếu.",
                    )
                )

        duration_rule = pack.get("duration_rule")
        duration_match = re.search(r"(?:thời hạn[^\n,.]{0,60}?|xác định thời hạn\s+)(\d{1,3})\s*tháng", normalized)
        if duration_rule and duration_match and int(duration_match.group(1)) > 36:
            months = duration_match.group(1)
            findings.append(
                _finding(
                    duration_rule,
                    f"Phát hiện thời hạn {months} tháng. Cần kiểm tra loại hợp đồng và ngoại lệ áp dụng.",
                )
            )

    primary_pack = rule_packs[0]
    return {
        "disclaimer": primary_pack.get(
            "disclaimer",
            "Kết quả là sàng lọc sơ bộ dựa trên dấu hiệu văn bản. Không phải tư vấn pháp lý.",
        ),
        "rule_pack_version": ", ".join(pack["rule_pack_version"] for pack in rule_packs),
        "source": primary_pack["source"],
        "sources": [pack["source"] for pack in rule_packs],
        "findings": findings,
    }


if __name__ == "__main__":
    sample = "Hợp đồng lao động. Công việc: Kế toán. Thời hạn: 48 tháng."
    assert any(item["id"] == "BLLD2019-ART20-FIXED-TERM" for item in screen_text(sample)["findings"])
    print("screening self-check passed")
