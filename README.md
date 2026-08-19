# คู่มือการติดตั้งและใช้งาน — AI Service: สร้างคำอธิบายสินค้า

ระบบนี้ประกอบด้วย 2 ส่วน:

1. **Backend** (`app.py`) — FastAPI server ที่รับชื่อสินค้า + คีย์เวิร์ด แล้วส่งให้ AI (ผ่าน Ollama) สร้างคำอธิบายสินค้า
2. **Frontend** (`index.html`) — หน้าเว็บฟอร์มธรรมดา (static HTML) ที่เรียก Backend ผ่าน API

```
project/
├── app.py
├── requirements.txt
├── .env                  ← สร้างเองจาก _env.example
├── prompts/
│   └── product_description.txt
└── index.html
```

⚠️ **สำคัญ**: โค้ดใน `app.py` โหลด system prompt จาก `prompts/product_description.txt` (บรรทัด `PROMPT_PATH = Path(__file__).parent / "prompts" / "product_description.txt"`) ดังนั้นต้องสร้างโฟลเดอร์ `prompts/` แล้ววางไฟล์ `product_description.txt` ไว้ข้างใน — วางไว้ระดับเดียวกับ `app.py` เฉยๆ จะหาไม่เจอและ server จะไม่ยอมสตาร์ท

---

## 1. สิ่งที่ต้องมีก่อนติดตั้ง

| อย่าง | เวอร์ชันแนะนำ | ตรวจสอบด้วย |
|---|---|---|
| Python | 3.10+ | `python3 --version` |
| Ollama | ล่าสุด | `ollama --version` |
| พื้นที่ดิสก์ | ≥ 8 GB (สำหรับโมเดล) | — |

---

## 2. ติดตั้ง Ollama และโมเดล

1. ติดตั้ง Ollama จาก https://ollama.com (มีให้ทั้ง macOS / Windows / Linux)
2. ดึงโมเดลที่ระบุใน config (ค่า default คือ `qwen3:8b`):
   ```bash
   ollama pull qwen3:8b
   ```
3. เช็คว่า Ollama รันอยู่ (ปกติจะรันอัตโนมัติหลังติดตั้ง เป็น service ที่พอร์ต `11434`):
   ```bash
   curl http://localhost:11434
   ```
   ถ้าไม่ได้รัน ให้สั่ง `ollama serve`

---

## 3. ติดตั้ง Backend (Python / FastAPI)

1. สร้างและเปิดใช้งาน virtual environment
   ```bash
   python3 -m venv venv
   source venv/bin/activate        # Windows: venv\Scripts\activate
   ```
2. ติดตั้ง dependencies
   ```bash
   pip install -r requirements.txt
   ```
3. คัดลอกไฟล์ env
   ```bash
   cp _env.example .env
   ```
4. แก้ไฟล์ `.env` ให้เป็นค่าจริง — **ห้ามใช้ค่า default ที่ให้มา** เพราะ `app.py` จะเช็คและปฏิเสธการสตาร์ทถ้ายังเป็นค่า default:

   | ตัวแปร | ความหมาย | วิธีตั้งค่า |
   |---|---|---|
   | `OLLAMA_BASE_URL` | ที่อยู่ของ Ollama | ปกติปล่อย `http://localhost:11434/v1` ไว้ได้เลยถ้ารันเครื่องเดียวกัน |
   | `MODEL_NAME` | ชื่อโมเดลที่ pull ไว้ | เช่น `qwen3:8b` |
   | `API_KEY` | รหัสลับสำหรับยืนยันตัวตนทุก request (header `X-API-Key`) | สร้างด้วย `python -c "import secrets; print(secrets.token_urlsafe(32))"` แล้วเอาค่าที่ได้มาใส่ |
   | `ALLOWED_ORIGINS` | origin ที่อนุญาตให้เรียก API (CORS) | ใส่ URL ของหน้าเว็บที่จะโฮสต์ `index.html` จริง เช่น `https://yourdomain.com` (คั่นด้วย comma ถ้ามีหลาย origin) |
   | `RATE_LIMIT` | จำกัด request ต่อ IP | ค่า default `10/minute` ปรับได้ตามโหลดที่คาดไว้ |

