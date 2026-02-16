from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
from pydantic import BaseModel
import httpx
import os
import time

# --- ГЛОБАЛЬНЫЙ КЛИЕНТ ---
http_client = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global http_client
    http_client = httpx.AsyncClient()
    yield
    await http_client.aclose()


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def read_root():
    if os.path.exists("index.html"): return FileResponse("index.html")
    return {"error": "index.html not found"}


# --- CONFIG ---
URL = "https://kgxvjlsojgkkhdaftncg.supabase.co"
KEY = "sb_publishable_2jhUvmgAKa-edfQyKSWlbA_nKxG65O0"
HEADERS = {
    "apikey": KEY,
    "Authorization": f"Bearer {KEY}",
    "Prefer": "return=representation"
}


# --- MODELS ---
class LoginData(BaseModel):
    username: str
    password: str


class RegData(BaseModel):
    username: str
    password: str
    first_name: str
    gender: str
    bio: str
    avatar_url: str
    secret_key: str


class ResetData(BaseModel):
    username: str
    secret_key: str
    new_password: str


class UpdateData(BaseModel):
    username: str
    first_name: str
    bio: str
    avatar_url: str


class LikeData(BaseModel):
    from_email: str
    to_email: str


class MessageData(BaseModel):
    sender_email: str
    receiver_email: str
    text: str


class AdminDecision(BaseModel):
    target_username: str
    action: str  # "approve" или "reject"


# --- API HELPERS ---
async def sb_request(method, endpoint, data=None):
    headers = HEADERS.copy()
    headers["Content-Type"] = "application/json"
    url = f"{URL}/rest/v1/{endpoint}"
    try:
        if method == "GET":
            r = await http_client.get(url, headers=headers)
        elif method == "POST":
            r = await http_client.post(url, headers=headers, json=data)
        elif method == "PATCH":
            r = await http_client.patch(url, headers=headers, json=data)
        elif method == "DELETE":
            r = await http_client.delete(url, headers=headers)  # Добавили DELETE

        if r.status_code in [200, 201, 204]:
            return r.json() if method != "PATCH" and method != "DELETE" else True
    except Exception as e:
        print(f"Error: {e}")
    return None


# --- ENDPOINTS ---

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    content = await file.read()
    filename = f"{int(time.time())}_{file.filename}"
    upload_url = f"{URL}/storage/v1/object/avatars/{filename}"
    headers = HEADERS.copy()
    headers["Content-Type"] = file.content_type
    async with httpx.AsyncClient() as client:
        r = await client.post(upload_url, headers=headers, content=content)
        if r.status_code == 200:
            return {"url": f"{URL}/storage/v1/object/public/avatars/{filename}"}
    raise HTTPException(status_code=400, detail="Upload failed")


@app.post("/register")
async def register(data: RegData):
    payload = data.dict()
    payload["email"] = f"{data.username}@local.test"

    # ЛОГИКА ОДОБРЕНИЯ:
    # Если регистрируется 'admin' - одобряем сразу.
    # Остальные - is_approved = False
    if data.username.lower() == "admin":
        payload["is_approved"] = True
    else:
        payload["is_approved"] = False

    if await sb_request("POST", "profiles", payload): return payload
    raise HTTPException(status_code=400, detail="Registration failed")


@app.post("/login")
async def login(data: LoginData):
    users = await sb_request("GET", f"profiles?username=eq.{data.username}")
    if not users: raise HTTPException(status_code=400, detail="Пользователь не найден")

    user = users[0]

    # Проверка пароля
    if str(user['password']) != data.password:
        raise HTTPException(status_code=400, detail="Неверный пароль")

    # Проверка одобрения (Админа пускаем всегда)
    if user['username'] != 'admin' and user.get('is_approved') is False:
        raise HTTPException(status_code=403, detail="Ваш аккаунт ожидает подтверждения администратора")

    return user


# --- НОВЫЕ АДМИНСКИЕ РУЧКИ ---

@app.get("/admin/pending")
async def get_pending_users():
    # Получить всех, у кого is_approved = false
    return await sb_request("GET", "profiles?is_approved=is.false&order=created_at.desc") or []


