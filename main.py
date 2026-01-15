import flet as ft
import random
import threading
import time
import os
import httpx  # Используется для сетевых запросов без HTTP/2
from postgrest import SyncPostgrestClient

# ==========================================================================================
# КОНФИГУРАЦИЯ И ГЛОБАЛЬНЫЕ НАСТРОЙКИ ПРИЛОЖЕНИЯ
# ==========================================================================================
# Данные доступа к вашему проекту Supabase.
URL = "https://kgxvjlsojgkkhdaftncg.supabase.co"
KEY = "sb_publishable_2jhUvmgAKa-edfQyKSWlbA_nKxG65O0"

# --- РЕШЕНИЕ ПРОБЛЕМЫ С HTTP/2 В БРАУЗЕРНОЙ СРЕДЕ ---
# Мы принудительно отключаем поддержку HTTP/2 через кастомный клиент httpx.
# Это критически важно для работы в Pyodide (GitHub Pages), так как там нет пакета 'h2'.
custom_session = httpx.Client(http2=False)

# Инициализация облегченного клиента базы данных.
supabase = SyncPostgrestClient(
    f"{URL}/rest/v1",
    headers={
        "apikey": KEY,
        "Authorization": f"Bearer {KEY}"
    },
    http_client=custom_session
)


def main(page: ft.Page):
    # Визуальные настройки страницы
    page.title = "FindCoup v5.2 Platinum Edition"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = ft.Colors.BLACK
    page.window_width = 400
    page.window_height = 800
    page.padding = 0

    # Глобальное хранилище данных текущего пользователя (Session State)
    user_state = {
        "email": "",
        "gender": "",
        "username": "",
        "first_name": "",
        "grade": "",
        "bio": "",
        "avatar_url": ""
    }

    # Переменные управления состоянием чатов и регистрации
    current_chat_partner = {"email": "", "username": "", "avatar_url": ""}
    chat_active = False
    reg_temp_avatar_url = ""

    # --------------------------------------------------------------------------------------
    # ВСПОМОГАТЕЛЬНЫЕ СЕРВИСНЫЕ ФУНКЦИИ
    # --------------------------------------------------------------------------------------

    def show_msg(text, color=ft.Colors.RED_600):
        """Отображает SnackBar для обратной связи с пользователем."""
        page.snack_bar = ft.SnackBar(
            content=ft.Text(text, color="white", weight="w500"),
            bgcolor=color,
            duration=3000
        )
        page.snack_bar.open = True
        page.update()

    def safe_query(func):
        """Обертка для защиты от сетевых исключений при запросах к API."""
        try:
            return func()
        except Exception as e:
            print(f"Database Query Error: {e}")
            return None

    # --------------------------------------------------------------------------------------
    # МОДУЛЬ ЗАГРУЗКИ МЕДИАФАЙЛОВ (SUPABASE STORAGE)
    # --------------------------------------------------------------------------------------

    def upload_image_to_supabase(file_path, username_prefix="user"):
        """Загрузка изображения через прямой POST-запрос к API Storage."""
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

            # Используем безопасный клиент без HTTP/2 для загрузки байтов
            with httpx.Client(http2=False) as client:
                response = client.post(upload_url, headers=headers, content=file_data)

                if response.status_code == 200:
                    return f"{URL}/storage/v1/object/public/avatars/{file_name}"
                else:
                    return None
        except Exception as e:
            show_msg(f"Ошибка загрузки: {e}")
            return None

    # --------------------------------------------------------------------------------------
    # МЕТРИКИ СООБЩЕНИЙ И СЧЕТЧИКИ
    # --------------------------------------------------------------------------------------

    def get_unread_total():
        """Возвращает общее количество новых сообщений для бейджа в навигации."""
        if not user_state["email"]: return 0
        res = safe_query(
            lambda: supabase.table("messages")
            .select("id", count="exact")
            .eq("receiver_email", user_state["email"])
            .eq("is_read", False).execute()
        )
        return res.count if res else 0

    def get_unread_for_user(sender_email):
        """Считает непрочитанные сообщения в конкретном диалоге."""
        res = safe_query(
            lambda: supabase.table("messages")
            .select("id", count="exact")
            .eq("receiver_email", user_state["email"])
            .eq("sender_email", sender_email)
            .eq("is_read", False).execute()
        )
        return res.count if res else 0

    def mark_as_read(sender_email):
        """Обновляет статус сообщений на 'прочитано' при открытии чата."""
        safe_query(
            lambda: supabase.table("messages")
            .update({"is_read": True})
            .eq("receiver_email", user_state["email"])
            .eq("sender_email", sender_email)
            .eq("is_read", False).execute()
        )

    # --------------------------------------------------------------------------------------
    # СИСТЕМА НАВИГАЦИИ (TABS)
    # --------------------------------------------------------------------------------------

    def get_nav(idx):
        """Создает нижнюю панель навигации."""
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
                ft.Tab(text="Лента", icon=ft.Icons.EXPLORE_ROUNDED),
                ft.Tab(text="Мэтчи", icon=ft.Icons.FAVORITE_ROUNDED),
                ft.Tab(text=chat_label, icon=ft.Icons.CHAT_BUBBLE_ROUNDED),
                ft.Tab(text="Профиль", icon=ft.Icons.PERSON_ROUNDED),
            ]
        )

    # ======================================================================================
    # ГЛАВНЫЙ КОНТРОЛЛЕР МАРШРУТИЗАЦИИ (ROUTING)
    # ======================================================================================

    def route_change(route):
        nonlocal chat_active, reg_temp_avatar_url
        chat_active = False
        page.overlay.clear()
        page.views.clear()

        # --- ЭКРАН: ВХОД В ПРИЛОЖЕНИЕ ---
        if page.route == "/":
            un_field = ft.TextField(
                label="Никнейм (с @)",
                width=320,
                border_color=ft.Colors.GREY_800,
                border_radius=15,
                prefix_icon=ft.Icons.ALTERNATE_EMAIL
            )
            ps_field = ft.TextField(
                label="Пароль",
                password=True,
                can_reveal_password=True,
                width=320,
                border_color=ft.Colors.GREY_800,
                border_radius=15,
                prefix_icon=ft.Icons.LOCK_OUTLINED
            )

            def login_process(_):
                username = un_field.value.strip()
                password = ps_field.value.strip()
                if "@" not in username:
                    un_field.error_text = "Нужен @"
                    page.update();
                    return

                res = safe_query(lambda: supabase.table("profiles").select("*").eq("username", username).execute())
                if res and res.data:
                    db_u = res.data[0]
                    if str(db_u.get("password")) == password:
                        user_state.update(db_u)
                        page.go("/feed")
                    else:
                        ps_field.error_text = "Ошибка пароля";
                        page.update()
                else:
                    un_field.error_text = "Не найден";
                    page.update()

            page.views.append(ft.View("/", [
                ft.Container(height=60),
                ft.Icon(ft.Icons.FAVORITE_ROUNDED, color=ft.Colors.RED, size=120),
                ft.Text("FindCoup", size=40, weight="bold"),
                ft.Text("Найди свою пару на бал", color="grey"),
                ft.Container(height=30),
                un_field, ps_field,
                ft.Container(height=10),
                ft.ElevatedButton("ВОЙТИ", width=320, height=55, bgcolor="red", color="white", on_click=login_process),
                ft.TextButton("Зарегистрироваться", on_click=lambda _: page.go("/register")),
                ft.TextButton("Забыли пароль?", on_click=lambda _: page.go("/reset_password"),
                              style=ft.ButtonStyle(color="grey"))
            ], horizontal_alignment="center", bgcolor="black"))

        # --- ЭКРАН: СБРОС ПАРОЛЯ ---
        elif page.route == "/reset_password":
            rs_un = ft.TextField(label="Никнейм (@)", width=320, border_radius=15)
            rs_ps = ft.TextField(label="Новый пароль", password=True, width=320, border_radius=15)

            def do_reset(_):
                if not rs_un.value or not rs_ps.value: return
                check = safe_query(
                    lambda: supabase.table("profiles").select("username").eq("username", rs_un.value).execute())
                if check and check.data:
                    safe_query(lambda: supabase.table("profiles").update({"password": rs_ps.value}).eq("username",
                                                                                                       rs_un.value).execute())
                    show_msg("Готово!", ft.Colors.GREEN_700)
                    page.go("/")
                else:
                    show_msg("Ник не найден")

            page.views.append(ft.View("/reset_password", [
                ft.AppBar(title=ft.Text("Сброс пароля")),
                ft.Container(height=40),
                rs_un, rs_ps,
                ft.ElevatedButton("ИЗМЕНИТЬ", width=320, bgcolor="red", on_click=do_reset),
                ft.TextButton("Назад", on_click=lambda _: page.go("/"))
            ], horizontal_alignment="center", bgcolor="black"))

        # --- ЭКРАН: РЕГИСТРАЦИЯ ---
        elif page.route == "/register":
            reg_temp_avatar_url = ""
            r_fn = ft.TextField(label="Имя", width=320, border_radius=10)
            r_un = ft.TextField(label="Никнейм (@)", width=320, border_radius=10)
            r_ps = ft.TextField(label="Пароль", password=True, width=320, border_radius=10)
            r_gn = ft.Dropdown(label="Пол", width=320,
                               options=[ft.dropdown.Option("Парень"), ft.dropdown.Option("Девушка")])
            r_bio = ft.TextField(label="О себе", width=320, multiline=True, border_radius=10)
            avatar_preview = ft.CircleAvatar(radius=60, bgcolor=ft.Colors.GREY_900,
                                             content=ft.Icon(ft.Icons.ADD_A_PHOTO))

            def on_up(e: ft.FilePickerResultEvent):
                nonlocal reg_temp_avatar_url
                if e.files:
                    show_msg("Загрузка...")
                    url = upload_image_to_supabase(e.files[0].path, "reg")
                    if url:
                        reg_temp_avatar_url = url
                        avatar_preview.foreground_image_src = url
                        avatar_preview.content = None
                        page.update()

            reg_pick = ft.FilePicker(on_result=on_up)
            page.overlay.append(reg_pick)

            def do_reg(_):
                if not r_un.value or not reg_temp_avatar_url:
                    show_msg("Нужны ник и фото!");
                    return
                email = f"{r_un.value.strip().replace('@', '')}@findcoup.local"
                data = {
                    "email": email, "password": r_ps.value, "first_name": r_fn.value,
                    "username": r_un.value, "gender": r_gn.value, "bio": r_bio.value,
                    "avatar_url": reg_temp_avatar_url, "grade": "Школьник"
                }
                if safe_query(lambda: supabase.table("profiles").insert(data).execute()):
                    user_state.update(data)
                    page.go("/feed")

            page.views.append(ft.View("/register", [
                ft.AppBar(title=ft.Text("Регистрация")),
                ft.Column([
                    ft.Container(height=10),
                    avatar_preview,
                    ft.TextButton("Выбрать фото", on_click=lambda _: reg_pick.pick_files()),
                    r_fn, r_un, r_ps, r_gn, r_bio,
                    ft.ElevatedButton("СОЗДАТЬ", width=320, height=55, bgcolor="red", on_click=do_reg),
                    ft.Container(height=30)
                ], horizontal_alignment="center", scroll=ft.ScrollMode.AUTO)
            ], bgcolor="black", horizontal_alignment="center"))

        # --- ЭКРАН: ЛЕНТА ЗНАКОМСТВ ---
        elif page.route == "/feed":
            card_stack = ft.Column(horizontal_alignment="center", spacing=15)

            def next_p(_=None):
                target = "Девушка" if user_state["gender"] == "Парень" else "Парень"
                res = safe_query(lambda: supabase.table("profiles").select("*").eq("gender", target).neq("username",
                                                                                                         user_state[
                                                                                                             "username"]).execute())
                if res and res.data:
                    p = random.choice(res.data)
                    card_stack.data = p
                    card_stack.controls = [
                        ft.Container(ft.Image(src=p.get("avatar_url"), fit="cover"), border_radius=30, height=480,
                                     width=360),
                        ft.Text(f"{p['first_name']}", size=28, weight="bold"),
                        ft.Text(p.get("bio", ""), italic=True, color="grey")
                    ]
                else:
                    card_stack.controls = [ft.Text("Никого нет рядом", color="grey")]
                page.update()

            def do_like(_):
                if not card_stack.data: return
                safe_query(lambda: supabase.table("likes").insert(
                    {"from_email": user_state["email"], "to_email": card_stack.data['email']}).execute())
                next_p()

            page.views.append(ft.View("/feed", [
                ft.AppBar(title=ft.Text("FindCoup", color="red"), automatically_imply_leading=False),
                get_nav(0),
                ft.Container(card_stack, padding=15),
                ft.Row([
                    ft.IconButton(ft.Icons.CLOSE, icon_size=40, on_click=next_p),
                    ft.IconButton(ft.Icons.FAVORITE, icon_size=50, icon_color="red", on_click=do_like)
                ], alignment="center")
            ], bgcolor="black", horizontal_alignment="center"))
            next_p()

        # --- ЭКРАН: МЭТЧИ ---
        elif page.route == "/matches":
            m_list = ft.ListView(expand=True, spacing=10, padding=15)
            likes = safe_query(
                lambda: supabase.table("likes").select("to_email").eq("from_email", user_state["email"]).execute())
            if likes and likes.data:
                for l in likes.data:
                    mut = safe_query(
                        lambda: supabase.table("likes").select("*").eq("from_email", l['to_email']).eq("to_email",
                                                                                                       user_state[
                                                                                                           "email"]).execute())
                    if mut and mut.data:
                        p_res = safe_query(lambda: supabase.table("profiles").select("*").eq("email", l[
                            'to_email']).single().execute())
                        if p_res:
                            u = p_res.data
                            m_list.controls.append(ft.ListTile(
                                leading=ft.CircleAvatar(foreground_image_src=u.get("avatar_url")),
                                title=ft.Text(u['first_name']),
                                trailing=ft.IconButton(ft.Icons.CHAT, on_click=lambda _, u=u: open_chat(u))
                            ))
            page.views.append(
                ft.View("/matches", [ft.AppBar(title=ft.Text("Мэтчи")), get_nav(1), m_list], bgcolor="black"))

        # --- ЭКРАН: СПИСОК ЧАТОВ ---
        elif page.route == "/messages":
            c_list = ft.ListView(expand=True, padding=10)
            raw = safe_query(lambda: supabase.table("messages").select("sender_email, receiver_email").or_(
                f"sender_email.eq.{user_state['email']},receiver_email.eq.{user_state['email']}").execute())
            emails = {m['receiver_email'] if m['sender_email'] == user_state['email'] else m['sender_email'] for m in
                      raw.data} if raw else set()
            for em in emails:
                p = safe_query(lambda: supabase.table("profiles").select("*").eq("email", em).single().execute())
                if p:
                    u = p.data
                    c_list.controls.append(ft.ListTile(
                        leading=ft.CircleAvatar(foreground_image_src=u.get("avatar_url")),
                        title=ft.Text(u['first_name']),
                        on_click=lambda _, u=u: open_chat(u)
                    ))
            page.views.append(
                ft.View("/messages", [ft.AppBar(title=ft.Text("Чаты")), get_nav(2), c_list], bgcolor="black"))

        # --- ЭКРАН: ОКНО ЧАТА ---
        elif page.route == "/chat":
            chat_active = True
            msg_view = ft.ListView(expand=True, spacing=10, padding=20, auto_scroll=True)
            msg_in = ft.TextField(hint_text="Сообщение...", expand=True, border_radius=20)

            def send_msg(_):
                if msg_in.value:
                    safe_query(lambda: supabase.table("messages").insert(
                        {"sender_email": user_state["email"], "receiver_email": current_chat_partner["email"],
                         "text": msg_in.value, "is_read": False}).execute())
                    msg_in.value = "";
                    sync_chat()

            def sync_chat():
                if not chat_active: return
                mark_as_read(current_chat_partner["email"])
                q = f"and(sender_email.eq.{user_state['email']},receiver_email.eq.{current_chat_partner['email']}),and(sender_email.eq.{current_chat_partner['email']},receiver_email.eq.{user_state['email']})"
                res = safe_query(lambda: supabase.table("messages").select("*").or_(q).order("created_at").execute())
                if res and res.data:
                    msg_view.controls = [ft.Row([ft.Container(content=ft.Text(m['text']),
                                                              bgcolor="red" if m['sender_email'] == user_state[
                                                                  'email'] else "#222222", padding=12,
                                                              border_radius=15)],
                                                alignment=ft.MainAxisAlignment.END if m['sender_email'] == user_state[
                                                    'email'] else ft.MainAxisAlignment.START) for m in res.data]
                    page.update()

            def poll():
                while chat_active:
                    time.sleep(4);
                    sync_chat()

            threading.Thread(target=poll, daemon=True).start()
            sync_chat()

            page.views.append(ft.View("/chat", [
                ft.AppBar(title=ft.Text(current_chat_partner['username']),
                          leading=ft.IconButton(ft.Icons.ARROW_BACK, on_click=lambda _: page.go("/messages"))),
                msg_view,
                ft.Container(content=ft.Row([msg_in, ft.IconButton(ft.Icons.SEND, on_click=send_msg)]), padding=20)
            ], bgcolor="black"))

        # --- ЭКРАН: ПРОФИЛЬ ---
        elif page.route == "/profile":
            ed_fn = ft.TextField(label="Имя", value=user_state["first_name"])
            ed_bio = ft.TextField(label="О себе", value=user_state["bio"], multiline=True)

            def save_p(_):
                safe_query(
                    lambda: supabase.table("profiles").update({"first_name": ed_fn.value, "bio": ed_bio.value}).eq(
                        "email", user_state["email"]).execute())
                show_msg("Сохранено", ft.Colors.GREEN_700)

            page.views.append(ft.View("/profile", [
                ft.AppBar(title=ft.Text("Профиль")),
                get_nav(3),
                ft.Column([
                    ft.Container(height=20),
                    ft.CircleAvatar(foreground_image_src=user_state["avatar_url"], radius=80),
                    ft.Text(user_state["username"], size=20, weight="bold"),
                    ed_fn, ed_bio,
                    ft.ElevatedButton("СОХРАНИТЬ", width=320, height=50, bgcolor="red", on_click=save_p),
                    ft.TextButton("Выйти", on_click=lambda _: page.go("/"), style=ft.ButtonStyle(color="red"))
                ], horizontal_alignment="center", spacing=15, scroll=ft.ScrollMode.AUTO)
            ], bgcolor="black", horizontal_alignment="center"))

        page.update()

    def open_chat(u):
        current_chat_partner.update(
            {"email": u['email'], "username": u['username'], "avatar_url": u.get("avatar_url", "")})
        page.go("/chat")

    page.on_route_change = route_change
    page.go("/")


# Запуск
ft.app(target=main)