5. วาง `product_description.txt` ไว้ในโฟลเดอร์ `prompts/`:
   ```bash
   mkdir -p prompts
   mv product_description.txt prompts/
   ```
6. รัน server
   ```bash
   python app.py
   ```
   หรือใช้ uvicorn ตรงๆ (แนะนำสำหรับ production เพราะคุมจำนวน worker ได้):
   ```bash
   uvicorn app:app --host 0.0.0.0 --port 8000
   ```
   ถ้าตั้งค่าถูกต้อง จะเห็น log: `Starting FastAPI server on http://0.0.0.0:8000`

---

## 4. เชื่อม Frontend เข้ากับ Backend

เปิดไฟล์ `index.html` แล้วแก้ค่าใน `CONFIG` (อยู่ใน `<script>` ท้ายไฟล์) ให้ตรงกับที่ตั้งไว้ใน `.env`:

```js
const CONFIG = {
    API_BASE_URL: "http://localhost:8000",   // ← เปลี่ยนเป็น URL จริงของ backend
    API_KEY: "changeme-generate-a-real-secret", // ← ต้องตรงกับ API_KEY ใน .env
};
```

จากนั้นเปิด `index.html` ด้วยเบราว์เซอร์ได้เลย (หรือรันผ่าน static server เช่น `python -m http.server 5500`) แล้วลองกรอกฟอร์ม กดปุ่ม "Gen เนื้อหาด้วย AI"

> ⚠️ **ข้อควรระวังเรื่องความปลอดภัย**: โค้ดในไฟล์เตือนไว้แล้วว่านี่เป็น static-HTML demo — การฝัง `API_KEY` ไว้ในไฟล์ JS ที่รันบน browser ตรงๆ หมายความว่าใครก็ตามที่เปิด "View Source" จะเห็น key ได้ทันที **ไม่เหมาะกับ production จริง** ถ้าจะขึ้นใช้งานจริงควรทำ backend ของตัวเองเป็นตัวกลาง (proxy) ที่เก็บ `API_KEY` ไว้ฝั่งเซิร์ฟเวอร์ แล้วให้ browser เรียกมาที่ proxy แทน

---

## 5. ทดสอบ API ด้วย curl

```bash
curl -X POST http://localhost:8000/api/generate-caption \
  -H "X-API-Key: YOUR_API_KEY" \
  -F "product_name=กระเป๋าหนังสะพายข้าง" \
  -F "keywords=กระเป๋าหนังแท้, มินิมอล, จุของได้เยอะ" \
  -F "goal=social"
```

ผลลัพธ์ที่ควรได้ (ตัวอย่าง):
```json
{"success": true, "caption": "✨ ...\n...\n#..."}
```

### รหัส error ที่พบได้บ่อย
| HTTP Status | สาเหตุ | วิธีแก้ |
|---|---|---|
| 401 | `X-API-Key` ไม่ตรงหรือไม่ได้ส่งมา | เช็คว่า header ตรงกับ `.env` |
| 422 | ไม่ได้ส่ง `product_name` หรือยาวเกิน 200 ตัวอักษร | เช็คข้อมูลที่ส่งใน form |
| 429 | เกิน rate limit | รอตามเวลาที่กำหนด หรือปรับ `RATE_LIMIT` |
| 503 | เชื่อมต่อ Ollama ไม่ได้ | เช็คว่า `ollama serve` รันอยู่ และ `OLLAMA_BASE_URL` ถูกต้อง |
| 504 | Ollama ตอบช้าเกินไป (timeout 60 วิ) | เครื่องอาจสเปกไม่พอสำหรับโมเดลนี้ ลองโมเดลเล็กลงหรือเพิ่ม timeout ในโค้ด |
| 502 | โมเดลตอบกลับมาว่างเปล่า | ลองใหม่ หรือเช็ค prompt/โมเดล |
| 500 | error อื่นๆ ที่ไม่คาดคิด | ดู log ฝั่ง server (`logger.exception`) |

---

## 6. Deploy ขึ้น production (แนวทางแนะนำ)

