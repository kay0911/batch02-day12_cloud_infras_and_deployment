# Deployment Information

Triển khai production AI Agent hoàn chỉnh kết hợp đầy đủ cơ chế API Key Authentication, Sliding Window Rate Limiting (Redis-backed), Cost Guard (Redis-backed), và Stateless Session History (Redis-backed).

## Public URL
- **Dịch vụ Agent**: `https://testrailway-production-6eb5.up.railway.app/`
- **Nền tảng vận hành**: Railway Cloud

## Danh sách Biến Môi trường Đã Cấu hình (Environment Variables)
Các cấu hình tuân thủ nguyên tắc 12-Factor App, toàn bộ được cấu hình trực tiếp trên Railway:
- `PORT`: `8000` (Cổng dịch vụ do Railway tự động cung cấp động và bind qua Docker)
- `ENVIRONMENT`: `production` (Kích hoạt chế độ kiểm tra nghiêm ngặt bắt buộc của môi trường sản xuất)
- `AGENT_API_KEY`: `your-secret-api-key` (Khóa API dùng để xác thực các client khi truy vấn `/ask` và `/metrics`)
- `JWT_SECRET`: `supersecretjwtkey` (Mã khóa bí mật dùng cho JWT)
- `GEMINI_API_KEY`: `AIzaSyBap3XcBcIp_...` (Khóa API chính thức của Google Gemini để kết nối xử lý ngôn ngữ thực tế)
- `LLM_MODEL`: `gemini-3.1-flash-lite` (Mô hình Gemini được chỉ định sử dụng)
- `REDIS_URL`: `redis://default:HYZLVXEvZrqGYLbyXFDgOfoBJzUlmNsY@redis.railway.internal:6379` (Đường dẫn kết nối nội bộ đến instance Redis trên Railway)
- `DAILY_BUDGET_USD`: `5.0` (Ngăn chặn tràn ngân sách tiêu dùng hằng ngày)
- `RATE_LIMIT_PER_MINUTE`: `20` (Hạn mức tối đa 20 yêu cầu mỗi phút cho mỗi client)

---

## Chi tiết Kết quả Kiểm thử (Test Cases & Outputs Verification)

Dưới đây là các câu lệnh kiểm thử chạy thực tế trên terminal cùng kết quả phản hồi trả về từ hệ thống:

### 1. Kiểm tra Trạng thái Liveness & Readiness (Health Checks)

#### A. Endpoint Liveness (`/health`)
Endpoint dùng để nền tảng cloud giám sát sự sống của container. Khi cấu hình `GEMINI_API_KEY`, hệ thống sẽ phát hiện và chuyển đổi sang kết nối Gemini.

**Câu lệnh chạy (PowerShell):**
```powershell
Invoke-RestMethod -Uri https://testrailway-production-6eb5.up.railway.app/health
```
**Kết quả thực tế trả về:**
```json
{
  "status": "ok",
  "version": "1.0.0",
  "environment": "production",
  "uptime_seconds": 289.7,
  "total_requests": 5,
  "checks": {
    "llm": "gemini"
  },
  "timestamp": "2026-06-12T09:14:57.496641+00:00"
}
```

#### B. Endpoint Readiness (`/ready`)
Kiểm tra kết nối trực tiếp đến cơ sở dữ liệu Redis. Load balancer sẽ chỉ đẩy traffic vào khi kết nối thành công (`ready: true`).

**Câu lệnh chạy (PowerShell):**
```powershell
Invoke-RestMethod -Uri https://testrailway-production-6eb5.up.railway.app/ready
```
**Kết quả thực tế trả về:**
```json
{
  "ready": true
}
```

---

### 2. Kiểm thử bảo mật (Authentication Test)
Gọi API `/ask` nhưng không gửi kèm khóa bảo mật `X-API-Key`.

**Câu lệnh chạy (PowerShell):**
```powershell
try {
  Invoke-RestMethod -Uri https://testrailway-production-6eb5.up.railway.app/ask -Method Post -ContentType "application/json" -Body '{"question": "Hello"}'
} catch {
  $_.Exception.Response.StatusCode
  $_.ErrorDetails.Message
}
```
**Kết quả thực tế trả về:**
```
401
{"detail":"Invalid or missing API key. Include header: X-API-Key: <key>"}
```
*(Đạt chuẩn: Trả về lỗi 401 Unauthorized khi không được xác thực).*

---

### 3. Kiểm thử tích hợp Gemini API thực tế (API Call Test)
Gửi câu hỏi hỏi mô hình Gemini thực tế trên cloud bằng API Key của dự án.

