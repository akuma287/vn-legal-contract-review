# VN Labor Contract Review — MVP

Local web app sàng lọc sơ bộ hợp đồng lao động Việt Nam.

## Chạy

```bash
python3 -m pip install -r requirements.txt
python3 app.py
```

Mở http://127.0.0.1:8000.

## AI review

AI review là tùy chọn. Chỉ tick checkbox khi được phép gửi toàn bộ nội dung hợp đồng và Authorization key tới external provider qua HTTP không mã hóa.

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

- TXT UTF-8 và PDF có text layer, tối đa 2 MiB.
- Không lưu file hay text hợp đồng.
- Rule pack `0.1.0`: Bộ luật Lao động 2019, `45/2019/QH14`, hiệu lực `2021-01-01`.
- Check heuristic Điều 21 và thời hạn >36 tháng của Điều 20.
- AI chỉ nêu `Cần kiểm tra`; citation AI bị filter vào IDs do rule engine sinh.

## Không có

DOCX, OCR, authentication, database, RAG/vector DB, embeddings, report PDF, telemetry, legal conclusion.

Kết quả không phải tư vấn pháp lý, không xác nhận tuân thủ, vi phạm, có hiệu lực, vô hiệu, hay hợp pháp.

## Test

```bash
python3 -m unittest -v
python3 -m compileall -q app.py screening.py tests
```

## Nguồn rule-pack

[Bộ luật Lao động 2019 — 45/2019/QH14](https://vbpl.vn/TW/Pages/vbpqen-toanvan.aspx?ItemID=11135)

Rule pack là snapshot MVP. Verify hiệu lực văn bản và nội dung từng Điều/Khoản trước pilot thật.