@app.post("/admin/decision")
async def admin_decision(data: AdminDecision):
    if data.action == "approve":
        # Ставим галочку is_approved = true
        success = await sb_request("PATCH", f"profiles?username=eq.{data.target_username}", {"is_approved": True})
        if success: return {"status": "approved"}

    elif data.action == "reject":
        # Удаляем пользователя из базы
        success = await sb_request("DELETE", f"profiles?username=eq.{data.target_username}")
        if success: return {"status": "rejected"}

    raise HTTPException(status_code=400, detail="Action failed")


# --- ОСТАЛЬНЫЕ РУЧКИ (БЕЗ ИЗМЕНЕНИЙ) ---

@app.post("/reset_password")
async def reset_password(data: ResetData):
    users = await sb_request("GET", f"profiles?username=eq.{data.username}")
    if not users: raise HTTPException(status_code=400, detail="Пользователь не найден")
    user = users[0]
    if not user.get('secret_key') or user['secret_key'] != data.secret_key:
        raise HTTPException(status_code=400, detail="Неверное секретное слово")
    success = await sb_request("PATCH", f"profiles?username=eq.{data.username}", {"password": data.new_password})
    if success: return {"status": "ok"}
    raise HTTPException(status_code=400, detail="Ошибка обновления")


@app.patch("/update_profile")
async def update_profile(data: UpdateData):
    payload = {"first_name": data.first_name, "bio": data.bio, "avatar_url": data.avatar_url}
    if await sb_request("PATCH", f"profiles?username=eq.{data.username}", payload): return payload
    raise HTTPException(status_code=400, detail="Update failed")


@app.get("/feed")
async def get_feed(gender: str, my_username: str):
    target = "Девушка" if gender == "Парень" else "Парень"
    # Показываем в ленте только ОДОБРЕННЫХ пользователей
    users = await sb_request("GET", f"profiles?gender=eq.{target}&is_approved=is.true&limit=50")
    if users: return [u for u in users if u['username'] != my_username]
    return []


@app.post("/like")
async def send_like(data: LikeData):
    await sb_request("POST", "likes", data.dict())
    return {"status": "ok"}


@app.get("/matches")
async def get_matches(email: str):
    my_likes = await sb_request("GET", f"likes?from_email=eq.{email}") or []
    result = []
    for l in my_likes:
        mutual = await sb_request("GET", f"likes?from_email=eq.{l['to_email']}&to_email=eq.{email}")
        if mutual:
            u = await sb_request("GET", f"profiles?email=eq.{l['to_email']}")
            if u: result.append(u[0])
    return result


@app.get("/chats_list")
async def get_chats_list(email: str):
    matches = await get_matches(email)
    for m in matches:
        unread = await sb_request("GET",
                                  f"messages?sender_email=eq.{m['email']}&receiver_email=eq.{email}&is_read=eq.false")
        m["unread_count"] = len(unread) if unread else 0
    return matches


@app.get("/check_unread")
async def check_unread(email: str):
    msgs = await sb_request("GET", f"messages?receiver_email=eq.{email}&is_read=eq.false&order=created_at.desc")
    if not msgs: return {"count": 0, "latest": None}
    last_msg = msgs[0]
    sender_profile = await sb_request("GET", f"profiles?email=eq.{last_msg['sender_email']}")
    sender_name = sender_profile[0]['first_name'] if sender_profile else "Кто-то"
    return {
        "count": len(msgs),
        "latest": {"id": last_msg['id'], "text": last_msg['text'], "sender": sender_name}
    }


@app.get("/chat")
async def get_chat(u1: str, u2: str):
    await sb_request("PATCH", f"messages?sender_email=eq.{u2}&receiver_email=eq.{u1}&is_read=eq.false",
                     {"is_read": True})
    q = f"messages?or=(and(sender_email.eq.{u1},receiver_email.eq.{u2}),and(sender_email.eq.{u2},receiver_email.eq.{u1}))&order=created_at.asc"
    return await sb_request("GET", q) or []


@app.post("/message")
async def send_message(data: MessageData):
    p = data.dict()
    p["is_read"] = False
    await sb_request("POST", "messages", p)
    return {"status": "ok"}
