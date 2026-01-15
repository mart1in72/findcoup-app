import flet as ft
import random
import threading
import time
import os
import httpx  # Используем для загрузки файлов и сетевых запросов
from postgrest import SyncPostgrestClient

# --- НАСТРОЙКИ ПОДКЛЮЧЕНИЯ ---
URL = "https://kgxvjlsojgkkhdaftncg.supabase.co"
KEY = "sb_publishable_2jhUvmgAKa-edfQyKSWlbA_nKxG65O0"

# --- ИСПРАВЛЕНИЕ ОШИБКИ HTTP/2 ---
# Мы создаем кастомную сессию httpx и отключаем http2 (False).
# Это убирает зависимость от пакета 'h2', который не может загрузиться в браузере.
custom_session = httpx.Client(http2=False)

# Инициализация облегченного клиента с использованием нашей сессии
supabase = SyncPostgrestClient(
    f"{URL}/rest/v1",
    headers={
        "apikey": KEY,
        "Authorization": f"Bearer {KEY}"
    },
    http_client=custom_session  # Передаем исправленный клиент сюда
)


def main(page: ft.Page):
    page.title = "FindCoup v5.2 Platinum"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = ft.Colors.BLACK
    page.window_width = 400
    page.window_height = 800

    user_state = {
        "email": "", "gender": "", "username": "",
        "first_name": "", "grade": "", "bio": "", "avatar_url": ""
    }

    current_chat_partner = {"email": "", "username": ""}
    chat_active = False
    reg_temp_avatar_url = ""

    def show_msg(text, color=ft.Colors.RED_600):
        page.snack_bar = ft.SnackBar(ft.Text(text, color="white"), bgcolor=color)
        page.snack_bar.open = True
        page.update()

    def safe_query(func):
        try:
            return func()
        except Exception as e:
            print(f"Error: {e}")
            return None

    # --- ЗАГРУЗКА ФОТО В STORAGE ---
    def upload_image_to_supabase(file_path, username_prefix="user"):
        try:
            file_name = f"{username_prefix}_{int(time.time())}.png"
            with open(file_path, "rb") as f:
                file_data = f.read()

            upload_url = f"{URL}/storage/v1/object/avatars/{file_name}"
            headers = {
                "apikey": KEY,
                "Authorization": f"Bearer {KEY}",
                "Content-Type": "image/png"
            }

            # Здесь также используем http2=False для стабильности в вебе
            with httpx.Client(http2=False) as client:
                response = client.post(upload_url, headers=headers, content=file_data)
                if response.status_code == 200:
                    public_url = f"{URL}/storage/v1/object/public/avatars/{file_name}"
                    return public_url
                else:
                    return None
        except Exception as e:
            show_msg(f"Ошибка загрузки: {e}")
            return None

    # --- СЧЕТЧИКИ СООБЩЕНИЙ ---
    def get_unread_total():
        if not user_state["email"]: return 0
        res = safe_query(
            lambda: supabase.table("messages").select("id", count="exact").eq("receiver_email", user_state["email"]).eq(
                "is_read", False).execute())
        return res.count if res else 0

    def get_unread_for_user(sender_email):
        res = safe_query(
            lambda: supabase.table("messages").select("id", count="exact").eq("receiver_email", user_state["email"]).eq(
                "sender_email", sender_email).eq("is_read", False).execute())
        return res.count if res else 0

    def mark_as_read(sender_email):
        safe_query(
            lambda: supabase.table("messages").update({"is_read": True}).eq("receiver_email", user_state["email"]).eq(
                "sender_email", sender_email).eq("is_read", False).execute())

    # --- НАВИГАЦИЯ ---
    def get_nav(idx):
        unread = get_unread_total()
        chat_label = f"Чаты ({unread})" if unread > 0 else "Чаты"
        return ft.Tabs(
            selected_index=idx,
            on_change=lambda e: page.go(["/feed", "/matches", "/messages", "/profile"][e.control.selected_index]),
            divider_color=ft.Colors.GREY_900,
            indicator_color=ft.Colors.RED,
            label_color=ft.Colors.RED,
            unselected_label_color=ft.Colors.GREY_400,
            tabs=[
                ft.Tab(text="Лента", icon=ft.Icons.EXPLORE),
                ft.Tab(text="Мэтчи", icon=ft.Icons.FAVORITE),
                ft.Tab(text=chat_label, icon=ft.Icons.CHAT_BUBBLE),
                ft.Tab(text="Профиль", icon=ft.Icons.PERSON),
            ]
        )

    # ================= РОУТИНГ =================
    def route_change(route):
        nonlocal chat_active, reg_temp_avatar_url
        chat_active = False
        page.overlay.clear()
        page.views.clear()

        # 1. ЭКРАН ВХОДА
        if page.route == "/":
            un = ft.TextField(label="Никнейм (с @)", width=300, border_color=ft.Colors.GREY_800, border_radius=10)
            ps = ft.TextField(label="Пароль", password=True, width=300, border_color=ft.Colors.GREY_800,
                              border_radius=10)

            def login_click(_):
                username_val = un.value.strip()
                password_val = ps.value.strip()
                un.error_text = None
                ps.error_text = None

                if "@" not in username_val:
                    un.error_text = "Добавьте @"
                    page.update()
                    return

                res = safe_query(lambda: supabase.table("profiles").select("*").eq("username", username_val).execute())

                if res and res.data:
                    user_data = res.data[0]
                    if str(user_data.get("password")) == password_val:
                        user_state.update(user_data)
                        page.go("/feed")
                    else:
                        ps.error_text = "Неверный пароль"
                        page.update()
                else:
                    un.error_text = "Не найден"
                    page.update()

            page.views.append(ft.View("/", [
                ft.Container(height=80),
                ft.Icon(ft.Icons.FAVORITE, color=ft.Colors.RED, size=100),
                ft.Text("FindCoup", size=35, weight="bold", color="white"),
                ft.Text("Найди себе пару на школьный бал :)", color=ft.Colors.GREY_500),
                ft.Container(height=20),
                un, ps,
                ft.Container(height=10),
                ft.ElevatedButton("ВОЙТИ", width=300, height=50, bgcolor=ft.Colors.RED, color="white",
                                  on_click=login_click),
                ft.TextButton("Создать новый аккаунт", on_click=lambda _: page.go("/register"),
                              style=ft.ButtonStyle(color="white")),
                ft.TextButton("Забыли пароль?", on_click=lambda _: page.go("/reset_password"),
                              style=ft.ButtonStyle(color=ft.Colors.GREY_500))
            ], horizontal_alignment="center", bgcolor="black"))

        # --- СБРОС ПАРОЛЯ ---
        elif page.route == "/reset_password":
            rs_un = ft.TextField(label="Ваш Никнейм (с @)", width=300)
            rs_new_ps = ft.TextField(label="Новый пароль", password=True, width=300)

            def reset_click(_):
                target_un = rs_un.value.strip()
                if not target_un or not rs_new_ps.value:
                    show_msg("Заполните поля!")
                    return
                check = safe_query(lambda: supabase.table("profiles").select("username").eq("username", target_un).execute())
                if check and check.data:
                    safe_query(lambda: supabase.table("profiles").update({"password": rs_new_ps.value}).eq("username", target_un).execute())
                    show_msg("Пароль изменен!", ft.Colors.GREEN_700)
                    page.go("/")
                else:
                    show_msg("Пользователь не найден!")

            page.views.append(ft.View("/reset_password", [
                ft.AppBar(title=ft.Text("Восстановление доступа"), bgcolor="black"),
                ft.Container(height=40),
                rs_un, rs_new_ps,
                ft.ElevatedButton("ОБНОВИТЬ", width=300, bgcolor=ft.Colors.RED, on_click=reset_click),
                ft.TextButton("Назад", on_click=lambda _: page.go("/"))
            ], horizontal_alignment="center", bgcolor="black"))

        # 2. ЭКРАН РЕГИСТРАЦИИ
        elif page.route == "/register":
            reg_temp_avatar_url = ""
            r_fn = ft.TextField(label="Ваше Имя", width=300)
            r_un = ft.TextField(label="Никнейм (@)", width=300)
            r_ps = ft.TextField(label="Пароль", password=True, width=300)
            r_gn = ft.Dropdown(label="Ваш Пол", width=300, options=[ft.dropdown.Option("Парень"), ft.dropdown.Option("Девушка")])
            r_bio = ft.TextField(label="О себе", width=300, multiline=True)
            avatar_preview = ft.CircleAvatar(radius=50, content=ft.Icon(ft.Icons.PERSON))

            def on_reg_file_picked(e: ft.FilePickerResultEvent):
                nonlocal reg_temp_avatar_url
                if e.files:
                    show_msg("Загрузка...")
                    url = upload_image_to_supabase(e.files[0].path, "reg")
                    if url:
                        reg_temp_avatar_url = url
                        avatar_preview.foreground_image_src = url
                        avatar_preview.content = None
                        page.update()

            reg_file_picker = ft.FilePicker(on_result=on_reg_file_picked)
            page.overlay.append(reg_file_picker)

            def register_click(_):
                if not r_un.value or not reg_temp_avatar_url:
                    show_msg("Добавьте фото и ник!")
                    return
                fake_email = f"{r_un.value.strip().replace('@', '')}@findcoup.local"
                data = {
                    "email": fake_email, "password": r_ps.value, "first_name": r_fn.value,
                    "username": r_un.value, "gender": r_gn.value, "bio": r_bio.value,
                    "avatar_url": reg_temp_avatar_url, "grade": "Школьник"
                }
                if safe_query(lambda: supabase.table("profiles").insert(data).execute()):
                    user_state.update(data)
                    page.go("/feed")

            page.views.append(ft.View("/register", [
                ft.AppBar(title=ft.Text("Регистрация"), bgcolor="black"),
                ft.Column([
                    avatar_preview,
                    ft.IconButton(ft.Icons.ADD_A_PHOTO, on_click=lambda _: reg_file_picker.pick_files()),
                    r_fn, r_un, r_ps, r_gn, r_bio,
                    ft.ElevatedButton("ЗАРЕГИСТРИРОВАТЬСЯ", width=300, bgcolor=ft.Colors.RED, on_click=register_click),
                ], horizontal_alignment="center", scroll=ft.ScrollMode.AUTO)
            ], bgcolor="black", horizontal_alignment="center"))

        # 3. ЭКРАН ЛЕНТЫ
        elif page.route == "/feed":
            card_res = ft.Column(horizontal_alignment="center", spacing=15)

            def load_next(_=None):
                target = "Девушка" if user_state["gender"] == "Парень" else "Парень"
                res = safe_query(lambda: supabase.table("profiles").select("*").eq("gender", target).neq("username", user_state["username"]).execute())
                if res and res.data:
                    u = random.choice(res.data)
                    card_res.data = u
                    card_res.controls = [
                        ft.Container(ft.Image(src=u.get("avatar_url") or "", fit="cover"), border_radius=25, height=450, width=350),
                        ft.Text(f"{u['first_name']}", size=26, weight="bold"),
                        ft.Text(u.get("bio", ""), italic=True, color=ft.Colors.GREY_400)
                    ]
                else:
                    card_res.controls = [ft.Text("Пусто!")]
                page.update()

            def match_click(_):
                if not card_res.data: return
                safe_query(lambda: supabase.table("likes").insert({"from_email": user_state["email"], "to_email": card_res.data['email']}).execute())
                load_next()

            page.views.append(ft.View("/feed", [
                ft.AppBar(title=ft.Text("Лента"), bgcolor="black"),
                get_nav(0),
                ft.Container(card_res, padding=10),
                ft.Row([
                    ft.IconButton(ft.Icons.CLOSE, on_click=load_next),
                    ft.IconButton(ft.Icons.FAVORITE, icon_color=ft.Colors.RED, on_click=match_click)
                ], alignment="center")
            ], bgcolor="black", horizontal_alignment="center"))
            load_next()

        # 4. ЭКРАН МЭТЧЕЙ
        elif page.route == "/matches":
            match_list = ft.ListView(expand=True, spacing=10, padding=10)
            my_likes = safe_query(lambda: supabase.table("likes").select("to_email").eq("from_email", user_state["email"]).execute())
            if my_likes and my_likes.data:
                for item in my_likes.data:
                    mutual = safe_query(lambda: supabase.table("likes").select("*").eq("from_email", item['to_email']).eq("to_email", user_state["email"]).execute())
                    if mutual and mutual.data:
                        u_res = safe_query(lambda: supabase.table("profiles").select("*").eq("email", item['to_email']).single().execute())
                        if u_res:
                            u = u_res.data
                            match_list.controls.append(ft.ListTile(
                                leading=ft.CircleAvatar(foreground_image_src=u.get("avatar_url")),
                                title=ft.Text(u['first_name']),
                                trailing=ft.IconButton(ft.Icons.CHAT, on_click=lambda _, user=u: open_chat(user))
                            ))
            page.views.append(ft.View("/matches", [ft.AppBar(title=ft.Text("Мэтчи")), get_nav(1), match_list], bgcolor="black"))

        # 5. ЭКРАН СПИСКА ЧАТОВ
        elif page.route == "/messages":
            chats_list = ft.ListView(expand=True)
            msgs = safe_query(lambda: supabase.table("messages").select("sender_email, receiver_email").or_(f"sender_email.eq.{user_state['email']},receiver_email.eq.{user_state['email']}").execute())
            partners = {m['receiver_email'] if m['sender_email'] == user_state['email'] else m['sender_email'] for m in msgs.data} if msgs else set()
            for p_email in partners:
                p_res = safe_query(lambda: supabase.table("profiles").select("*").eq("email", p_email).single().execute())
                if p_res:
                    u = p_res.data
                    chats_list.controls.append(ft.ListTile(
                        leading=ft.CircleAvatar(foreground_image_src=u.get("avatar_url")),
                        title=ft.Text(u['first_name']),
                        on_click=lambda _, user=u: open_chat(user)
                    ))
            page.views.append(ft.View("/messages", [ft.AppBar(title=ft.Text("Чаты")), get_nav(2), chats_list], bgcolor="black"))

        # 6. ЭКРАН ПЕРЕПИСКИ
        elif page.route == "/chat":
            chat_active = True
            msg_list = ft.ListView(expand=True, spacing=10, auto_scroll=True)
            msg_in = ft.TextField(hint_text="Сообщение...", expand=True)

            def send_msg(_):
                if msg_in.value:
                    safe_query(lambda: supabase.table("messages").insert({"sender_email": user_state["email"], "receiver_email": current_chat_partner["email"], "text": msg_in.value, "is_read": False}).execute())
                    msg_in.value = ""
                    refresh_chat()

            def refresh_chat():
                if not chat_active: return
                mark_as_read(current_chat_partner["email"])
                res = safe_query(lambda: supabase.table("messages").select("*").or_(f"and(sender_email.eq.{user_state['email']},receiver_email.eq.{current_chat_partner['email']}),and(sender_email.eq.{current_chat_partner['email']},receiver_email.eq.{user_state['email']})").order("created_at").execute())
                if res and res.data:
                    msg_list.controls = [ft.Row([ft.Container(content=ft.Text(m['text']), bgcolor=ft.Colors.RED if m['sender_email'] == user_state['email'] else ft.Colors.GREY_900, padding=12, border_radius=15)], alignment=ft.MainAxisAlignment.END if m['sender_email'] == user_state['email'] else ft.MainAxisAlignment.START) for m in res.data]
                    page.update()

            threading.Thread(target=lambda: (time.sleep(3), refresh_chat() if chat_active else None), daemon=True).start()
            refresh_chat()
            page.views.append(ft.View("/chat", [
                ft.AppBar(title=ft.Text(current_chat_partner['username']), leading=ft.IconButton(ft.Icons.ARROW_BACK, on_click=lambda _: page.go("/messages"))),
                msg_list,
                ft.Container(ft.Row([msg_in, ft.IconButton(ft.Icons.SEND, on_click=send_msg)]), padding=15)
            ], bgcolor="black"))

        # 7. ЭКРАН ПРОФИЛЯ
        elif page.route == "/profile":
            p_un = ft.TextField(label="Никнейм", value=user_state["username"])
            p_fn = ft.TextField(label="Имя", value=user_state["first_name"])
            p_bio = ft.TextField(label="О себе", value=user_state.get("bio", ""), multiline=True)

            def save_profile(_):
                data = {"username": p_un.value, "first_name": p_fn.value, "bio": p_bio.value, "avatar_url": user_state["avatar_url"]}
                if safe_query(lambda: supabase.table("profiles").update(data).eq("username", user_state["username"]).execute()):
                    user_state.update(data)
                    show_msg("Сохранено!", ft.Colors.GREEN_700)

            page.views.append(ft.View("/profile", [
                ft.AppBar(title=ft.Text("Мой Профиль")),
                get_nav(3),
                ft.Column([
                    ft.CircleAvatar(foreground_image_src=user_state["avatar_url"], radius=70),
                    p_un, p_fn, p_bio,
                    ft.ElevatedButton("СОХРАНИТЬ", width=300, bgcolor=ft.Colors.RED, on_click=save_profile),
                    ft.TextButton("Выйти", on_click=lambda _: page.go("/"))
                ], horizontal_alignment="center", spacing=15)
            ], bgcolor="black", horizontal_alignment="center"))

        page.update()

    def open_chat(u):
        current_chat_partner.update({"email": u['email'], "username": u['username']})
        page.go("/chat")

    page.on_route_change = route_change
    page.go("/")


ft.app(target=main)
