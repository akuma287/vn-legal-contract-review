# Vietnamese Labor Contract Screening MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local private web app that preliminarily screens uploaded Vietnamese labor-contract text against a small versioned Labor Code rule pack.

**Architecture:** `screening.py` contains pure rule-pack loading and text analysis. `app.py` serves one escaped HTML interface and handles request-scoped TXT/PDF parsing with stdlib `http.server` plus already-installed `pypdf`. `rules/labor_code_2019.json` provides all source metadata rendered in findings.

**Tech Stack:** Python 3.13 stdlib, `pypdf`, `unittest`.

**Spec:** `docs/superpowers/specs/2026-09-10-vn-labor-contract-mvp-design.md`

## Global Constraints

- Private local listener only: `127.0.0.1:8000`.
- Accept only UTF-8 `.txt` and text-based `.pdf`; limit upload to `2 MiB`.
- Never save uploads, extracted contract text, findings, or user data.
- No RAG, embeddings, vector DB, auth, DOCX, OCR, report export, or telemetry.
- Optional external AI review sends contract text only after an explicit checkbox consent on that upload; it defaults to `http://103.160.2.141/v1` and model `cx/gpt-5.6-terra`.
- API credentials are loaded only from ignored `.env` or process environment; never track a secret.
- Every deterministic or AI finding uses `Cần kiểm tra`; never claim legal validity, invalidity, legality, or compliance.
- Every finding cites rule-pack source metadata from Labor Code `45/2019/QH14`, effective `2021-01-01`.
- Rule pack version: `0.1.0`.

---

### Task 1: Versioned rule pack and pure screening engine

**Files:**
- Create: `rules/labor_code_2019.json`
- Create: `screening.py`
- Create: `tests/test_screening.py`

**Interfaces:**
- Produces: `load_rule_pack(path: str | Path = DEFAULT_RULE_PACK) -> dict`
- Produces: `screen_text(text: str, rule_pack: dict | None = None) -> dict`
- `screen_text` returns source metadata, disclaimer, `rule_pack_version`, and zero or more structured findings.

- [ ] **Step 1: Write a failing screening test**

```python
def test_missing_wages_emits_review_finding_with_article_21_basis():
    result = screen_text("HỢP ĐỒNG LAO ĐỘNG\nCông việc: Kế toán\nThời hạn: 12 tháng")
    finding = next(item for item in result["findings"] if item["id"] == "BLLD2019-ART21-WAGES")
    assert finding["severity"] == "review"
    assert finding["legal_basis"] == "Điều 21 khoản 1 điểm đ Bộ luật Lao động 2019"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_screening.ScreeningTests.test_missing_wages_emits_review_finding_with_article_21_basis -v`

Expected: FAIL because `screening` does not exist.

- [ ] **Step 3: Implement minimal rule pack and screening engine**

Implement Article 21 heuristic rules for work, workplace, duration, wages, work/rest time, social insurance, training. Implement Article 20 duration rule only when an explicit integer month duration exceeds 36. All absence-based outcomes are `review` findings with `Cần kiểm tra` text and `missing_facts`.

- [ ] **Step 4: Add boundary tests and run all screening tests**

```python
def test_fixed_term_over_36_months_emits_review_finding():
    result = screen_text("Hợp đồng xác định thời hạn 48 tháng. Công việc: Kế toán.")
    assert any(item["id"] == "BLLD2019-ART20-FIXED-TERM" for item in result["findings"])


def test_result_does_not_contain_compliance_verdict():
    result = screen_text("Công việc: Kế toán")
    assert "compliant" not in str(result).lower()
```

Run: `python3 -m unittest tests.test_screening -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add rules/labor_code_2019.json screening.py tests/test_screening.py
git commit -m "feat: add labor contract screening rules"
```

### Task 2: Local upload UI and safe request handling

**Files:**
- Create: `app.py`
- Modify: `tests/test_screening.py`

