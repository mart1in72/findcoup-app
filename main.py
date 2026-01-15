import flet as ft
import random
import threading
import time
import os
import httpx  # Используем для загрузки файлов вместо тяжелого storage SDK
from postgrest import SyncPostgrestClient # Легкий клиент для таблиц

# --- НАСТРОЙКИ ПОДКЛЮЧЕНИЯ ---
URL = "https://kgxvjlsojgkkhdaftncg.supabase.co"
KEY = "sb_publishable_2jhUvmgAKa-edfQyKSWlbA_nKxG65O0"

custom_session = httpx.Client(http2=False)

# Инициализация облегченного клиента для таблиц (заменяет старый supabase клиент)
supabase = SyncPostgrestClient(
    f"{URL}/rest/v1",
    headers={
        "apikey": KEY,
        "Authorization": f"Bearer {KEY}"
    },
    http_client=custom_session  # Используем наш готовый клиент
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

    # --- ЗАГРУЗКА ФОТО В STORAGE (ИЗМЕНЕНО: БЕЗ ИСПОЛЬЗОВАНИЯ SUPABASE SDK) ---
    def upload_image_to_supabase(file_path, username_prefix="user"):
        try:
            file_name = f"{username_prefix}_{int(time.time())}.png"
            # Читаем файл в бинарном режиме
            with open(file_path, "rb") as f:
                file_data = f.read()

            # Отправляем файл напрямую через REST API Storage (Bucket: avatars)
            upload_url = f"{URL}/storage/v1/object/avatars/{file_name}"
            headers = {
                "apikey": KEY,
                "Authorization": f"Bearer {KEY}",
                "Content-Type": "image/png"
            }

            with httpx.Client() as client:
                response = client.post(upload_url, headers=headers, content=file_data)
                if response.status_code == 200:
                    # Формируем публичную ссылку (render используется для оптимизации)
                    public_url = f"{URL}/storage/v1/object/public/avatars/{file_name}"
                    return public_url
                else:
                    print(f"Storage Error: {response.text}")
                    return None
        except Exception as e:
            print(f"Upload Error: {e}")
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
                un.border_color = ft.Colors.GREY_800
                ps.border_color = ft.Colors.GREY_800

                if "@" not in username_val:
                    un.error_text = "Email введён некорректно, добавьте @"
                    show_msg("Ошибка в формате никнейма", ft.Colors.RED_600)
                    page.update()
                    return

                res = safe_query(lambda: supabase.table("profiles").select("*").eq("username", username_val).execute())

                if res and res.data:
                    user_data = res.data[0]
                    if str(user_data.get("password")) == password_val:
                        user_state.update(user_data)
                        page.go("/feed")
                    else:
                        ps.error_text = "Неверный пароль! Попробуйте еще раз"
                        ps.border_color = ft.Colors.RED_600
                        show_msg("Ошибка доступа: неверный пароль", ft.Colors.RED_600)
                        page.update()
                else:
                    un.error_text = "Пользователь не зарегистрирован"
                    un.border_color = ft.Colors.RED_600
                    show_msg("Никнейм не найден в базе данных", ft.Colors.RED_600)
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

        elif page.route == "/reset_password":
            rs_un = ft.TextField(label="Ваш Никнейм (с @)", width=300, border_color=ft.Colors.GREY_800)
            rs_new_ps = ft.TextField(label="Новый пароль", password=True, width=300, border_color=ft.Colors.GREY_800)

            def reset_click(_):
                target_un = rs_un.value.strip()
                if not target_un or not rs_new_ps.value:
                    show_msg("Заполните все поля!", ft.Colors.RED_600)
                    return
                check = safe_query(
                    lambda: supabase.table("profiles").select("username").eq("username", target_un).execute())
                if check and check.data:
                    upd = safe_query(
                        lambda: supabase.table("profiles").update({"password": rs_new_ps.value}).eq("username",
                                                                                                    target_un).execute())
                    if upd:
                        show_msg("Пароль успешно изменен!", ft.Colors.GREEN_700)
                        page.go("/")
                else:
                    show_msg("Пользователь не найден!", ft.Colors.RED_600)

            page.views.append(ft.View("/reset_password", [
                ft.AppBar(title=ft.Text("Восстановление доступа"), bgcolor="black", color="white"),
                ft.Container(height=40),
                ft.Text("Введите никнейм и новый пароль", color="white", size=16),
                ft.Container(height=20),
                rs_un,
                rs_new_ps,
                ft.Container(height=20),
                ft.ElevatedButton("ОБНОВИТЬ ПАРОЛЬ", width=300, height=50, bgcolor=ft.Colors.RED, color="white",
                                  on_click=reset_click),
                ft.TextButton("Вернуться назад", on_click=lambda _: page.go("/"), style=ft.ButtonStyle(color="white"))
            ], horizontal_alignment="center", bgcolor="black"))

        elif page.route == "/register":
            reg_temp_avatar_url = ""
            r_fn = ft.TextField(label="Ваше Имя", width=300, border_color=ft.Colors.GREY_800)
            r_un = ft.TextField(label="Никнейм (обязательно с @)", width=300, border_color=ft.Colors.GREY_800)
            r_ps = ft.TextField(label="Придумайте Пароль", password=True, width=300, border_color=ft.Colors.GREY_800)
            r_gn = ft.Dropdown(label="Ваш Пол", width=300, border_color=ft.Colors.GREY_800,
                               options=[ft.dropdown.Option("Парень"), ft.dropdown.Option("Девушка")])
            r_bio = ft.TextField(label="Напиши о себе", width=300, multiline=True, max_lines=3,
                                 border_color=ft.Colors.GREY_800)
            avatar_preview = ft.CircleAvatar(radius=50, bgcolor=ft.Colors.GREY_900,
                                             content=ft.Icon(ft.Icons.PERSON, size=40))

            def on_reg_file_picked(e: ft.FilePickerResultEvent):
                nonlocal reg_temp_avatar_url
                if e.files:
                    show_msg("Загружаем ваше фото...", ft.Colors.BLUE_700)
                    url = upload_image_to_supabase(e.files[0].path, "reg_user")
                    if url:
                        reg_temp_avatar_url = url
                        avatar_preview.foreground_image_src = url
                        avatar_preview.content = None
                        show_msg("Фотография успешно сохранена!", ft.Colors.GREEN_700)
                        page.update()

            reg_file_picker = ft.FilePicker(on_result=on_reg_file_picked)
            page.overlay.append(reg_file_picker)

            def register_click(_):
                new_username = r_un.value.strip()
                if "@" not in new_username:
                    show_msg("Email введён некорректно, добавьте пожалуйста знак @", ft.Colors.RED_600)
                    return
                if not r_un.value or not r_ps.value or not r_fn.value or not reg_temp_avatar_url:
                    show_msg("Заполните профиль и добавьте фото!", ft.Colors.RED_600)
                    return
                fake_email = f"{new_username.replace('@', '')}@findcoup.local"
                data = {
                    "email": fake_email, "password": r_ps.value, "first_name": r_fn.value,
                    "username": new_username, "gender": r_gn.value, "bio": r_bio.value,
                    "avatar_url": reg_temp_avatar_url, "grade": "Школьник"
                }
                if safe_query(lambda: supabase.table("profiles").insert(data).execute()):
                    user_state.update(data)
                    page.go("/feed")
                else:
                    show_msg("Этот никнейм уже кем-то занят.", ft.Colors.RED_600)

            page.views.append(ft.View("/register", [
                ft.AppBar(title=ft.Text("Регистрация в FindCoup"), color="white", bgcolor="black"),
                ft.Column([
                    ft.Container(height=10),
                    ft.Stack([
                        avatar_preview,
                        ft.IconButton(ft.Icons.ADD_A_PHOTO, bgcolor=ft.Colors.RED, icon_color="white", top=65, right=-5,
                                      on_click=lambda _: reg_file_picker.pick_files(
                                          file_type=ft.FilePickerFileType.IMAGE))
                    ], width=110, height=110),
                    ft.Text("Нажмите для выбора аватара", color=ft.Colors.GREY_500, size=12),
                    r_fn, r_un, r_ps, r_gn, r_bio,
                    ft.ElevatedButton("ЗАРЕГИСТРИРОВАТЬСЯ", width=300, height=50, bgcolor=ft.Colors.RED, color="white",
                                      on_click=register_click),
                    ft.Container(height=20)
                ], horizontal_alignment="center", scroll=ft.ScrollMode.AUTO, spacing=15)
            ], bgcolor="black", horizontal_alignment="center"))

        elif page.route == "/feed":
            card_res = ft.Column(horizontal_alignment="center", spacing=15)

            def load_next(_=None):
                target = "Девушка" if user_state["gender"] == "Парень" else "Парень"
                res = safe_query(lambda: supabase.table("profiles").select("*").eq("gender", target).neq("username",
                                                                                                         user_state[
                                                                                                             "username"]).execute())
                if res and res.data:
                    u = random.choice(res.data)
                    card_res.data = u
                    card_res.controls = [
                        ft.Container(
                            ft.Image(src=u.get("avatar_url") or "https://via.placeholder.com/400", fit="cover"),
                            border_radius=25, height=450, width=350, border=ft.border.all(1, ft.Colors.GREY_900)),
                        ft.Text(f"{u['first_name']}, {u.get('grade', '')}", size=26, weight="bold", color="white"),
                        ft.Text(u.get("bio", "Нет описания"), italic=True, text_align="center", width=300,
                                color=ft.Colors.GREY_400),
                        ft.Text(f"{u['username']}", color=ft.Colors.RED, size=16, weight="bold")
                    ]
                else:
                    card_res.controls = [
                        ft.Container(ft.Text("Анкеты закончились! Зайдите позже.", color="white", size=18), padding=50)]
                page.update()

            def match_click(_):
                if not card_res.data: return
                target_email = card_res.data['email']
                safe_query(lambda: supabase.table("likes").insert(
                    {"from_email": user_state["email"], "to_email": target_email}).execute())
                check = safe_query(
                    lambda: supabase.table("likes").select("*").eq("from_email", target_email).eq("to_email",
                                                                                                  user_state[
                                                                                                      "email"]).execute())
                if check and check.data:
                    show_msg(f"Новый мэтч с {card_res.data['first_name']}!", ft.Colors.GREEN_700)
                load_next()

            page.views.append(ft.View("/feed", [
                ft.AppBar(title=ft.Text("Лента FindCoup", color=ft.Colors.RED, weight="bold"), bgcolor="black",
                          automatically_imply_leading=False),
                get_nav(0),
                ft.Container(card_res, padding=10, alignment=ft.alignment.center),
                ft.Row([
                    ft.IconButton(ft.Icons.CLOSE_ROUNDED, icon_size=45, icon_color="white", bgcolor=ft.Colors.GREY_900,
                                  on_click=load_next),
                    ft.Container(width=30),
                    ft.IconButton(ft.Icons.FAVORITE_ROUNDED, icon_size=55, icon_color="white", bgcolor=ft.Colors.RED,
                                  on_click=match_click)
                ], alignment="center")
            ], bgcolor="black", horizontal_alignment="center"))
            load_next()

        elif page.route == "/matches":
            match_list = ft.ListView(expand=True, spacing=10, padding=10)
            my_likes = safe_query(
                lambda: supabase.table("likes").select("to_email").eq("from_email", user_state["email"]).execute())
            if my_likes and my_likes.data:
                for item in my_likes.data:
                    mutual = safe_query(
                        lambda: supabase.table("likes").select("*").eq("from_email", item['to_email']).eq("to_email",
                                                                                                          user_state[
                                                                                                              "email"]).execute())
                    if mutual and mutual.data:
                        u_res = safe_query(lambda: supabase.table("profiles").select("*").eq("email", item[
                            'to_email']).single().execute())
                        if u_res:
                            u = u_res.data
                            match_list.controls.append(ft.ListTile(
                                leading=ft.CircleAvatar(foreground_image_src=u.get("avatar_url") or ""),
                                title=ft.Text(u['first_name'], color="white", weight="bold"),
                                subtitle=ft.Text(f"{u['username']}", color="grey"),
                                trailing=ft.IconButton(ft.Icons.CHAT_ROUNDED, icon_color=ft.Colors.RED,
                                                       on_click=lambda _, user=u: open_chat(user))
                            ))
            page.views.append(ft.View("/matches", [
                ft.AppBar(title=ft.Text("Ваши мэтчи", color="white"), bgcolor="black",
                          automatically_imply_leading=False),
                get_nav(1),
                match_list
            ], bgcolor="black"))

        elif page.route == "/messages":
            chats_list = ft.ListView(expand=True)
            msgs = safe_query(lambda: supabase.table("messages").select("sender_email, receiver_email").or_(
                f"sender_email.eq.{user_state['email']},receiver_email.eq.{user_state['email']}").execute())
            partners = {m['receiver_email'] if m['sender_email'] == user_state['email'] else m['sender_email'] for m in
                        msgs.data} if msgs else set()
            for p_email in partners:
                p_res = safe_query(
                    lambda: supabase.table("profiles").select("*").eq("email", p_email).single().execute())
                if p_res:
                    u = p_res.data
                    cnt = get_unread_for_user(p_email)
                    badge = ft.Container(content=ft.Text(str(cnt), size=10, weight="bold", color="white"),
                                         bgcolor=ft.Colors.RED, padding=5, border_radius=10, visible=cnt > 0)
                    chats_list.controls.append(ft.ListTile(
                        leading=ft.CircleAvatar(foreground_image_src=u.get("avatar_url") or ""),
                        title=ft.Text(u['first_name'], color="white"),
                        trailing=badge,
                        on_click=lambda _, user=u: open_chat(user)
                    ))
            page.views.append(ft.View("/messages", [
                ft.AppBar(title=ft.Text("Мессенджер", color="white"), bgcolor="black",
                          automatically_imply_leading=False),
                get_nav(2),
                chats_list
            ], bgcolor="black"))

        elif page.route == "/chat":
            chat_active = True
            msg_list = ft.ListView(expand=True, spacing=10, padding=10, auto_scroll=True)
            msg_in = ft.TextField(hint_text="Сообщение...", expand=True, border_color=ft.Colors.GREY_800, color="white",
                                  on_submit=lambda _: send_msg(None))

            def send_msg(_):
                if msg_in.value:
                    safe_query(lambda: supabase.table("messages").insert(
                        {"sender_email": user_state["email"], "receiver_email": current_chat_partner["email"],
                         "text": msg_in.value, "is_read": False}).execute())
                    msg_in.value = ""
                    page.update()
                    refresh_chat()

            def refresh_chat():
                if not chat_active: return
                mark_as_read(current_chat_partner["email"])
                res = safe_query(lambda: supabase.table("messages").select("*").or_(
                    f"and(sender_email.eq.{user_state['email']},receiver_email.eq.{current_chat_partner['email']}),and(sender_email.eq.{current_chat_partner['email']},receiver_email.eq.{user_state['email']})").order(
                    "created_at").execute())
                if res and res.data:
                    msg_list.controls = [ft.Row(
                        [ft.Container(content=ft.Text(m['text'], color="white"),
                                      bgcolor=ft.Colors.RED if m['sender_email'] == user_state[
                                          'email'] else ft.Colors.GREY_900, padding=12, border_radius=15)],
                        alignment=ft.MainAxisAlignment.END if m['sender_email'] == user_state[
                            'email'] else ft.MainAxisAlignment.START
                    ) for m in res.data]
                    try:
                        page.update()
                    except:
                        pass

            threading.Thread(target=lambda: (time.sleep(2), refresh_chat() if chat_active else None),
                             daemon=True).start()
            refresh_chat()
            page.views.append(ft.View("/chat", [
                ft.AppBar(title=ft.Row(
                    [ft.CircleAvatar(foreground_image_src=current_chat_partner.get("avatar_url", ""), radius=15),
                     ft.Text(f" {current_chat_partner['username']}")]), bgcolor="black",
                          leading=ft.IconButton(ft.Icons.ARROW_BACK, icon_color=ft.Colors.RED,
                                                on_click=lambda _: page.go("/messages"))),
                msg_list,
                ft.Container(
                    ft.Row([msg_in, ft.IconButton(ft.Icons.SEND_ROUNDED, icon_color=ft.Colors.RED, on_click=send_msg)]),
                    padding=15)
            ], bgcolor="black"))

        elif page.route == "/profile":
            p_un = ft.TextField(label="Никнейм", value=user_state["username"], border_color=ft.Colors.GREY_800)
            p_fn = ft.TextField(label="Имя", value=user_state["first_name"], border_color=ft.Colors.GREY_800)
            p_bio = ft.TextField(label="Описание", value=user_state.get("bio", ""), multiline=True,
                                 border_color=ft.Colors.GREY_800)

            def on_prof_file_picked(e: ft.FilePickerResultEvent):
                if e.files:
                    show_msg("Обновляем аватар...", ft.Colors.BLUE_700)
                    url = upload_image_to_supabase(e.files[0].path, f"upd_{user_state['username']}")
                    if url:
                        user_state["avatar_url"] = url
                        show_msg("Успешно! Нажмите сохранить.", ft.Colors.GREEN_700)
                        page.go("/profile")

            prof_file_picker = ft.FilePicker(on_result=on_prof_file_picked)
            page.overlay.append(prof_file_picker)

            def save_profile(_):
                data = {"username": p_un.value, "first_name": p_fn.value, "bio": p_bio.value,
                        "avatar_url": user_state["avatar_url"]}
                if safe_query(lambda: supabase.table("profiles").update(data).eq("username",
                                                                                 user_state["username"]).execute()):
                    user_state.update(data)
                    show_msg("Профиль обновлен!", ft.Colors.GREEN_700)

            page.views.append(ft.View("/profile", [
                ft.AppBar(title=ft.Text("Мой Профиль", color="white"), bgcolor="black",
                          automatically_imply_leading=False),
                get_nav(3),
                ft.Container(ft.Column([
                    ft.Stack([ft.CircleAvatar(foreground_image_src=user_state["avatar_url"], radius=70),
                              ft.IconButton(ft.Icons.EDIT, bgcolor=ft.Colors.RED, icon_color="white", top=100, right=0,
                                            on_click=lambda _: prof_file_picker.pick_files(
                                                file_type=ft.FilePickerFileType.IMAGE))]),
                    ft.TextButton("Обновить фото", icon=ft.Icons.UPLOAD, icon_color=ft.Colors.RED,
                                  style=ft.ButtonStyle(color="white"), on_click=lambda _: prof_file_picker.pick_files(
                            file_type=ft.FilePickerFileType.IMAGE)),
                    p_un, p_fn, p_bio,
                    ft.ElevatedButton("СОХРАНИТЬ", width=300, height=50, bgcolor=ft.Colors.RED, color="white",
                                      on_click=save_profile),
                    ft.TextButton("Выйти", style=ft.ButtonStyle(color=ft.Colors.RED), on_click=lambda _: page.go("/"))
                ], horizontal_alignment="center", spacing=15, scroll=ft.ScrollMode.AUTO), padding=20)
            ], bgcolor="black", horizontal_alignment="center"))

        page.update()

    def open_chat(u):
        current_chat_partner.update(
            {"email": u['email'], "username": u['username'], "avatar_url": u.get("avatar_url", "")})
        page.go("/chat")

    page.on_route_change = route_change
    page.go("/")

ft.app(target=main)
