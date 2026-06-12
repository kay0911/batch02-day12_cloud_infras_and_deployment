"""
Production AI Agent — Kết hợp tất cả Day 12 concepts

Checklist:
  ✅ Config từ environment (12-factor)
  ✅ Structured JSON logging
  ✅ API Key authentication (via app.auth)
  ✅ Rate limiting (via app.rate_limiter)
  ✅ Cost guard (via app.cost_guard)
  ✅ Input validation (Pydantic)
  ✅ Health check + Readiness probe
  ✅ Graceful shutdown
  ✅ Security headers
  ✅ CORS
  ✅ Error handling
"""
import os
import time
import signal
import logging
import json
from datetime import datetime, timezone
from contextlib import asynccontextmanager
import urllib.request
import urllib.error

from fastapi import FastAPI, HTTPException, Security, Depends, Request, Response
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn
import redis

from app.config import settings
from app.auth import verify_api_key
from app.rate_limiter import check_rate_limit
from app.cost_guard import check_and_record_cost
from app.skills import GEMINI_TOOLS, execute_tool

# Mock LLM (thay bằng OpenAI/Anthropic khi có API key)
from utils.mock_llm import ask as llm_ask

# ─────────────────────────────────────────────────────────
# Logging — JSON structured
# ─────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format='{"ts":"%(asctime)s","lvl":"%(levelname)s","msg":"%(message)s"}',
)
logger = logging.getLogger(__name__)

START_TIME = time.time()
_is_ready = False
_request_count = 0
_error_count = 0

# ─────────────────────────────────────────────────────────
# Redis Session Storage cho Conversation History (Stateless)
# ─────────────────────────────────────────────────────────
USE_REDIS = False
_redis = None
if settings.redis_url:
    try:
        _redis = redis.from_url(settings.redis_url, decode_responses=True)
        _redis.ping()
        USE_REDIS = True
        logger.info("Stateless history connected to Redis successfully.")
    except Exception as e:
        logger.warning(f"Stateless history failed to connect to Redis: {e}. Falling back to in-memory.")

_memory_store = {}

def load_history(user_id: str) -> list:
    """Tải lịch sử chat của user từ Redis hoặc bộ nhớ tạm."""
    if USE_REDIS:
        history = _redis.get(f"history:{user_id}")
        return json.loads(history) if history else []
    return _memory_store.get(f"history:{user_id}", [])

def save_history(user_id: str, history: list, ttl_seconds: int = 3600):
    """Lưu lịch sử chat của user vào Redis hoặc bộ nhớ tạm (Giới hạn tối đa 20 tin nhắn)."""
    if len(history) > 20:
        history = history[-20:]
    if USE_REDIS:
        _redis.setex(f"history:{user_id}", ttl_seconds, json.dumps(history))
    else:
        _memory_store[f"history:{user_id}"] = history

def call_llm(question: str, history: list) -> str:
    """Gọi Gemini API nếu có GEMINI_API_KEY, ngược lại dùng mock LLM."""
    if settings.gemini_api_key:
        # Chuyển đổi định dạng history cho Gemini API
        contents = []
        for msg in history:
            role = "model" if msg["role"] == "assistant" else "user"
            contents.append({
                "role": role,
                "parts": [{"text": msg["content"]}]
            })
        
        max_turns = 4
        for turn in range(max_turns):
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.llm_model}:generateContent?key={settings.gemini_api_key}"
            headers = {"Content-Type": "application/json"}
            body = {
                "contents": contents,
                "tools": GEMINI_TOOLS
            }
            
            req = urllib.request.Request(
                url,
                data=json.dumps(body).encode("utf-8"),
                headers=headers,
                method="POST"
            )
            try:
                with urllib.request.urlopen(req, timeout=15) as response:
                    res_body = response.read().decode("utf-8")
                    res_data = json.loads(res_body)
                    
                    candidate = res_data.get("candidates", [{}])[0]
                    content = candidate.get("content", {})
                    parts = content.get("parts", [{}])
                    first_part = parts[0]
                    
                    # Nếu Gemini yêu cầu gọi tool
                    if "functionCall" in first_part:
                        fn_call = first_part["functionCall"]
                        name = fn_call["name"]
                        args = fn_call.get("args", {})
                        
                        logger.info(f"Gemini requested tool call: {name} with args {args}")
                        
                        # Chạy tool cục bộ
                        tool_res = execute_tool(name, args)
                        
                        # Thêm kết quả của tool vào chuỗi hội thoại gửi tiếp cho Gemini
                        contents.append({
                            "role": "model",
                            "parts": [
                                {
                                    "functionCall": {
                                        "name": name,
                                        "args": args
                                    }
                                }
                            ]
                        })
                        contents.append({
                            "role": "function",
                            "parts": [
                                {
                                    "functionResponse": {
                                        "name": name,
                                        "response": tool_res
                                    }
                                }
                            ]
                        })
                        continue
                    
                    elif "text" in first_part:
                        return first_part["text"]
                    else:
                        raise ValueError(f"Unexpected part format from Gemini: {first_part}")
                        
            except urllib.error.HTTPError as e:
                error_msg = e.read().decode("utf-8")
                logger.error(f"Gemini API HTTP Error: {e.code} - {error_msg}")
                raise HTTPException(status_code=e.code, detail=f"Gemini API Error: {error_msg}")
            except Exception as e:
                logger.error(f"Gemini API Connection Error: {e}")
                raise HTTPException(status_code=500, detail=f"Failed to connect to Gemini API: {str(e)}")
                
        raise HTTPException(status_code=500, detail="Gemini tool call loop limit exceeded")
    else:
        return llm_ask(question)