**Interfaces:**
- Produces: `render_report(result: dict, filename: str) -> str`
- Produces: `extract_contract_text(filename: str, content: bytes) -> str`
- Produces: `make_server(host: str = "127.0.0.1", port: int = 8000) -> HTTPServer`

- [ ] **Step 1: Write a failing renderer test**

```python
def test_report_escapes_untrusted_filename_and_keeps_preliminary_disclaimer():
    html = render_report(screen_text("Công việc: Kế toán"), '<img src=x onerror=alert(1)>.txt')
    assert "&lt;img" in html
    assert "Kết quả là sàng lọc sơ bộ" in html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_screening.AppTests.test_report_escapes_untrusted_filename_and_keeps_preliminary_disclaimer -v`

Expected: FAIL because `app` does not exist.

- [ ] **Step 3: Implement app**

Use only `http.server`, `email.parser.BytesParser` for multipart parsing, `html.escape`, and `pypdf.PdfReader`. Python 3.13 no longer provides `cgi`. Bind the server to `127.0.0.1`; render a single upload form with explicit AI-consent checkbox; reject invalid extension, empty content, content above `2 * 1024 * 1024`, unreadable PDF, and PDF with no text layer. Do not write uploaded content to disk. The AI adapter reads `LEGAL_AI_API_KEY` only from ignored `.env` or process environment and filters model citations to rule-pack IDs.

- [ ] **Step 4: Add request-boundary tests and run all tests**

```python
def test_extract_contract_text_rejects_invalid_extension():
    with self.assertRaisesRegex(ValueError, "TXT hoặc PDF"):
        extract_contract_text("contract.docx", b"not a docx")


def test_extract_contract_text_rejects_oversized_upload():
    with self.assertRaisesRegex(ValueError, "2 MiB"):
        extract_contract_text("contract.txt", b"a" * (2 * 1024 * 1024 + 1))
```

Run: `python3 -m unittest -v`

Expected: PASS.

- [ ] **Step 5: Smoke-test browser route and commit**

Run:

```bash
python3 app.py > /tmp/vn-labor-screening.log 2>&1 &
PID=$!
trap 'kill $PID' EXIT
sleep 1
curl -fsS http://127.0.0.1:8000/ | grep -F 'Rà soát sơ bộ hợp đồng lao động'
kill $PID
wait $PID 2>/dev/null || true
trap - EXIT
git add app.py tests/test_screening.py
git commit -m "feat: add local contract upload screen"
```

Expected: page heading printed and command exits `0`.

### Task 3: Project documentation and clean verification

**Files:**
- Create: `README.md`
- Create: `.gitignore`

**Interfaces:**
- Documents run command `python3 app.py` and test command `python3 -m unittest -v`.

- [ ] **Step 1: Write README and .gitignore**

Document exact scope, legal limitation, supported formats, local-only storage behavior, source snapshot, run/test commands, and omitted production features. Ignore `.venv/`, `__pycache__/`, `.DS_Store`, and local uploads.

- [ ] **Step 2: Run complete verification**

Run:

```bash
python3 -m unittest -v
python3 -m compileall -q app.py screening.py tests
python3 app.py > /tmp/vn-labor-screening.log 2>&1 &
PID=$!
trap 'kill $PID' EXIT
sleep 1
curl -fsS http://127.0.0.1:8000/ | grep -F 'Rà soát sơ bộ hợp đồng lao động'
printf 'Hợp đồng lao động\nCông việc: Kế toán\nThời hạn: 48 tháng\n' > /tmp/sample-contract.txt
curl -fsS -F 'contract=@/tmp/sample-contract.txt;type=text/plain' http://127.0.0.1:8000/screen | grep -F 'Thời hạn hợp đồng xác định'
kill $PID
wait $PID 2>/dev/null || true
trap - EXIT
git diff --check
git status --short
```

Expected: all tests pass, syntax check exits `0`, UI and upload smoke checks find expected text, no whitespace errors, only intended documentation changes before commit.

- [ ] **Step 3: Commit**

```bash
git add README.md .gitignore
git commit -m "docs: document local labor contract screener"
```
