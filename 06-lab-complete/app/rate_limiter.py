import time
import logging
from collections import defaultdict, deque
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
        logger.info("Rate Limiter connected to Redis successfully.")
    except Exception as e:
        logger.warning(f"Rate Limiter failed to connect to Redis: {e}. Falling back to in-memory.")

# Bộ lưu trữ dự phòng in-memory
_rate_windows: dict[str, deque] = defaultdict(deque)

def check_rate_limit(user_id: str):
    """
    Kiểm tra tần suất truy cập của client dựa trên API key bucket (user_id).
    Sử dụng giải thuật Sliding Window với Redis ZSET hoặc Python deque.
    """
    now = time.time()
    limit = settings.rate_limit_per_minute

    if USE_REDIS:
        key = f"ratelimit:{user_id}"
        pipe = r.pipeline()
        
        # Loại bỏ các logs request quá 60s trước
        pipe.zremrangebyscore(key, 0, now - 60)
        # Lấy số lượng request trong 60s qua
        pipe.zcard(key)
        
        _, count = pipe.execute()
        
        if count >= limit:
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded: {limit} req/min",
                headers={"Retry-After": "60"},
            )
            
        # Lưu request mới và set TTL
        pipe.zadd(key, {str(now): now})
        pipe.expire(key, 60)
        pipe.execute()
    else:
        window = _rate_windows[user_id]
        # Loại bỏ timestamps cũ ngoài window 60s
        while window and window[0] < now - 60:
            window.popleft()
            
        if len(window) >= limit:
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded: {limit} req/min",
                headers={"Retry-After": "60"},
            )
        window.append(now)
