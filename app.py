import logging
import os
import re
from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Form, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from openai import AsyncOpenAI
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

# ==========================================
# 1. โหลด config จาก environment variables
# ==========================================
load_dotenv()

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")
MODEL_NAME = os.environ.get("MODEL_NAME", "qwen3:8b")
API_KEY = os.environ.get("API_KEY")
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]
RATE_LIMIT = os.environ.get("RATE_LIMIT", "10/minute")

if not API_KEY or API_KEY == "changeme-generate-a-real-secret":
    raise RuntimeError(
        "ต้องตั้งค่า API_KEY ใน .env ก่อนรันเซิร์ฟเวอร์ (ห้ามใช้ค่า default)"
    )
if not ALLOWED_ORIGINS:
    raise RuntimeError("ต้องตั้งค่า ALLOWED_ORIGINS ใน .env อย่างน้อย 1 origin")

# ==========================================
# 2. Logging — เพื่อ debug ปัญหาใน production ได้จริง
# ==========================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("ai_service")

# ==========================================
# 3. โหลด system prompt จากไฟล์แยก (แก้ prompt ได้โดยไม่ต้องแตะโค้ด)
# ==========================================
PROMPT_PATH = Path(__file__).parent / "prompts" / "product_description.txt"
try:
    SYSTEM_PROMPT = PROMPT_PATH.read_text(encoding="utf-8")
except FileNotFoundError as exc:
    raise RuntimeError(f"ไม่พบไฟล์ system prompt ที่ {PROMPT_PATH}") from exc

# ==========================================
# 4. ตั้งค่าแอป FastAPI + rate limiter + CORS
# ==========================================
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="AI Service API",
    description="API สำหรับหน้า 'แนะนำคำอธิบายสินค้า' — สร้างคำอธิบายสินค้าด้วย AI จากชื่อสินค้า + คีย์เวิร์ด SEO",
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,  # ระบุ origin จริง ไม่ใช้ "*"
    allow_credentials=False,  # ไม่ได้ใช้ cookie/session จึงไม่จำเป็นต้องเปิด
    allow_methods=["POST"],
    allow_headers=["Content-Type", "X-API-Key"],
)

# ==========================================
# 5. เชื่อมต่อ Ollama แบบ async + timeout (กัน event loop ค้าง)
# ==========================================
client = AsyncOpenAI(
    base_url=OLLAMA_BASE_URL,
    api_key="ollama",
    timeout=httpx.Timeout(60.0, connect=5.0),
)

# ==========================================
# 6. Auth dependency — ตรวจ X-API-Key ทุก request
# ==========================================
async def verify_api_key(x_api_key: str = Header(...)) -> None:
    if x_api_key != API_KEY:
        logger.warning("Rejected request with invalid API key")
        raise HTTPException(status_code=401, detail="Unauthorized")


# ==========================================
# 7. ตัวกรองสำรอง (safety net): โมเดลบางครั้งหลุดกฎที่สั่งไว้ใน prompt
# ==========================================
BANNED_LINE_PREFIXES = ["พาดหัว:", "จุดเด่น:", "สภาพเสื้อ:", "สภาพสินค้า:"]
_CJK_PATTERN = re.compile(r"[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af\u3400-\u4dbf]")
_THINK_PATTERN = re.compile(r"<think>.*?</think>", flags=re.DOTALL)


def clean_caption(text: str) -> str:
    """ตัด <think>, อักษรที่ไม่ใช่ไทย/อังกฤษ และ prefix ต้องห้ามออกจากผลลัพธ์ AI"""
    text = _THINK_PATTERN.sub("", text).strip()
    text = _CJK_PATTERN.sub("", text)

    cleaned_lines = []
    for line in text.split("\n"):
        stripped = line.strip()
        for prefix in BANNED_LINE_PREFIXES:
            if stripped.startswith(prefix):
                stripped = stripped[len(prefix):].strip()
                break
        cleaned_lines.append(stripped)

    return "\n".join(cleaned_lines).strip()


# ==========================================
# 8. Endpoint หลัก
# ==========================================
MAX_PRODUCT_NAME_LEN = 200
MAX_KEYWORDS_LEN = 300


@app.post("/api/generate-caption", dependencies=[Depends(verify_api_key)])
@limiter.limit(RATE_LIMIT)
async def generate_caption(
    request: Request,  # จำเป็นสำหรับ slowapi
    product_name: str = Form(..., min_length=1, max_length=MAX_PRODUCT_NAME_LEN),
    keywords: str = Form("", max_length=MAX_KEYWORDS_LEN),
    goal: str = Form("social"),
):
    goal = goal if goal in ("social", "website") else "social"

    user_text = (
        f"ชื่อสินค้า: {product_name}\n"
        f"คีย์เวิร์ด (SEO Keywords): {keywords or '(ไม่ได้ระบุ)'}\n"
        f"เป้าหมายของข้อความ: {goal}"
    )

    try:
        response = await client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_text},
            ],
            max_tokens=800,
            temperature=0.5,
            extra_body={
                "think": False,
                "options": {"num_ctx": 8192},
            },
        )
    except httpx.ConnectError:
        logger.exception("Cannot connect to Ollama at %s", OLLAMA_BASE_URL)
        raise HTTPException(
            status_code=503, detail="บริการ AI ไม่พร้อมใช้งานชั่วคราว กรุณาลองใหม่อีกครั้ง"
        )
    except httpx.TimeoutException:
        logger.exception("Ollama request timed out")
        raise HTTPException(
            status_code=504, detail="สร้างเนื้อหาใช้เวลานานเกินไป กรุณาลองใหม่อีกครั้ง"
        )
    except Exception:
        logger.exception("Unexpected error calling model")
        raise HTTPException(status_code=500, detail="เกิดข้อผิดพลาดที่ไม่คาดคิด")

    raw_caption = response.choices[0].message.content
    if not raw_caption or not raw_caption.strip():
        logger.error("Model returned empty content for product_name=%r", product_name)
        raise HTTPException(
            status_code=502, detail="AI ไม่สามารถสร้างเนื้อหาได้ กรุณาลองใหม่อีกครั้ง"
        )

    return {"success": True, "caption": clean_caption(raw_caption)}


if __name__ == "__main__":
    import uvicorn

    logger.info("Starting FastAPI server on http://0.0.0.0:8000")
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=False)
