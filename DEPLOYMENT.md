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
**macOS / Linux:**
```bash
curl -X POST https://testrailway-production-6eb5.up.railway.app/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Hello"}'
```
**Windows PowerShell:**
```powershell
# Dùng curl.exe (không dùng alias curl)
curl.exe -X POST https://testrailway-production-6eb5.up.railway.app/ask -H "Content-Type: application/json" -d '{\"question\": \"Hello\"}'
```
**Expected Response:** `401 Unauthorized`

### 3. API Test (Successful request with API Key)
**macOS / Linux:**
```bash
curl -X POST https://testrailway-production-6eb5.up.railway.app/ask \
  -H "X-API-Key: your-secret-api-key" \
  -H "Content-Type: application/json" \
  -d '{"question": "What is deployment?"}'
```
**Windows PowerShell:**
```powershell
# Cách 1: Sử dụng curl.exe trực tiếp
curl.exe -X POST https://testrailway-production-6eb5.up.railway.app/ask -H "X-API-Key: your-secret-api-key" -H "Content-Type: application/json" -d '{\"question\": \"What is deployment?\"}'

# Cách 2: Sử dụng Invoke-RestMethod của PowerShell
Invoke-RestMethod -Uri https://testrailway-production-6eb5.up.railway.app/ask -Method Post -ContentType "application/json" -Headers @{"X-API-Key"="your-secret-api-key"} -Body '{"question":"What is deployment?"}'
```
**Expected Response:**
```json
{
  "question": "What is deployment?",
  "answer": "This is a mock response from LLM for prompt: What is deployment?",
  "model": "gemini-3.1-flash-lite",
  "timestamp": "2026-06-12T07:41:00Z"
}
```

### 4. Rate Limiting Test (Exceeding 20 req/min)
**macOS / Linux:**
```bash
for i in {1..25}; do 
  curl -H "X-API-Key: your-secret-api-key" \
       -X POST https://testrailway-production-6eb5.up.railway.app/ask \
       -H "Content-Type: application/json" \
       -d '{"question": "Hello"}'
done
```
**Windows PowerShell:**
```powershell
for ($i=1; $i -le 25; $i++) {
  curl.exe -H "X-API-Key: your-secret-api-key" -X POST https://testrailway-production-6eb5.up.railway.app/ask -H "Content-Type: application/json" -d '{\"question\": \"Hello\"}'
}
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
