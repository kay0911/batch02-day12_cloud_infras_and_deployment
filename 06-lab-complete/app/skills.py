import time
import psutil
import logging

logger = logging.getLogger(__name__)
START_TIME = time.time()

# Danh sách các công cụ khai báo gửi cho Gemini
GEMINI_TOOLS = [
    {
        "function_declarations": [
            {
                "name": "get_system_status",
                "description": "Returns current server CPU usage, memory usage, and system uptime. Useful when the user asks about system performance, resource consumption, or how the server is doing.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {}
                }
            },
            {
                "name": "calculate",
                "description": "Safely evaluates mathematical expressions. Useful for answering mathematical queries.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "expression": {
                            "type": "STRING",
                            "description": "The math expression to evaluate, e.g., '12 * (34 + 5)'"
                        }
                    },
                    "required": ["expression"]
                }
            },
            {
                "name": "get_weather",
                "description": "Get mock weather forecast for a location. Useful when the user asks about the weather in a specific city.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "location": {
                            "type": "STRING",
                            "description": "The city and state/country, e.g. 'Hanoi, Vietnam'"
                        }
                    },
                    "required": ["location"]
                }
            }
        ]
    }
]

def get_system_status() -> dict:
    try:
        cpu_percent = psutil.cpu_percent(interval=0.05)
        memory = psutil.virtual_memory()
        uptime = round(time.time() - START_TIME, 1)
        return {
            "cpu_usage_percent": cpu_percent,
            "memory_used_mb": round(memory.used / (1024 * 1024), 1),
            "memory_total_mb": round(memory.total / (1024 * 1024), 1),
            "memory_usage_percent": memory.percent,
            "server_uptime_seconds": uptime,
            "status": "healthy"
        }
    except Exception as e:
        logger.error(f"Error reading system status: {e}")
        return {"error": f"Failed to get system status: {str(e)}"}

def calculate(expression: str) -> dict:
    # Chỉ cho phép các ký tự an toàn
    allowed = "0123456789+-*/(). "
    if not expression or not all(c in allowed for c in expression):
        return {"error": "Invalid characters in math expression. Only digits and standard operators (+,-,*,/,parentheses) are allowed."}
    try:
        # Thực thi eval an toàn bằng cách bỏ các builtins nhạy cảm
        result = eval(expression, {"__builtins__": None}, {})
        return {"expression": expression, "result": float(result)}
    except Exception as e:
        return {"error": f"Failed to evaluate expression: {str(e)}"}

def get_weather(location: str) -> dict:
    loc_lower = location.lower()
    if "hanoi" in loc_lower or "hà nội" in loc_lower:
        return {"location": location, "temperature_c": 28, "condition": "Sunny with clouds", "humidity": 75}
    elif "saigon" in loc_lower or "hồ chí minh" in loc_lower or "hcm" in loc_lower:
        return {"location": location, "temperature_c": 32, "condition": "Rainy and humid", "humidity": 85}
    elif "da nang" in loc_lower or "đà nẵng" in loc_lower:
        return {"location": location, "temperature_c": 26, "condition": "Breezy and cloudy", "humidity": 70}
    else:
        return {"location": location, "temperature_c": 22, "condition": "Clear skies", "humidity": 60}

def execute_tool(name: str, args: dict) -> dict:
    logger.info(f"Executing local tool '{name}' with args: {args}")
    if name == "get_system_status":
        return get_system_status()
    elif name == "calculate":
        return calculate(args.get("expression", ""))
    elif name == "get_weather":
        return get_weather(args.get("location", ""))
    else:
        return {"error": f"Tool '{name}' not found"}