**Câu lệnh chạy (PowerShell):**
```powershell
Invoke-RestMethod -Uri https://testrailway-production-6eb5.up.railway.app/ask -Method Post -ContentType "application/json" -Headers @{"X-API-Key"="your-secret-api-key"} -Body '{"question":"What is a stateless API?"}'
```
**Kết quả thực tế trả về:**
```json
{
  "question": "What is a stateless API?",
  "answer": "A **stateless API** is an API design paradigm where the server does not store any information about the client's past requests. Each request from a client must contain all the necessary information, context, and credentials to understand and complete the request...",
  "model": "gemini-3.1-flash-lite",
  "timestamp": "2026-06-12T09:12:44.201824+00:00"
}
```

---

### 4. Kiểm thử Stateless Session History (Conversation Memory)
Sử dụng Redis để lưu trữ và duy trì ngữ cảnh chat liên tục giữa các request độc lập của cùng một `user_id`.

#### Bước A: Gửi ngữ cảnh giới thiệu tên
**Câu lệnh chạy (PowerShell):**
```powershell
Invoke-RestMethod -Uri https://testrailway-production-6eb5.up.railway.app/ask -Method Post -ContentType "application/json" -Headers @{"X-API-Key"="your-secret-api-key"} -Body '{"question":"My name is John. What is yours?","user_id":"test_history_123"}'
```
**Kết quả trả về từ Gemini:**
```json
{
  "question": "My name is John. What is yours?",
  "answer": "Nice to meet you, John! I don't have a personal name—I am a large language model trained by Google...",
  "model": "gemini-3.1-flash-lite",
  "timestamp": "2026-06-12T09:14:28.021041+00:00"
}
```

#### Bước B: Gửi câu hỏi truy hồi thông tin cũ
**Câu lệnh chạy (PowerShell):**
```powershell
Invoke-RestMethod -Uri https://testrailway-production-6eb5.up.railway.app/ask -Method Post -ContentType "application/json" -Headers @{"X-API-Key"="your-secret-api-key"} -Body '{"question":"What is my name?","user_id":"test_history_123"}'
```
**Kết quả trả về từ Gemini:**
```json
{
  "question": "What is my name?",
  "answer": "Your name is John.",
  "model": "gemini-3.1-flash-lite",
  "timestamp": "2026-06-12T09:14:38.031812+00:00"
}
```
*(Đạt chuẩn: Mặc dù server hoàn toàn stateless, Redis đã đồng bộ lịch sử hội thoại chính xác giúp Gemini nhận diện được tên người dùng).*

---

### 5. Kiểm thử Rate Limiting (Hạn mức 20 req/min)
Thực thi gửi liên tiếp 25 requests liên tục thông qua vòng lặp PowerShell để kích hoạt cơ chế khóa trượt của Redis ZSET.

**Câu lệnh chạy (PowerShell):**
```powershell
for ($i=1; $i -le 25; $i++) {
  try {
    Invoke-RestMethod -Uri https://testrailway-production-6eb5.up.railway.app/ask -Method Post -ContentType "application/json" -Headers @{"X-API-Key"="your-secret-api-key"} -Body '{"question":"Hello","user_id":"test_limiter"}' | Out-Null
  } catch {
    $_.Exception.Response.StatusCode
    break
  }
}
```
**Kết quả thực tế trả về:**
```
429
```
*(Đạt chuẩn: Trả về HTTP Code `429 Too Many Requests` khi request thứ 21 được gửi đi).*

---

### 6. Kiểm thử Cost Guard & Metrics
Truy cập `/metrics` để xem lượng token đã tiêu thụ được tích lũy chi phí quy đổi sang USD thực tế.

**Câu lệnh chạy (PowerShell):**
```powershell
Invoke-RestMethod -Uri https://testrailway-production-6eb5.up.railway.app/metrics -Headers @{"X-API-Key"="your-secret-api-key"}
```
**Kết quả thực tế trả về:**
```json
{
  "uptime_seconds": 277.8,
  "total_requests": 3,
  "error_count": 0,
  "daily_cost_usd": 0.0023,
  "daily_budget_usd": 5.0
}
```

---

## Ảnh chụp màn hình (Screenshots)
Các bằng chứng triển khai được lưu trữ trong thư mục dự án:
- [Giao diện điều khiển Railway (Dashboard)](file:///c:/code/VinUni/batch02-day12_cloud_infras_and_deployment/screenshots/running.png)
- [Kiểm tra hoạt động qua logs live (Service Logs)](file:///c:/code/VinUni/batch02-day12_cloud_infras_and_deployment/screenshots/health_check.png)
