import json
import unittest
from io import BytesIO
from unittest.mock import patch

from pypdf import PdfWriter

from app import (
    CHAT_SESSIONS,
    chat_with_ai,
    create_chat_session,
    extract_contract_text,
    render_chat_page,
    render_home,
    render_report,
    review_with_ai,
    validate_request_origin,
)
from screening import screen_text


class ScreeningTests(unittest.TestCase):
    def test_missing_wages_emits_review_finding_with_article_21_basis(self):
        result = screen_text(
            "HỢP ĐỒNG LAO ĐỘNG\nCông việc: Kế toán\nThời hạn: 12 tháng"
        )

        finding = next(
            item
            for item in result["findings"]
            if item["id"] == "BLLD2019-ART21-WAGES"
        )

        self.assertEqual(finding["severity"], "review")
        self.assertEqual(
            finding["legal_basis"],
            "Điều 21 khoản 1 điểm đ Bộ luật Lao động 2019",
        )

    def test_work_without_workplace_emits_workplace_review_finding(self):
        result = screen_text("Hợp đồng lao động. Công việc: Kế toán.")

        self.assertTrue(
            any(item["id"] == "BLLD2019-ART21-WORKPLACE" for item in result["findings"])
        )

    def test_fixed_term_over_36_months_emits_review_finding(self):
        result = screen_text("Hợp đồng xác định thời hạn 48 tháng. Công việc: Kế toán.")

        self.assertTrue(
            any(item["id"] == "BLLD2019-ART20-FIXED-TERM" for item in result["findings"])
        )

    def test_result_does_not_contain_compliance_verdict(self):
        result = screen_text("Công việc: Kế toán")

        self.assertNotIn("compliant", str(result).lower())
        self.assertNotIn("hợp pháp", str(result).casefold())

    def test_multi_law_rule_packs_emit_domain_findings(self):
        text = (
            "Hợp đồng lao động. Lương gross 50.000.000 VNĐ. "
            "Người lao động xử lý dữ liệu cá nhân khách hàng, mã nguồn và tác phẩm thuộc công ty."
        )
        ids = {item["id"] for item in screen_text(text)["findings"]}

        self.assertIn("BHXH2024-COMPULSORY-WAGE-BASE", ids)
        self.assertIn("PIT2007-GROSS-NET-WITHHOLDING", ids)
        self.assertIn("PDPD2023-EMPLOYEE-CUSTOMER-DATA", ids)
        self.assertIn("IP2005-WORK-CREATED-ASSET", ids)


