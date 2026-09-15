# VN Contract Review — MVP

Local web app sàng lọc sơ bộ hợp đồng Việt Nam.

## Chạy

```bash
python3 -m pip install -r requirements.txt
python3 app.py
```

Mở http://127.0.0.1:8000.

## AI review

AI review là tùy chọn. Trước khi gửi đến AI, app che PII dạng SĐT, CCCD, email và mã số thuế bằng placeholder như `{{PHONE_NUMBER_1}}`. Tên người/địa chỉ chưa được che trong MVP regex-only.

```bash
cp .env.example .env
# Điền LEGAL_AI_API_KEY mới trong .env
```

App dùng endpoint/model:

```text
http://103.160.2.141/v1/chat/completions
cx/gpt-5.6-terra
```

Không commit `.env`. Key từng xuất hiện trong chat phải rotate trước khi dùng lại.

## Phạm vi hiện tại

- TXT UTF-8, PDF có text layer và DOCX, tối đa 2 MiB.
- Không lưu file hay text hợp đồng.
- Có nút tải báo cáo PDF đơn giản từ kết quả hiện tại; không pixel-perfect theo web UI.
- Rule pack nền: chủ thể/thẩm quyền, thanh toán, chấm dứt, tranh chấp.
- Rule pack chuyên đề: hợp đồng lao động, dịch vụ, hợp tác, BHXH, thuế TNCN, dữ liệu cá nhân, sở hữu trí tuệ.
- Hợp đồng có thể match nhiều pack; ví dụ hợp tác cung cấp dịch vụ chạy cả hợp tác và dịch vụ.
- AI chỉ nêu `Cần kiểm tra`; citation AI bị filter vào IDs do rule engine sinh.

## Không có

DOC legacy, OCR, authentication, database, RAG/vector DB, embeddings, PDF pixel-perfect, telemetry, legal conclusion.

Kết quả không phải tư vấn pháp lý, không xác nhận tuân thủ, vi phạm, có hiệu lực, vô hiệu, hay hợp pháp.

## Test

```bash
python3 -m unittest -v
python3 -m compileall -q app.py screening.py tests
```

## Nguồn rule-pack

[Bộ luật Dân sự 2015 — 91/2015/QH13](https://vbpl.vn/TW/Pages/vbpq-toanvan.aspx?ItemID=96189)
[Bộ luật Lao động 2019 — 45/2019/QH14](https://vbpl.vn/TW/Pages/vbpqen-toanvan.aspx?ItemID=11135)

Rule pack là snapshot MVP. Verify hiệu lực văn bản và nội dung từng Điều/Khoản trước pilot thật.