# ─────────────────────────────────────────────────────────
# Lifespan
# ─────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _is_ready
    logger.info(json.dumps({
        "event": "startup",
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
    }))
    time.sleep(0.1)  # simulate init
    _is_ready = True
    logger.info(json.dumps({"event": "ready"}))

    yield

    _is_ready = False
    logger.info(json.dumps({"event": "shutdown"}))

# ─────────────────────────────────────────────────────────
# App Setup
# ─────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key"],
)

@app.middleware("http")
async def request_middleware(request: Request, call_next):
    global _request_count, _error_count
    start = time.time()
    _request_count += 1
    try:
        response: Response = await call_next(request)
        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        if "server" in response.headers:
            del response.headers["server"]
        duration = round((time.time() - start) * 1000, 1)
        logger.info(json.dumps({
            "event": "request",
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "ms": duration,
        }))
        return response
    except Exception as e:
        _error_count += 1
        raise

# ─────────────────────────────────────────────────────────
# Models
# ─────────────────────────────────────────────────────────
class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000,
                          description="Your question for the agent")
    user_id: str | None = Field(default=None, description="Optional identifier for stateless session tracking")

class AskResponse(BaseModel):
    question: str
    answer: str
    model: str
    timestamp: str

# ─────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────

@app.get("/", tags=["Info"])
def root(request: Request):
    accept = request.headers.get("accept", "")
    if "text/html" in accept:
        static_file = os.path.join(os.path.dirname(__file__), "static", "index.html")
        if os.path.exists(static_file):
            with open(static_file, "r", encoding="utf-8") as f:
                return HTMLResponse(content=f.read(), status_code=200)
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "endpoints": {
            "ask": "POST /ask (requires X-API-Key)",
            "health": "GET /health",
            "ready": "GET /ready",
            "metrics": "GET /metrics (requires X-API-Key)"
        },
    }

@app.post("/ask", response_model=AskResponse, tags=["Agent"])
async def ask_agent(
    body: AskRequest,
    request: Request,
    _key: str = Depends(verify_api_key),
):
    """
    Send a question to the AI agent.

    **Authentication:** Include header `X-API-Key: <your-key>`
    """
    # Lấy định danh người dùng (mặc định lấy 8 ký tự đầu của API Key nếu client không gửi user_id)
    user_id = body.user_id or _key[:8]

    # Kiểm tra Rate Limit (Sliding Window qua Redis)
    check_rate_limit(user_id)

    # Ước lượng và kiểm tra chi phí token đầu vào
    input_tokens = len(body.question.split()) * 2
    check_and_record_cost(user_id, input_tokens, 0)

    logger.info(json.dumps({
        "event": "agent_call",
        "user_id": user_id,
        "q_len": len(body.question),
        "client": str(request.client.host) if request.client else "unknown",
    }))

    # Tải lịch sử cuộc hội thoại (Stateless)
    history = load_history(user_id)
    history.append({"role": "user", "content": body.question})

    # Gọi mô hình LLM xử lý câu hỏi
    answer = call_llm(body.question, history)

    # Lưu kết quả trả lời vào lịch sử cuộc trò chuyện
    history.append({"role": "assistant", "content": answer})
    save_history(user_id, history)

    # Ước lượng và cộng dồn chi phí token đầu ra
    output_tokens = len(answer.split()) * 2
    check_and_record_cost(user_id, 0, output_tokens)

    return AskResponse(
        question=body.question,
        answer=answer,
        model=settings.llm_model,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )

@app.get("/health", tags=["Operations"])
def health():
    """Liveness probe. Platform restarts container if this fails."""
    status = "ok"
    checks = {
        "llm": "gemini" if settings.gemini_api_key else ("mock" if not settings.openai_api_key else "openai")
    }
    return {
        "status": status,
        "version": settings.app_version,
        "environment": settings.environment,
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "total_requests": _request_count,
        "checks": checks,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

@app.get("/ready", tags=["Operations"])
def ready():
    """Readiness probe. Load balancer stops routing here if not ready."""
    if not _is_ready:
        raise HTTPException(503, "Not ready")
    if USE_REDIS:
        try:
            _redis.ping()
        except Exception:
            raise HTTPException(503, "Redis connection failed")
    return {"ready": True}

@app.get("/metrics", tags=["Operations"])
def metrics(_key: str = Depends(verify_api_key)):
    """Basic metrics (protected)."""
    # Lấy thông tin chi phí tổng quan tích lũy trong ngày
    daily_cost_usd = 0.0
    if USE_REDIS:
        # Tổng hợp tất cả keys daily budget trong Redis để ước tính tổng chi phí (chỉ phục vụ demo)
        keys = _redis.keys("budget:day:*")
        for k in keys:
            daily_cost_usd += float(_redis.get(k) or 0.0)
    
    return {
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "total_requests": _request_count,
        "error_count": _error_count,
        "daily_cost_usd": round(daily_cost_usd, 4),
        "daily_budget_usd": settings.daily_budget_usd,
    }

# ─────────────────────────────────────────────────────────
# Graceful Shutdown
# ─────────────────────────────────────────────────────────
def _handle_signal(signum, _frame):
    logger.info(json.dumps({"event": "signal", "signum": signum}))

signal.signal(signal.SIGTERM, _handle_signal)

if __name__ == "__main__":
    logger.info(f"Starting {settings.app_name} on {settings.host}:{settings.port}")
    logger.info(f"API Key: {settings.agent_api_key[:4]}****")
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        timeout_graceful_shutdown=30,
    )