class AppTests(unittest.TestCase):
    def test_report_escapes_untrusted_filename_and_keeps_preliminary_disclaimer(self):
        html = render_report(
            screen_text("Công việc: Kế toán"),
            '<img src=x onerror=alert(1)>.txt',
        )

        self.assertIn("&lt;img", html)
        self.assertNotIn("<img src=x", html)
        self.assertIn("Kết quả là sàng lọc sơ bộ", html)

    def test_report_lists_legal_sources_but_hides_rule_checks(self):
        html = render_report(
            screen_text("Hợp đồng lao động. Công việc: Kế toán."),
            "contract.txt",
        )

        self.assertIn("Căn cứ pháp lý đang dùng", html)
        self.assertIn("Bộ luật Lao động 2019", html)
        self.assertIn("Luật Bảo hiểm xã hội 2024", html)
        self.assertNotIn("<h2>Rule checks</h2>", html)
        self.assertNotIn("BLLD2019-ART21-WAGES", html)

    def test_ai_consent_says_pii_is_masked_before_ai_transfer(self):
        home = render_home()
        self.assertIn("Thông tin cá nhân sẽ được che", home)
        self.assertIn("trước khi gửi đến AI", home)
        self.assertNotIn("Authorization key", home)

    def test_home_shows_loading_overlay_after_submit(self):
        home = render_home()
        self.assertIn("id='loading-overlay'", home)
        self.assertIn("Đang rà soát hợp đồng", home)
        self.assertIn("addEventListener('submit'", home)

    def test_cross_site_origin_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Origin"):
            validate_request_origin("https://attacker.example", "127.0.0.1:8000")

    def test_local_origin_and_cli_without_origin_are_accepted(self):
        validate_request_origin("http://127.0.0.1:8000", "127.0.0.1:8000")
        validate_request_origin("https://vn-legal-contract-review.onrender.com", "vn-legal-contract-review.onrender.com")
        validate_request_origin("", "127.0.0.1:8000")

    def test_extract_contract_text_rejects_invalid_extension(self):
        with self.assertRaisesRegex(ValueError, "TXT hoặc PDF"):
            extract_contract_text("contract.docx", b"not a docx")

    def test_extract_contract_text_rejects_oversized_upload(self):
        with self.assertRaisesRegex(ValueError, "2 MiB"):
            extract_contract_text("contract.txt", b"a" * (2 * 1024 * 1024 + 1))

    def test_extract_contract_text_rejects_pdf_without_text_layer(self):
        stream = BytesIO()
        writer = PdfWriter()
        writer.add_blank_page(width=100, height=100)
        writer.write(stream)

        with self.assertRaisesRegex(ValueError, "lớp văn bản"):
            extract_contract_text("scan.pdf", stream.getvalue())

    def test_ai_review_requires_explicit_consent(self):
        with self.assertRaisesRegex(PermissionError, "đồng ý"):
            review_with_ai(
                "Công việc: Kế toán",
                screen_text("Công việc: Kế toán"),
                consent=False,
            )

    @patch("app.urlopen", side_effect=TimeoutError)
    @patch.dict("os.environ", {"LEGAL_AI_API_KEY": "test-key"}, clear=False)
    def test_ai_review_timeout_returns_safe_error(self, _mocked_urlopen):
        with self.assertRaisesRegex(RuntimeError, "Không kết nối được AI provider"):
            review_with_ai(
                "Công việc: Kế toán",
                screen_text("Công việc: Kế toán"),
                consent=True,
            )

    @patch("app.urlopen")
    @patch.dict("os.environ", {"LEGAL_AI_API_KEY": "test-key"}, clear=False)
    def test_ai_review_uses_allowed_rule_pack_citations_only(self, mocked_urlopen):
        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def read(self):
                return json.dumps(
                    {
                        "choices": [
                            {
                                "message": {
                                    "content": json.dumps(
                                        {
                                            "summary": "The contract is compliant.",
                                            "findings": [
                                                {
                                                    "title": "Cần kiểm tra lương",
                                                    "issue": "Thiếu mức lương rõ ràng.",
                                                    "risk_level": "review",
                                                    "legal_basis_ids": [
                                                        "BLLD2019-ART21-WAGES",
                                                        "MADE-UP-CITATION",
                                                    ],
                                                    "missing_facts": ["Mức lương"],
                                                },
                                                {
                                                    "title": "Cần kiểm tra không có căn cứ",
                                                    "issue": "Không được giữ finding này.",
                                                    "risk_level": "review",
                                                    "legal_basis_ids": ["MADE-UP-CITATION"],
                                                    "missing_facts": [],
                                                },
                                            ],
                                        },
                                        ensure_ascii=False,
                                    )
                                }
                            }
                        ]
                    },
                    ensure_ascii=False,
                ).encode()

        mocked_urlopen.return_value = Response()
        result = review_with_ai(
            "Công việc: Kế toán",
            screen_text("Công việc: Kế toán"),
            consent=True,
        )

        self.assertEqual(
            result["findings"][0]["legal_basis_ids"], ["BLLD2019-ART21-WAGES"]
        )
        self.assertEqual(result["findings"][0]["risk_level"], "review")
        self.assertEqual(len(result["findings"]), 1)
        self.assertNotIn("compliant", result["summary"].lower())

    def test_ai_review_persists_clarifying_questions(self):
        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def read(self):
                return json.dumps(
                    {
                        "choices": [
                            {
                                "message": {
                                    "content": json.dumps(
                                        {
                                            "summary": "Sàng lọc sơ bộ.",
                                            "findings": [
                                                {
                                                    "title": "Cần kiểm tra lương",
                                                    "issue": "Thiếu mức lương rõ ràng.",
                                                    "risk_level": "review",
                                                    "legal_basis_ids": [
                                                        "BLLD2019-ART21-WAGES"
                                                    ],
                                                    "missing_facts": ["Mức lương"],
                                                }
                                            ],
                                            "clarifying_questions": [
                                                {
                                                    "question": "Mức lương cụ thể là bao nhiêu?",
                                                    "clause_ref": "Điều 3.1",
                                                    "why_important": "Rủi ro tài chính trực tiếp.",
                                                },
                                                {
                                                    "question": "",
                                                    "clause_ref": "",
                                                    "why_important": "",
                                                },
                                            ],
                                        },
                                        ensure_ascii=False,
                                    )
                                }
                            }
                        ]
                    },
                    ensure_ascii=False,
                ).encode()

        with patch("app.urlopen", return_value=Response()):
            result = review_with_ai(
                "Công việc: Kế toán",
                screen_text("Công việc: Kế toán"),
                consent=True,
            )

        self.assertEqual(len(result["clarifying_questions"]), 1)
        question = result["clarifying_questions"][0]
        self.assertIn("Mức lương", question["question"])
        self.assertIn(question["clause_ref"], "Điều 3.1")

        html = render_report(
            screen_text("Công việc: Kế toán"),
            "contract.txt",
            ai_review=result,
        )
        self.assertIn("Câu hỏi cần làm rõ", html)
        self.assertIn("Mức lương cụ thể", html)

    def test_ai_review_without_clarifying_questions_renders_no_section(self):
        result = {
            "summary": "Sàng lọc sơ bộ.",
            "findings": [],
            "clarifying_questions": [],
        }
        html = render_report(
            screen_text("Công việc: Kế toán"),
            "contract.txt",
            ai_review=result,
        )
        self.assertNotIn("Câu hỏi cần làm rõ", html)


    def test_ai_review_masks_pii_before_sending_to_provider(self):
        captured: dict[str, str] = {}

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def read(self):
                return json.dumps(
                    {"choices": [{"message": {"content": json.dumps({"summary": "OK", "findings": [], "clarifying_questions": []}, ensure_ascii=False)}}]},
                    ensure_ascii=False,
                ).encode()

        def fake_urlopen(request, timeout):
            captured["body"] = request.data.decode()
            return Response()

        contract = "Người lao động: Nguyễn Văn A, SĐT 0901234567, email nguyenvana@gmail.com, CCCD 079203001234."
        with patch("app.urlopen", side_effect=fake_urlopen):
            review_with_ai(contract, screen_text("Công việc: Kế toán"), consent=True)

        body = captured["body"]
        self.assertNotIn("0901234567", body)
        self.assertNotIn("nguyenvana@gmail.com", body)
        self.assertNotIn("079203001234", body)
        self.assertIn("PHONE_NUMBER", body)
        self.assertIn("EMAIL_ADDRESS", body)
        self.assertIn("VN_CCCD", body)

    def test_chat_session_renders_chat_form_after_ai_review(self):
        CHAT_SESSIONS.clear()
        result = screen_text("Công việc: Kế toán")
        ai_review = {"summary": "OK", "findings": [], "clarifying_questions": []}
        session_id = create_chat_session("contract.txt", "Công việc: Kế toán", result, ai_review)

        html = render_report(result, "contract.txt", ai_review=ai_review, session_id=session_id)

        self.assertIn("Hỏi tiếp về hợp đồng", html)
        self.assertIn(session_id, html)
        self.assertIn("← Kiểm tra hợp đồng khác", html)

    @patch("app.urlopen")
    def test_chat_answer_renders_inside_existing_report_with_history(self, mocked_urlopen):
        CHAT_SESSIONS.clear()
        result = screen_text("Công việc: Kế toán")
        ai_review = {"summary": "OK", "findings": [], "clarifying_questions": []}
        session_id = create_chat_session("contract.txt", "Công việc: Kế toán", result, ai_review)

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def read(self):
                return json.dumps({"choices": [{"message": {"content": "Cần kiểm tra lương."}}]}, ensure_ascii=False).encode()

        mocked_urlopen.return_value = Response()
        answer = chat_with_ai(session_id, "Lương ổn chưa?")
        html = render_chat_page(session_id)

        self.assertIn("Kết quả rà soát sơ bộ", html)
        self.assertIn("Lương ổn chưa?", html)
        self.assertIn(answer, html)
        self.assertIn("Hỏi tiếp về hợp đồng", html)
        self.assertIn("id='chat-panel'", html)
        self.assertIn("class='chat-log'", html)
        self.assertIn("action='/chat#chat-panel'", html)
        self.assertIn("scrollTop = chatLog.scrollHeight", html)

    @patch("app.urlopen")
    @patch.dict("os.environ", {"LEGAL_AI_API_KEY": "test-key"}, clear=False)
    def test_chat_masks_user_question_before_sending_to_provider(self, mocked_urlopen):
        CHAT_SESSIONS.clear()
        result = screen_text("Công việc: Kế toán")
        session_id = create_chat_session(
            "contract.txt",
            "Người lao động SĐT 0901234567. Công việc: Kế toán.",
            result,
            {"summary": "OK", "findings": [], "clarifying_questions": []},
        )
        captured: dict[str, str] = {}

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def read(self):
                return json.dumps({"choices": [{"message": {"content": "Cần kiểm tra mức lương."}}]}, ensure_ascii=False).encode()

        def fake_urlopen(request, timeout):
            captured["body"] = request.data.decode()
            return Response()

        mocked_urlopen.side_effect = fake_urlopen
        answer = chat_with_ai(session_id, "SĐT 0901234567 có cần ghi không?")

        self.assertIn("Cần kiểm tra", answer)
        self.assertNotIn("0901234567", captured["body"])
        self.assertIn("PHONE_NUMBER", captured["body"])


if __name__ == "__main__":
    unittest.main()
