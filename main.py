import flet as ft
import random
import threading
import time
import os
import httpx 
from postgrest import SyncPostgrestClient

# ==========================================================================================
# КОНФИГУРАЦИЯ
# ==========================================================================================
URL = "https://kgxvjlsojgkkhdaftncg.supabase.co"
KEY = "sb_publishable_2jhUvmgAKa-edfQyKSWlbA_nKxG65O0"

# Отключаем HTTP/2 для стабильности в Pyodide
custom_session = httpx.Client(http2=False)

supabase = SyncPostgrestClient(
    f"{URL}/rest/v1", 
    headers={
        "apikey": KEY,
        "Authorization": f"Bearer {KEY}"
    },
    http_client=custom_session
)

def main(page: ft.Page):
    page.title = "FindCoup v5.2 Platinum"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = ft.Colors.BLACK
    page.window_width = 400
    page.window_height = 800
    page.padding = 0

    user_state = {
        "email": "", "gender": "", "username": "",
        "first_name": "", "grade": "", "bio": "", "avatar_url": ""
    }

    current_chat_partner = {"email": "", "username": "", "avatar_url": ""}
    chat_active = False
    reg_temp_avatar_url = ""

    def show_msg(text, color=ft.Colors.RED_600):
        page.snack_bar = ft.SnackBar(content=ft.Text(text), bgcolor=color)
        page.snack_bar.open = True
        page.update()

    def safe_query(func):
        try: return func()
        except: return None

    def upload_image_to_supabase(file_path, prefix="user"):
        try:
            file_name = f"{prefix}_{int(time.time())}.png"
            with open(file_path, "rb") as f:
                data = f.read()
            u_url = f"{URL}/storage/v1/object/avatars/{file_name}"
            headers = {"apikey": KEY, "Authorization": f"Bearer {KEY}", "Content-Type": "image/png"}
            with httpx.Client(http2=False) as client:
                resp = client.post(u_url, headers=headers, content=data)
                if resp.status_code == 200:
                    return f"{URL}/storage/v1/object/public/avatars/{file_name}"
            return None
        except: return None

    # --- НАВИГАЦИЯ ---
    def get_nav(idx):
        return ft.Tabs(
            selected_index=idx,
            on_change=lambda e: page.go(["/feed", "/matches", "/messages", "/profile"][e.control.selected_index]),
            divider_color=ft.Colors.GREY_900,
            indicator_color=ft.Colors.RED,
            tabs=[
                ft.Tab(text="Лента", icon=ft.Icons.EXPLORE_ROUNDED),
                ft.Tab(text="Мэтчи", icon=ft.Icons.FAVORITE_ROUNDED),
                ft.Tab(text="Чаты", icon=ft.Icons.CHAT_BUBBLE_ROUNDED),
                ft.Tab(text="Профиль", icon=ft.Icons.PERSON_ROUNDED),
            ]
        )

    def route_change(route):
        nonlocal chat_active, reg_temp_avatar_url
        chat_active = False
        page.views.clear()

        # 1. ВХОД
        if page.route == "/":
            un = ft.TextField(label="Никнейм (@)", width=320, border_radius=15)
            ps = ft.TextField(label="Пароль", password=True, width=320, border_radius=15)

            def login_click(_):
                res = safe_query(lambda: supabase.table("profiles").select("*").eq("username", un.value).execute())
                if res and res.data:
                    if str(res.data[0].get("password")) == ps.value:
                        user_state.update(res.data[0])
                        page.go("/feed")
                    else: show_msg("Неверный пароль")
                else: show_msg("Не найден")

            page.views.append(ft.View("/", [
                ft.Container(height=60),
                ft.Icon(ft.Icons.FAVORITE_ROUNDED, color=ft.Colors.RED, size=100),
                ft.Text("FindCoup", size=35, weight="bold"),
                ft.Container(height=20),
                un, ps,
                ft.ElevatedButton("ВОЙТИ", width=320, height=50, bgcolor="red", on_click=login_click),
                ft.TextButton("Регистрация", on_click=lambda _: page.go("/register"))
            ], horizontal_alignment="center", bgcolor="black"))

        # 2. РЕГИСТРАЦИЯ
        elif page.route == "/register":
            r_fn = ft.TextField(label="Имя", width=320)
            r_un = ft.TextField(label="Никнейм (@)", width=320)
            r_ps = ft.TextField(label="Пароль", password=True, width=320)
            r_gn = ft.Dropdown(label="Пол", width=320, options=[ft.dropdown.Option("Парень"), ft.dropdown.Option("Девушка")])
            preview = ft.CircleAvatar(radius=50, content=ft.Icon(ft.Icons.PERSON))

            def on_res(e: ft.FilePickerResultEvent):
                nonlocal reg_temp_avatar_url
                if e.files:
                    url = upload_image_to_supabase(e.files[0].path, "reg")
                    if url:
                        reg_temp_avatar_url = url
                        preview.foreground_image_src = url
                        page.update()

            pk = ft.FilePicker(on_result=on_res)
            page.overlay.append(pk)

            def reg_done(_):
                if not r_un.value or not reg_temp_avatar_url: return
                data = {"username": r_un.value, "first_name": r_fn.value, "password": r_ps.value, 
                        "gender": r_gn.value, "avatar_url": reg_temp_avatar_url, "email": f"{r_un.value}@find.local"}
                if safe_query(lambda: supabase.table("profiles").insert(data).execute()):
                    user_state.update(data)
                    page.go("/feed")

            page.views.append(ft.View("/register", [
                ft.AppBar(title=ft.Text("Регистрация")),
                ft.Column([
                    preview, 
                    ft.TextButton("Загрузить фото", on_click=lambda _: pk.pick_files()),
                    r_fn, r_un, r_ps, r_gn,
                    ft.ElevatedButton("СОЗДАТЬ", width=320, bgcolor="red", on_click=reg_done)
                ], horizontal_alignment="center", scroll=ft.ScrollMode.AUTO) # padding удален отсюда
            ], bgcolor="black", horizontal_alignment="center"))

        # 3. ЛЕНТА
        elif page.route == "/feed":
            stack = ft.Column(horizontal_alignment="center")

            def load_next(_=None):
                seek = "Девушка" if user_state["gender"] == "Парень" else "Парень"
                res = safe_query(lambda: supabase.table("profiles").select("*").eq("gender", seek).neq("username", user_state["username"]).execute())
                if res and res.data:
                    p = random.choice(res.data)
                    stack.data = p
                    stack.controls = [
                        ft.Container(ft.Image(src=p['avatar_url'], fit="cover"), border_radius=25, height=450, width=350),
                        ft.Text(p['first_name'], size=26, weight="bold")
                    ]
                else: stack.controls = [ft.Text("Пусто")]
                page.update()

            page.views.append(ft.View("/feed", [
                ft.AppBar(title=ft.Text("Лента")),
                get_nav(0),
                ft.Container(stack, padding=20),
                ft.Row([
                    ft.IconButton(ft.Icons.CLOSE, on_click=load_next),
                    ft.IconButton(ft.Icons.FAVORITE, icon_color="red", on_click=lambda _: load_next())
                ], alignment="center")
            ], bgcolor="black", horizontal_alignment="center"))
            load_next()

        # 4. ПРОФИЛЬ
        elif page.route == "/profile":
            page.views.append(ft.View("/profile", [
                ft.AppBar(title=ft.Text("Профиль")),
                get_nav(3),
                ft.Column([
                    ft.CircleAvatar(foreground_image_src=user_state["avatar_url"], radius=70),
                    ft.Text(user_state["username"], size=22),
                    ft.ElevatedButton("ВЫЙТИ", on_click=lambda _: page.go("/"))
                ], horizontal_alignment="center", spacing=20) # padding удален отсюда
            ], bgcolor="black", horizontal_alignment="center"))

        page.update()

    page.on_route_change = route_change
    page.go("/")

ft.app(main)
