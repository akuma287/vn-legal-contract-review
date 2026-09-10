# Vietnamese Labor Contract Screening MVP Design

## Goal

Build a private local web app for preliminary screening of Vietnamese labor-contract text. It must surface missing/ambiguous contract information, show exact source metadata for every rule, and avoid legal conclusions.

## Scope

### Included

- Local browser UI at `http://127.0.0.1:8000`.
- Upload UTF-8 `.txt` or text-based `.pdf`, maximum 2 MiB.
- Extract text in memory only; no database, cache, telemetry, or saved uploads.
- Detect basic presence of fields required by Article 21 of Labor Code 45/2019/QH14.
- Detect a stated definite term exceeding 36 months under Article 20 when duration is expressed as an integer number of months.
- Return structured findings, source citation, missing facts, and a preliminary-screening disclaimer.
- Optional AI review through the user-selected OpenAI-compatible provider. It must require an explicit upload-time consent checkbox before contract text is sent externally.
- One runnable test module using `unittest`.

### Excluded

- DOCX/OCR, RAG/vector DB, embeddings, authentication, report export, retention, external source fetching, and legal determination. Optional AI review is limited to the configured provider with upload-time consent.
- Any claim that a contract is valid, invalid, compliant, legal, illegal, complete, or enforceable.

## Architecture

`app.py` uses `http.server` only. `screening.py` owns pure text analysis and consumes the versioned `rules/labor_code_2019.json` rule pack. The browser only posts a multipart file; request handling parses, screens, and renders an escaped HTML report. Uploaded bytes and extracted text exist only for that request.

## Rule Pack

The committed rule pack is an explicit snapshot for Labor Code 45/2019/QH14, effective 2021-01-01. It records the official source URL, `rule_pack_version`, rule IDs, Article/Khoản citation labels, and short evidence-oriented descriptions.

Rules are heuristic presence checks. A finding means `Cần kiểm tra`, never proof of a violation. Any rule that cannot derive a fact must emit `missing_facts`, not guess.

## Result Contract

```json
{
  "disclaimer": "Kết quả là sàng lọc sơ bộ...",
  "rule_pack_version": "0.1.0",
  "source": {"instrument": "45/2019/QH14", "effective_from": "2021-01-01", "url": "..."},
  "findings": [{
    "id": "BLLD2019-ART21-WAGES",
    "severity": "review",
    "title": "Cần kiểm tra nội dung tiền lương",
    "evidence": "Không tìm thấy dấu hiệu rõ ràng...",
    "legal_basis": "Điều 21 khoản 1 điểm đ...",
    "missing_facts": ["Mức lương..."],
    "recommendation": "Đối chiếu bản gốc..."
  }]
}
```

## Safety and Acceptance Criteria

- Reject untrusted extension, empty file, oversized file, password-protected/unreadable PDF, and PDF without text layer.
- Escape file name, contract text, and all rendered values.
- Return no success-like legal conclusion.
- Rule pack is loaded from disk and validated before screening.
- Unit tests prove: required-content finding, fixed-term finding, no exact `compliant` verdict, escaped renderer, and invalid/oversized upload errors.

## Source

Official National Database of Legal Normative Documents: Labor Code 45/2019/QH14, effective 2021-01-01: https://vbpl.vn/TW/Pages/vbpqen-toanvan.aspx?ItemID=11135