### แบบ systemd (Linux server)
สร้างไฟล์ `/etc/systemd/system/ai-service.service`:
```ini
[Unit]
Description=AI Service - Product Description Generator
After=network.target

[Service]
User=youruser
WorkingDirectory=/path/to/project
Environment="PATH=/path/to/project/venv/bin"
ExecStart=/path/to/project/venv/bin/uvicorn app:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now ai-service
sudo systemctl status ai-service
```

### วางไว้หลัง Nginx (reverse proxy + HTTPS)
```nginx
server {
    listen 443 ssl;
    server_name api.yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```
แล้วอัปเดต `ALLOWED_ORIGINS` ใน `.env` และ `API_BASE_URL` ใน `index.html` ให้เป็น `https://api.yourdomain.com`

### เช็คลิสต์ก่อนขึ้น production
- [ ] เปลี่ยน `API_KEY` เป็นค่าที่สุ่มใหม่ ไม่ใช้ค่า default
- [ ] ตั้ง `ALLOWED_ORIGINS` เป็นโดเมนจริงเท่านั้น (ไม่ใช้ `*`)
- [ ] เปิด HTTPS (ผ่าน Nginx/Caddy หรือ reverse proxy อื่น) — อย่าเปิด API ตรงๆ แบบ HTTP
- [ ] ปรับ `RATE_LIMIT` ให้เหมาะกับโหลดจริง
- [ ] อย่าฝัง `API_KEY` ไว้ใน `index.html` ที่เป็น public — ทำ proxy backend คั่นกลาง (ดูข้อ 4)
- [ ] ตรวจว่าเครื่อง server มี RAM/GPU พอสำหรับรันโมเดลใน Ollama (`qwen3:8b` ต้องการ RAM ประมาณ 8 GB+)
- [ ] ตั้ง log rotation ถ้าจะรันระยะยาว

---

## 7. วิธีใช้งานหน้าเว็บ (สำหรับผู้ใช้ทั่วไป)

1. เปิดหน้าเว็บ "สร้างคำอธิบายสินค้า"
2. กรอก **ชื่อสินค้า** (จำเป็น เช่น "กระเป๋าหนังสะพายข้าง")
3. กรอก **คีย์เวิร์ด SEO** (ไม่บังคับ คั่นด้วยจุลภาค เช่น "กระเป๋าหนังแท้, มินิมอล")
4. เลือก **เป้าหมายของข้อความ**:
   - **โซเชียลมีเดีย** — สั้น กระชับ มีอีโมจิ เหมาะโพสต์ Facebook/IG/Line
   - **เว็บไซต์** — ทางการ ละเอียด 2-3 ย่อหน้า ไม่มีอีโมจิ เหมาะหน้าสินค้าบนเว็บ
5. กดปุ่ม **"Gen เนื้อหาด้วย AI"** รอผลลัพธ์ทางขวา (ปกติไม่กี่วินาทีถึงไม่กี่สิบวินาที ขึ้นกับสเปกเครื่อง)
6. กด **"คัดลอกข้อความ"** เพื่อคัดลอกไปใช้ต่อ หรือกด **"สร้างใหม่"** เพื่อ gen เวอร์ชันใหม่

---

## 8. คำถามที่พบบ่อย (FAQ)

**Q: server ไม่ยอมสตาร์ท ขึ้น error "ต้องตั้งค่า API_KEY"**
A: ยังไม่ได้แก้ `.env` หรือยังใช้ค่า `changeme-generate-a-real-secret` อยู่

**Q: เปิดหน้าเว็บแล้วกด gen ไม่ได้ผล ขึ้น "เชื่อมต่อ API ไม่สำเร็จ"**
A: เช็คว่า backend รันอยู่จริงที่พอร์ต 8000, และ `API_BASE_URL` ใน `index.html` ตรงกับที่ backend รันอยู่

**Q: อยากเปลี่ยนโมเดล AI**
A: `ollama pull <ชื่อโมเดล>` แล้วแก้ `MODEL_NAME` ใน `.env` แล้ว restart server

**Q: อยากแก้โทนของคำอธิบายสินค้า**
A: แก้ที่ `prompts/product_description.txt` ได้โดยตรง ไม่ต้องแตะโค้ด — restart server หลังแก้เพื่อให้โหลด prompt ใหม่
