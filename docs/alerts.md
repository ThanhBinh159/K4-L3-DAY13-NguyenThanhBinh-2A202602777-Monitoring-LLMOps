# Template Alert và Runbook

Mỗi alert phải dựa trên triệu chứng người dùng hoặc SLO, không dựa trực tiếp vào tên implementation nội bộ.

## Alert mẫu để tham khảo

Ví dụ dưới đây minh họa mức độ cụ thể cần có. Học viên không cần copy nguyên, nhưng ba alert trong bài nộp nên rõ ràng tương tự: điều kiện là gì, kéo dài bao lâu, ảnh hưởng tới user ra sao và người trực cần kiểm tra gì trước.

- Tên: `HighLatencyP95`
- Severity: `warning`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: latency P95 của `response_sent.latency_ms`
- Điều kiện và thời gian duy trì: `p95(latency_ms) > 3000ms` trong 5 phút
- Ảnh hưởng tới người dùng: người dùng phải chờ lâu hơn trước khi nhận câu trả lời
- Ba bước kiểm tra đầu tiên:
  1. Mở dashboard latency để xác nhận P95/P99 và khoảng thời gian tăng.
  2. Lọc `data/logs.jsonl` trong khoảng đó, lấy một `correlation_id` có `latency_ms` cao.
  3. Mở trace cùng `correlation_id` trên Langfuse, so sánh các span chính để xác định bước nào bất thường.
- Mitigation tạm thời: dựa trên evidence thực tế để rollback prompt, khôi phục cấu hình liên quan, tắt practice scenario hoặc giảm tải khi demo.
- Owner: `student-<MSSV>`

## Alert 1

- Tên: HighLatencyP95
- Severity: warning
- Duration: 5m
- Kênh thông báo: Slack #k4-l3b-alerts
- SLI/SLO liên quan: P95 của response_sent.latency_ms; SLO request thành công trong 3000ms.
- Điều kiện và thời gian duy trì: P95 > 3000ms liên tục 5 phút.
- Ảnh hưởng tới người dùng: câu trả lời đến chậm.
- Ba bước kiểm tra đầu tiên:
  1. Xem panel latency, so P95/P99 với TTFT và xác định khoảng thời gian tăng.
  2. Lọc log response_sent có latency_ms cao trong khoảng đó, lấy correlation_id.
  3. Mở trace cùng ID; so thời gian span retrieval và generation để khoanh vùng.
- Mitigation tạm thời: xử lý span chậm đã xác nhận; nếu thay đổi prompt gây chậm, rollback label production về version trước.
- Owner: student-2A202602777

## Alert 2

- Tên: ElevatedErrorRate
- Severity: critical
- Duration: 5m
- Kênh thông báo: Slack #k4-l3b-alerts
- SLI/SLO liên quan: tỷ lệ request_failed / request_received; SLO request thành công.
- Điều kiện và thời gian duy trì: error rate > 2% liên tục 5 phút.
- Ảnh hưởng tới người dùng: một phần request không nhận được câu trả lời.
- Ba bước kiểm tra đầu tiên:
  1. Xem panel errors và thời điểm error rate tăng; đọc breakdown theo error_type.
  2. Lọc request_failed trong log, lấy một correlation_id và error_type.
  3. Mở trace cùng ID, xác định span lỗi và so với request thành công.
- Mitigation tạm thời: khôi phục dependency gây lỗi hoặc tắt practice scenario sau khi xác nhận; theo dõi error rate trở lại ngưỡng.
- Owner: student-2A202602777

## Alert 3

- Tên: LowRetrievalSuccess
- Severity: warning
- Duration: 5m
- Kênh thông báo: Slack #k4-l3b-alerts
- SLI/SLO liên quan: retrieval success; guardrail tối thiểu 90% trong config/slo.yaml.
- Điều kiện và thời gian duy trì: tool_success=true trên tổng lần gọi tool dưới 90% liên tục 5 phút.
- Ảnh hưởng tới người dùng: câu trả lời có thể thiếu context hoặc request thất bại.
- Ba bước kiểm tra đầu tiên:
  1. Xem retrieval success trong panel errors để xác định khoảng giảm.
  2. Lọc log có tool_name=retrieval và tool_success=false, lấy correlation_id.
  3. Mở trace cùng ID, kiểm tra span retrieval và lỗi từ kho tài liệu.
- Mitigation tạm thời: khôi phục truy xuất tài liệu; nếu đang chạy practice scenario, tắt scenario rồi đo lại.
- Owner: student-2A202602777
