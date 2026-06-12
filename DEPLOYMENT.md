# Deployment Information

## Public URL
https://testrailway-production-6eb5.up.railway.app/

## Platform
Railway

## Test Commands

### 1. Health Check
```bash
curl https://testrailway-production-6eb5.up.railway.app/health
```
**Expected Response:**
```json
{
  "status": "ok",
  "version": "1.0.0",
  "environment": "production",
  "uptime_seconds": 12.5,
  "total_requests": 0,
  "checks": {
    "llm": "mock"
  },
  "timestamp": "2026-06-12T07:40:00Z"
}
```

### 2. Authentication Test (Failure without API Key)
```bash
curl -X POST https://testrailway-production-6eb5.up.railway.app/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Hello"}'
```
**Expected Response:** `401 Unauthorized`

### 3. API Test (Successful request with API Key)
```bash
curl -X POST https://testrailway-production-6eb5.up.railway.app/ask \
  -H "X-API-Key: your-secret-api-key" \
  -H "Content-Type: application/json" \
  -d '{"question": "What is deployment?"}'
```
**Expected Response:**
```json
{
  "question": "What is deployment?",
  "answer": "This is a mock response from LLM for prompt: What is deployment?",
  "model": "gpt-4o-mini",
  "timestamp": "2026-06-12T07:41:00Z"
}
```

### 4. Rate Limiting Test (Exceeding 20 req/min)
Chạy liên tục nhiều requests bằng vòng lặp:
```bash
for i in {1..25}; do 
  curl -H "X-API-Key: your-secret-api-key" \
       -X POST https://testrailway-production-6eb5.up.railway.app/ask \
       -H "Content-Type: application/json" \
       -d '{"question": "Hello"}'
done
```
**Expected Response:** Trả về `429 Too Many Requests` khi vượt hạn mức.

## Environment Variables Set
- `PORT`: 8000 (Cổng kết nối dịch vụ)
- `ENVIRONMENT`: `production`
- `AGENT_API_KEY`: `your-secret-api-key` (Dùng để authenticate client)
- `JWT_SECRET`: `supersecretjwtkey` (Dùng để mã hóa/xác thực nếu cần)
- `REDIS_URL`: `redis://...` (Kết nối cơ sở dữ liệu Redis để lưu trữ stateless session history, rate limiting và cost guard)
- `DAILY_BUDGET_USD`: `5.0`
- `RATE_LIMIT_PER_MINUTE`: `20`

## Screenshots
- [Deployment dashboard](file:///c:/code/VinUni/batch02-day12_cloud_infras_and_deployment/screenshots/running.png)
- [Service running (health check)](file:///c:/code/VinUni/batch02-day12_cloud_infras_and_deployment/screenshots/health_check.png)
