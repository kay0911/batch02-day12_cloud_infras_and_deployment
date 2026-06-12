# Day 12 Lab - Mission Answers
**Student Name:** Trần Duy Khánh
**StudentID:** 2A202600592

## Part 1: Localhost vs Production

### Exercise 1.1: Anti-patterns found
Trong file [app.py](file:///c:/code/VinUni/batch02-day12_cloud_infras_and_deployment/01-localhost-vs-production/develop/app.py) của thư mục `develop/`, có 5 vấn đề phản khuôn mẫu (anti-pattern) chính:
1. **Hardcoded API Key & Database URL:** Khóa bí mật (`OPENAI_API_KEY`) và thông tin kết nối cơ sở dữ liệu (`DATABASE_URL`) bị ghi cứng trực tiếp vào mã nguồn. Nếu đẩy lên GitHub public, thông tin bảo mật sẽ bị lộ ngay lập tức.
2. **Thiếu hệ thống cấu hình tập trung (Config Management):** Các biến cấu hình hệ thống như `DEBUG = True` hay `MAX_TOKENS = 500` bị khai báo tĩnh trong file, gây khó khăn khi cần thay đổi theo môi trường mà không sửa code.
3. **Sử dụng lệnh `print()` để log thông tin:** Không sử dụng thư viện logging chuyên nghiệp. Điều này dẫn đến việc ghi đè trực tiếp các thông tin nhạy cảm (như API key) ra Standard Output và không có cấu trúc log rõ ràng để quản lý.
4. **Không có Health Check endpoint:** Thiếu các endpoint `/health` và `/ready`. Khi ứng dụng gặp sự cố hoặc crash, các nền tảng đám mây (Cloud Platforms) hoặc Kubernetes sẽ không phát hiện ra để tự động khởi động lại.
5. **Cấu hình Port và Host cứng:** Gắn cứng host là `"localhost"` và port `8000` cùng với tùy chọn `reload=True`. Khi deploy lên các Cloud Run, Railway, Render, cổng PORT sẽ được cấp phát động. Việc gán cứng localhost sẽ khiến các kết nối từ Internet bên ngoài không truy cập được vào ứng dụng.

### Exercise 1.3: Comparison table

| Feature | Develop | Production | Why Important? |
|---------|---------|------------|----------------|
| **Config** | Hardcode trong code | Đọc từ biến môi trường (Env vars) | Giúp ứng dụng linh hoạt, tuân thủ nguyên tắc 12-factor, dễ dàng thay đổi cấu hình giữa Dev/Staging/Prod mà không cần sửa code. |
| **Secrets** | Lưu trực tiếp dạng string | Đọc qua `os.getenv` | Tránh rò rỉ mã khóa API, mật khẩu Database trên các hệ thống quản lý phiên bản mã nguồn như Git/GitHub. |
| **Port** | Cố định `8000` | Đọc động qua `PORT` env | Các nền tảng đám mây tự động cấp phát cổng ngẫu nhiên và inject qua biến môi trường. |
| **Health Check** | Không hỗ trợ | Có `/health` (Liveness) & `/ready` (Readiness) | Giúp bộ cân bằng tải (Load Balancer) và Cloud Orchestrator kiểm soát vòng đời của ứng dụng và điều phối traffic chính xác. |
| **Shutdown** | Tắt đột ngột (Hard kill) | Graceful shutdown (SIGTERM handler) | Đảm bảo các request đang xử lý dở được hoàn thành và đóng kết nối cơ sở dữ liệu an toàn trước khi tắt dịch vụ. |
| **Logging** | Dùng hàm `print()` | Structured JSON Logging | Giúp dễ dàng tổng hợp, tìm kiếm và phân tích log trên các công cụ chuyên dụng như Loki, ElasticSearch hay Datadog. |

### Câu hỏi thảo luận (Part 1)
1. **Điều gì xảy ra nếu push code chứa API key lên GitHub public:**
   Các bot quét tự động (như GitGuardian) sẽ quét thấy key trong vòng vài giây và key có thể bị kẻ xấu lạm dụng, dẫn đến phát sinh chi phí lớn. Các nhà cung cấp (như OpenAI) thường sẽ tự động khóa (deactivate) key ngay lập tức nếu phát hiện bị rò rỉ.
2. **Tại sao stateless quan trọng khi scale:**
   Stateless đảm bảo rằng bất kỳ instance nào của ứng dụng cũng có thể xử lý bất kỳ request nào mà không cần phụ thuộc vào bộ nhớ cục bộ. Điều này giúp hệ thống dễ dàng mở rộng theo chiều ngang (thêm/bớt container) và thực hiện cập nhật không gián đoạn (rolling updates).
3. **Ý nghĩa thực tế của "dev/prod parity" trong 12-factor:**
   Nghĩa là thu hẹp khoảng cách giữa môi trường develop và production ở mức tối đa (sử dụng cùng phiên bản ngôn ngữ, cùng loại database, cùng thư viện và cách thức cấu hình) nhằm hạn chế lỗi phát sinh do khác biệt môi trường.

---

## Part 2: Docker

### Exercise 2.1: Dockerfile questions
1. **Base image là gì:** `python:3.11` (Bản phân phối Python đầy đủ dựa trên Debian, kích thước khoảng ~1 GB).
2. **Working directory là gì:** `/app` (Thư mục làm việc mặc định được tạo bên trong container).
3. **Tại sao COPY requirements.txt trước:** Để tận dụng cơ chế Docker layer cache. Khi code thay đổi nhưng dependencies giữ nguyên, Docker sẽ bỏ qua bước `pip install` và lấy từ cache giúp giảm thiểu thời gian build image.
4. **CMD vs ENTRYPOINT khác nhau thế nào:**
   - `CMD` định nghĩa câu lệnh mặc định chạy khi container khởi động và có thể bị ghi đè hoàn toàn khi chạy lệnh `docker run <image> <command_moi>`.
   - `ENTRYPOINT` định nghĩa tệp thực thi chính và không thể bị ghi đè một cách dễ dàng, các tham số từ `CMD` hoặc command line sẽ được nối tiếp làm đối số cho `ENTRYPOINT`.

### Exercise 2.3: Image size comparison
- **Develop (Basic - Single-stage):** ~1.01 GB (1010 MB)
- **Production (Advanced - Multi-stage slim):** ~160 MB
- **Difference:** Giảm khoảng **84%** dung lượng đĩa.

*Lý do:* Multi-stage build chỉ copy thư viện đã cài đặt sẵn ở stage builder sang stage runtime sạch (`python:3.11-slim`), loại bỏ hoàn toàn các công cụ biên dịch mã nguồn như `gcc` và bộ nhớ cache tải về của `pip`.

### Câu hỏi thảo luận (Part 2)
1. **Tại sao COPY requirements.txt và cài đặt trước khi COPY code:**
   Để tối ưu hóa Docker Layer Cache. Source code thay đổi rất thường xuyên, trong khi danh sách thư viện (requirements.txt) rất ít khi đổi. Việc này giúp việc build container ở các lần tiếp theo cực kỳ nhanh.
2. **`.dockerignore` nên chứa gì và tại sao `venv/` và `.env` quan trọng:**
   Nên chứa `venv/`, `.env`, `.git`, `.vscode`, `__pycache__`. `venv/` chứa các thư viện cài đặt riêng cho máy host (có thể không tương thích với OS của container), còn `.env` chứa các bí mật không được phép đóng gói vào image để tránh lộ secrets.
3. **Mount volume vào container như thế nào:**
   Sử dụng cờ `-v` hoặc `--volume` khi dùng CLI (ví dụ: `docker run -v /duong/dan/host:/app/data`), hoặc định nghĩa trong khối `volumes` của file `docker-compose.yml`.

---

## Part 3: Cloud Deployment

### Exercise 3.1: Railway deployment
- **URL triển khai public:** `https://testrailway-production-6eb5.up.railway.app/`
- **Screenshot Dashboard:** [screenshots/running.png](file:///c:/code/VinUni/batch02-day12_cloud_infras_and_deployment/screenshots/running.png)

### Câu hỏi thảo luận (Part 3)
1. **Tại sao serverless (Lambda) không phải lúc nào cũng tốt cho AI agent:**
   AI agent thường xử lý các tác vụ tốn nhiều thời gian (LLM response latency) dễ vượt quá timeout của Lambda. Đồng thời, các kết nối dạng truyền phát dữ liệu (Streaming responses/WebSockets) hoạt động không hiệu quả và đắt đỏ trên mô hình serverless.
2. **"Cold start" là gì và ảnh hưởng của nó:**
   Là thời gian trễ khi khởi động một container mới từ trạng thái nghỉ hoàn toàn (idle). Nó khiến người dùng đầu tiên truy cập phải chờ từ 2-10 giây để container khởi động và tải tài nguyên, làm giảm trải nghiệm người dùng (UX).
3. **Khi nào nên upgrade từ Railway lên Cloud Run (GCP):**
   Khi dự án cần khả năng scale lớn tự động về 0 khi không có traffic, cần tích hợp sâu vào hạ tầng bảo mật của Google Cloud (IAM, VPC), hoặc khi traffic tăng cực kỳ lớn cần tối ưu hóa chi phí trên quy mô doanh nghiệp.

---

## Part 4: API Security

### Exercise 4.1-4.3: Test results
- **Gọi API không có API Key (Mong đợi trả về 401):**
  ```json
  {
    "detail": "Invalid or missing API key. Include header: X-API-Key: <key>"
  }
  ```
- **Gọi API với API Key hợp lệ (Mong đợi trả về 200):**
  ```json
  {
    "question": "Hello",
    "answer": "This is a mock response from LLM for prompt: Hello",
    "model": "gpt-4o-mini",
    "timestamp": "2026-06-12T07:40:00Z"
  }
  ```
- **Gọi API vượt quá tần suất cho phép (Rate limit 20 req/min - Mong đợi trả về 429):**
  ```json
  {
    "detail": "Rate limit exceeded: 20 req/min"
  }
  ```

### Exercise 4.4: Cost guard implementation
Giải pháp ngăn chặn vượt ngân sách (Cost Guard) được thiết kế bằng cách sử dụng **Redis** để lưu trữ lịch sử tiêu dùng theo ngày:
- Hệ thống ước tính mã token (input tokens) và token kết quả (output tokens) sau khi gọi LLM mock.
- Tính toán chi phí thực tế theo công thức: `cost = (input_tokens / 1000) * $0.00015 + (output_tokens / 1000) * $0.0006`.
- Trước khi thực thi truy vấn, hệ thống kiểm tra chi phí tích lũy của ngày hôm đó trong Redis. Nếu chi phí vượt quá giới hạn ngày `daily_budget_usd` (mặc định là $5.0), API sẽ lập tức trả về lỗi `503 Service Unavailable / Budget exhausted`.

---

## Part 5: Scaling & Reliability

### Exercise 5.1-5.5: Implementation notes
- **Liveness & Readiness Probes:**
  - `/health`: Trả về `{"status": "ok"}` nhanh chóng để báo hiệu ứng dụng đang hoạt động tốt.
  - `/ready`: Trả về kết quả sau khi kiểm tra trạng thái kết nối đến Redis/Database. Đảm bảo Load Balancer không điều phối traffic vào container chưa kết nối xong tài nguyên.
- **Graceful Shutdown:**
  Khi nhận tín hiệu `SIGTERM` từ môi trường quản lý (Docker/Cloud platform), ứng dụng sẽ chuyển cờ `_is_ready = False` để báo cho Load Balancer ngắt kết nối nhận request mới, đợi 30 giây để các tiến trình request hiện tại xử lý xong trước khi chính thức tắt máy.
- **Stateless Design:**
  Toàn bộ lịch sử cuộc trò chuyện (Conversation history) được đưa ra lưu trữ tập trung tại cơ sở dữ liệu Redis thay vì RAM cục bộ của container. Điều này cho phép mở rộng quy mô (Scale) lên nhiều container phía sau Nginx Load Balancer mà không sợ người dùng bị mất ngữ cảnh hội thoại khi request rơi vào container khác.
