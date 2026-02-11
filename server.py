from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
from pydantic import BaseModel
import httpx
import os
import time

# --- ГЛОБАЛЬНЫЙ КЛИЕНТ (УСКОРЕНИЕ) ---
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
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- ГЛАВНАЯ СТРАНИЦА ---
@app.get("/")
async def read_root():
    if os.path.exists("index.html"):
        return FileResponse("index.html")
    return {"error": "index.html не найден"}


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
    bio: str  # <-- Добавлено описание при регистрации
    avatar_url: str


# Модель для обновления профиля
class UpdateData(BaseModel):
    username: str  # Используем логин как ID для поиска
    first_name: str  # Новое имя
    bio: str  # Новое описание
    avatar_url: str  # Новое фото


class LikeData(BaseModel):
    from_email: str
    to_email: str


class MessageData(BaseModel):
    sender_email: str
    receiver_email: str
    text: str


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

        if r.status_code in [200, 201, 204]:
            return r.json() if method != "PATCH" else True
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
    if await sb_request("POST", "profiles", payload): return payload
    raise HTTPException(status_code=400, detail="Error")


@app.post("/login")
async def login(data: LoginData):
    users = await sb_request("GET", f"profiles?username=eq.{data.username}")
    if users and str(users[0]['password']) == data.password: return users[0]
    raise HTTPException(status_code=400, detail="Error")


# --- НОВЫЙ ENDPOINT: ОБНОВЛЕНИЕ ПРОФИЛЯ ---
@app.patch("/update_profile")
async def update_profile(data: UpdateData):
    # Обновляем поля по username
    payload = {
        "first_name": data.first_name,
        "bio": data.bio,
        "avatar_url": data.avatar_url
    }
    # Supabase query: UPDATE profiles SET ... WHERE username = ...
    success = await sb_request("PATCH", f"profiles?username=eq.{data.username}", payload)
    if success:
        return payload  # Возвращаем обновленные данные
    raise HTTPException(status_code=400, detail="Update failed")


@app.get("/feed")
async def get_feed(gender: str, my_username: str):
    target = "Девушка" if gender == "Парень" else "Парень"
    users = await sb_request("GET", f"profiles?gender=eq.{target}&limit=50")
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
