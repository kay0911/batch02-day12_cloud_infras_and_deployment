import time
import logging
from fastapi import HTTPException
import redis
from app.config import settings

logger = logging.getLogger(__name__)

# Kết nối Redis nếu cấu hình khả dụng
USE_REDIS = False
r = None
if settings.redis_url:
    try:
        r = redis.from_url(settings.redis_url, decode_responses=True)
        r.ping()
        USE_REDIS = True
        logger.info("Cost Guard connected to Redis successfully.")
    except Exception as e:
        logger.warning(f"Cost Guard failed to connect to Redis: {e}. Falling back to in-memory.")

# Các biến lưu trữ dự phòng in-memory
_memory_daily_cost: dict[str, float] = {}
_memory_monthly_cost: dict[str, float] = {}
_memory_reset_day = time.strftime("%Y-%m-%d")
_memory_reset_month = time.strftime("%Y-%m")

def check_and_record_cost(user_id: str, input_tokens: int, output_tokens: int):
    """
    Ước tính và ghi nhận chi phí gọi LLM theo ngày và theo tháng của từng user.
    Ngăn chặn cuộc gọi API nếu vượt quá daily_budget_usd hoặc monthly_budget ($10.0).
    """
    global _memory_reset_day, _memory_reset_month
    
    now_day = time.strftime("%Y-%m-%d")
    now_month = time.strftime("%Y-%m")
    
    # Tính chi phí dựa trên token thực tế (GPT-4o-mini rates)
    cost = (input_tokens / 1000) * 0.00015 + (output_tokens / 1000) * 0.0006

    if USE_REDIS:
        day_key = f"budget:day:{user_id}:{now_day}"
        month_key = f"budget:month:{user_id}:{now_month}"
        
        # 1. Kiểm tra ngân sách tháng (Giới hạn cứng $10.0/tháng)
        monthly_cost = float(r.get(month_key) or 0.0)
        if monthly_cost + cost > 10.0:
            raise HTTPException(
                status_code=402,
                detail=f"Monthly budget exceeded: $10.0 limit. Spent: ${monthly_cost:.4f}",
            )
            
        # 2. Kiểm tra ngân sách ngày
        daily_cost = float(r.get(day_key) or 0.0)
        if daily_cost + cost > settings.daily_budget_usd:
            raise HTTPException(
                status_code=503,
                detail=f"Daily budget exhausted: ${settings.daily_budget_usd} limit. Try again tomorrow.",
            )
            
        # 3. Cộng dồn chi phí mới
        pipe = r.pipeline()
        pipe.incrbyfloat(day_key, cost)
        pipe.expire(day_key, 2 * 24 * 3600)  # TTL 2 ngày
        pipe.incrbyfloat(month_key, cost)
        pipe.expire(month_key, 32 * 24 * 3600) # TTL 32 ngày
        pipe.execute()
        
        logger.info(f"Cost Guard (Redis): user={user_id} added=${cost:.5f} daily=${daily_cost + cost:.4f} monthly=${monthly_cost + cost:.4f}")
    else:
        # Xử lý reset theo ngày/tháng trong bộ nhớ cục bộ
        if now_day != _memory_reset_day:
            _memory_daily_cost.clear()
            _memory_reset_day = now_day
        if now_month != _memory_reset_month:
            _memory_monthly_cost.clear()
            _memory_reset_month = now_month
            
        monthly_cost = _memory_monthly_cost.get(user_id, 0.0)
        if monthly_cost + cost > 10.0:
            raise HTTPException(
                status_code=402,
                detail=f"Monthly budget exceeded: $10.0 limit. Spent: ${monthly_cost:.4f}",
            )
            
        daily_cost = _memory_daily_cost.get(user_id, 0.0)
        if daily_cost + cost > settings.daily_budget_usd:
            raise HTTPException(
                status_code=503,
                detail=f"Daily budget exhausted: ${settings.daily_budget_usd} limit. Try again tomorrow.",
            )
            
        _memory_daily_cost[user_id] = daily_cost + cost
        _memory_monthly_cost[user_id] = monthly_cost + cost
        
        logger.info(f"Cost Guard (In-Memory): user={user_id} added=${cost:.5f} daily=${daily_cost + cost:.4f} monthly=${monthly_cost + cost:.4f}")
