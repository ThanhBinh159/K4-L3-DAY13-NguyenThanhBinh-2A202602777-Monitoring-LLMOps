# Báo cáo cá nhân — K4-L3B Day 13 Monitoring & LLMOps

> Mỗi học viên hoàn thiện một file duy nhất này. Chỉ cần 3 output text và 5 ảnh runtime; dùng đường dẫn tương đối, ví dụ `evidence/03-incident-trace.png`.

## 1. Thông tin học viên

- **Họ và tên:** Nguyễn Thanh Bình
- **MSSV:** 2A202602777
- **Lớp:** K4-L3B
- **Repository URL:** https://github.com/ThanhBinh159/K4-L3-DAY13-NguyenThanhBinh-2A202602777-Monitoring-LLMOps
- **Commit SHA cuối:**
- **Challenge ID:**
- **Tên project Langfuse cá nhân:** `day13-k4-l3b-2A202602777`

## 2. Evidence index

Giữ đúng ba output text và năm ảnh dưới đây. Không tách thêm ảnh; nếu cần giải thích, ghi bằng chữ trong các mục sau.

| Evidence | Đường dẫn |
|---|---|
| Pytest cuối | `evidence/pytest.txt` |
| Log validator | `evidence/log-validator.txt` |
| Dashboard validator | `evidence/dashboard-validator.txt` |
| Structured log + incident log | `evidence/01-incident-log.png` |
| Trace list | `evidence/02-trace-list.png` |
| Trace waterfall + metadata + incident trace | `evidence/03-incident-trace.png` |
| Prompt versions + promote/rollback | `evidence/04-prompt-versioning.png` |
| Dashboard + incident metric | `evidence/05-dashboard-incident.png` |

## 3. Kết quả kỹ thuật

| Nội dung | Baseline | Kết quả cuối | Nhận xét |
|---|---|---|---|
| `validate_logs.py` | 30/100; 21 records, 20 thiếu fields, 20 thiếu enrichment, 0 correlation ID | 100/100; 21 records, 10 correlation ID, 0 PII leak | CP1 hoàn tất |
| `validate_dashboard.py` | 6/6 panel | 6/6 panel (CP2; cần chạy lại trên commit cuối) | Validator chỉ kiểm tra contract; dashboard runtime kiểm chứng riêng |
| `pytest` | 22 passed in 7.89s; có cảnh báo Langfuse export timeout | 30 passed in 4.44s (CP2; cần chạy lại trên commit cuối) | |
| Số traces hợp lệ | 10 | 10 trace mới của workload baseline v1 đã thấy trên Langfuse (CP2; chờ ảnh evidence cuối) | |
| Số PII leak | 0 | 0 | |
| Latency P95 / TTFT P95 | | | |
| Retrieval success rate | | | |

## 4. Logging và PII

- **Cách tạo/nhận và truyền correlation ID:** Middleware giữ `x-request-id` hợp lệ (1–64 ký tự chữ, số, dấu `.`, `_`, `:`, `-`), thay ID thiếu/không hợp lệ bằng `req-` và UUID rút gọn; gắn vào context log, response header và trace metadata.
- **Các metadata được ghi vào structured log:** `ts`, `level`, `event`, `correlation_id`, `user_id_hash`, `session_id`, `feature`, `model`, `env`; response có latency, TTFT, tokens, cost, quality và trạng thái retrieval.
- **Cách bảo đảm PII được scrub trước khi ghi:** `scrub_event` duyệt cả chuỗi lồng trong dict/list trước `JsonlFileProcessor`; user ID được hash, message/answer chỉ ghi preview đã scrub.
- **Cách kiểm chứng kết quả:** Sau khi tách baseline log và chạy lại 10 request, `validate_logs.py` báo 21 records, 0 thiếu field/context, 10 correlation ID và 0 PII leak (100/100).

## 5. Tracing và prompt versioning

- **Cách xác nhận traces do chính tôi tạo trong project cá nhân:** Project Langfuse `day13-k4-l3b-2A202602777` hiển thị trace của workload tự chạy; trace baseline `0804f84906ae529b7770c93d8a9e8539` khớp `correlation_id=req-0c22831b` từ request mẫu.
- **Cấu trúc root/retrieval/generation observations:** `day13-agent-request` → `lab-agent-run` → `retrieval` (retriever) và `llm-generate` (generation). Generation ghi model, prompt metadata, input/output tokens, cost và TTFT; không ghi raw prompt/output. Test riêng cho phần này: 2 passed. Trace `c1b6888b6bd0900af0d138bd31d5d916` hiển thị đúng hai child, 212 tokens và cost 0.002748 USD; input/output gốc không được capture.
- **Cách nối trace với log:** `correlation_id` nằm trong log và trace metadata; trace trên có `req-c1e4c875`, khớp ID do workload trả về. Preview email trong metadata đã được scrub.
- **Prompt name:** `day13-chat`; trace kiểm tra ban đầu còn `prompt_source=local-fallback`, `prompt_version=local-v1`. Cần tạo và kiểm chứng v1/v2 trên project Langfuse cá nhân.
- **Version/label baseline:** `day13-chat` v1 có `baseline` và `production`; trace `0804f84906ae529b7770c93d8a9e8539` xác nhận `prompt_source=langfuse`, `prompt_label=baseline`, `prompt_version=1`.
- **Version/label candidate:** `day13-chat` v2 có `candidate` và `latest`; cùng workload 10 input trả 10/10 HTTP 200. Trace `5783d215f56def9550d402add28b087b` xác nhận `prompt_source=langfuse`, `prompt_label=candidate`, `prompt_version=2`.
- **Trace ID của mỗi version:** baseline v1: `0804f84906ae529b7770c93d8a9e8539`; candidate v2: `5783d215f56def9550d402add28b087b`; production v2: `0c028137301b5bb642bc63db49d48b8c` (`correlation_id=req-0f18ca7e`).
- **Cách promote và rollback `production`:** Chuyển label `production` từ v1 sang v2, chạy request `req-0f18ca7e`; trace trên xác nhận `prompt_source=langfuse`, `prompt_label=production`, `prompt_version=2`. Sau đó đã chuyển `production` về v1; cần ảnh prompt versions sau rollback để hoàn tất evidence.

## 6. Dashboard, SLO và alerts

- **Dashboard và sáu panel:** Endpoint `/dashboard` đọc `data/logs.jsonl` theo cửa sổ 60 phút, refresh 30 giây; có latency P50/P95/P99 và TTFT, traffic, error rate và retrieval success, cost, input/output tokens, quality proxy. Contract ở [dashboard.yaml](../config/dashboard.yaml); test tổng hợp và render: 2 passed. Đã mở runtime và xác nhận đủ sáu panel; tại thời điểm kiểm tra trang hiển thị 20 requests, 0 failures trong 60 phút. Ảnh evidence cuối cần chụp sau challenge.
- **SLO và lý do chọn:** [SLO](../config/slo.yaml) giữ 99.5% request thành công trong 3000 ms trên cửa sổ 28 ngày. 10 request baseline đều HTTP 200 và dưới 2000 ms, nhưng mẫu quá nhỏ để hiệu chỉnh mục tiêu dài hạn.
- **Cách tính error budget:** 100% − 99.5% = 0.5%; trên 10,000 request cho phép tối đa 50 request lỗi hoặc chậm hơn 3000 ms.
- **Ba alert và runbook tương ứng:** [HighLatencyP95, ElevatedErrorRate, LowRetrievalSuccess](../config/alert_rules.yaml) có severity, duration 5m, owner, Slack channel và [runbook](../docs/alerts.md) với ba bước dashboard → log → trace cùng mitigation.

> Ví dụ cách viết error budget: "SLO 99.5% trong 28 ngày nghĩa là error budget 0.5%. Nếu workload có 10,000 request thì tối đa 50 request được phép lỗi hoặc chậm hơn ngưỡng SLO."

## 7. Điều tra challenge

- **Challenge ID:**
- **Khoảng thời gian điều tra:**
- **Triệu chứng từ metrics:**
- **Log line và correlation ID liên quan:**
- **Trace ID và span gây ảnh hưởng:**
- **Root cause:**
- **Fix action:**
- **Preventive measure:**

> Gợi ý cách viết ngắn, không thay cho evidence thực tế: "Metric cho thấy `[latency/error/cost/quality]` bất thường trong `[khoảng thời gian]`. Log line `[event]` có `correlation_id=[...]` đại diện cho request bị ảnh hưởng. Trace cùng `correlation_id` cho thấy span `[retrieval/generation/prompt/tool]` có dấu hiệu `[chậm/lỗi/token tăng]`. Root cause là `[nguyên nhân suy ra từ evidence]`. Fix action là `[hành động khôi phục]`; preventive measure là `[alert/runbook/test/guardrail để ngăn tái diễn]`."

## 8. Giải thích và tự đánh giá

- **Một quyết định kỹ thuật quan trọng và lý do:** Dùng FastAPI hiện có để phục vụ dashboard từ JSONL và YAML; tránh thêm service/dependency mới trong lab, đồng thời giữ nguồn số liệu đúng contract.
- **Một lỗi/blocker đã gặp:** Python 3.14.7 khiến `pydantic-core` phải build từ source và lỗi tại PyO3.
- **Cách tìm nguyên nhân và xử lý:** Kiểm tra `py -0p`, chuyển môi trường ảo sang Python 3.13.15 và cài lại các phiên bản dependency được pin; pip sau đó cài thành công.
- **Cách hiểu luồng Metrics → Logs → Traces:** Metric chỉ ra thời gian và triệu chứng; log trong khoảng đó cung cấp `correlation_id` và context request; trace cùng ID cho thấy bước retrieval/generation gây ảnh hưởng.
- **Vai trò của prompt version, token/cost, SLO hoặc rollback trong vận hành LLM:** Version và label cho phép so sánh cùng workload và rollback; token/cost cho thấy chi phí theo request; SLO, error budget và alert xác định khi nào cần điều tra.
- **Điều quan trọng nhất đã học:**
- **Hạn chế hoặc phần chưa hoàn thành, nếu có:**

## 9. Checklist trước khi nộp

- [ ] Kết quả và evidence thuộc commit SHA cuối.
- [ ] Tất cả ảnh/output mở được bằng đường dẫn tương đối.
- [ ] Có đúng 3 file text và 5 ảnh runtime theo hướng dẫn.
- [ ] Incident evidence nối đúng metric → log → trace.
- [ ] Trace/prompt evidence thuộc project Langfuse cá nhân và ảnh không lộ key/secret.
- [ ] Repository chạy lại được theo README.
- [ ] Không có secret, API key, PII thô hoặc evidence của người khác/lớp khác.
- [ ] URL repo và commit SHA cuối đã được nộp trên LMS/Codelabs.
