import flet as ft
import httpx
import random
import asyncio
import time
import base64

# --- КОНФИГУРАЦИЯ SUPABASE ---
URL = "https://kgxvjlsojgkkhdaftncg.supabase.co"
# Убедитесь, что этот ключ рабочий и имеет права на запись в Storage
KEY = "sb_publishable_2jhUvmgAKa-edfQyKSWlbA_nKxG65O0"
HEADERS = {
    "apikey": KEY,
    "Authorization": f"Bearer {KEY}",
    "Prefer": "return=representation"
}


async def main(page: ft.Page):
    # Настройки страницы
    page.title = "FindCoup Web"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = ft.Colors.BLACK
    page.padding = 0  # Убираем отступы для фуллскрина

    # Глобальное состояние
    state = {
        "user": {},
        "partner": {},
        "is_chatting": False,
        "feed_data": [],
        "upload_file_name": None,
        "upload_file_bytes": None,
        "current_tab": 0  # Для навигации
    }

    # --- ИНИЦИАЛИЗАЦИЯ FILE PICKER (ВАЖНО: В САМОМ НАЧАЛЕ) ---
    async def on_file_picked(e: ft.FilePickerResultEvent):
        if e.files and len(e.files) > 0:
            file_obj = e.files[0]
            if file_obj.content:  # Для веба контент приходит в base64
                try:
                    # data:image/jpeg;base64,/9j/4AAQ... -> берем часть после запятой
                    b64_str = file_obj.content.split(",")[1]
                    state["upload_file_bytes"] = base64.b64decode(b64_str)
                    state["upload_file_name"] = file_obj.name

                    # Обновляем превью
                    if img_preview:
                        img_preview.src_base64 = b64_str
                        img_preview.src = ""
                        btn_upload.text = "Фото выбрано!"
                        btn_upload.icon = ft.Icons.CHECK
                        await page.update_async()
                except Exception as err:
                    print(f"Ошибка чтения файла: {err}")

    file_picker = ft.FilePicker(on_result=on_file_picked)
    page.overlay.append(file_picker)  # Добавляем в оверлей сразу

    # --- API ФУНКЦИИ ---
    async def api_get(table, params=""):
        try:
            headers = HEADERS.copy()
            headers["Content-Type"] = "application/json"
            async with httpx.AsyncClient() as client:
                r = await client.get(f"{URL}/rest/v1/{table}?{params}", headers=headers)
                if r.status_code == 200: return r.json()
        except Exception as e:
            print(f"GET Error: {e}")
        return []

    async def api_post_json(table, data):
        try:
            headers = HEADERS.copy()
            headers["Content-Type"] = "application/json"
            async with httpx.AsyncClient() as client:
                r = await client.post(f"{URL}/rest/v1/{table}", headers=headers, json=data)
                return r.status_code in [200, 201]
        except:
            return False

    # Функция для обновления статуса сообщений (Прочитано)
    async def api_mark_read(sender, receiver):
        try:
            headers = HEADERS.copy()
            headers["Content-Type"] = "application/json"
            # PATCH запрос: обновить is_read=True где отправитель=ОН и получатель=Я
            query = f"sender_email=eq.{sender}&receiver_email=eq.{receiver}&is_read=eq.false"
            async with httpx.AsyncClient() as client:
                await client.patch(f"{URL}/rest/v1/messages?{query}", headers=headers, json={"is_read": True})
        except:
            pass

    async def api_upload_file(bucket, filename, file_bytes):
        try:
            upload_url = f"{URL}/storage/v1/object/{bucket}/{filename}"
            headers = HEADERS.copy()
            # Определяем тип (упрощенно)
            ctype = "image/png" if filename.endswith(".png") else "image/jpeg"
            headers["Content-Type"] = ctype
            if "Prefer" in headers: del headers["Prefer"]

            async with httpx.AsyncClient() as client:
                r = await client.post(upload_url, headers=headers, content=file_bytes)
                if r.status_code == 200:
                    return f"{URL}/storage/v1/object/public/{bucket}/{filename}"
        except Exception as e:
            print(f"Upload Error: {e}")
        return None

    async def show_snack(text, color=ft.Colors.RED):
        page.snack_bar = ft.SnackBar(ft.Text(text), bgcolor=color)
        page.snack_bar.open = True
        await page.update_async()

    # --- НАВИГАЦИЯ ---
    async def on_nav_change(e):
        idx = e.control.selected_index
        # 0: Feed, 1: Matches, 2: Chats, 3: Profile
        routes = ["/feed", "/matches", "/chats_list", "/profile"]
        if idx < len(routes):
            # Если уходим из чата, останавливаем обновление
            state["is_chatting"] = False
            await page.push_route_async(routes[idx])

    def get_nav(idx):
        return ft.NavigationBar(
            selected_index=idx,
            on_change=on_nav_change,
            destinations=[
                ft.NavigationDestination(icon=ft.Icons.EXPLORE, label="Лента"),
                ft.NavigationDestination(icon=ft.Icons.FAVORITE, label="Мэтчи"),
                ft.NavigationDestination(icon=ft.Icons.CHAT_BUBBLE, label="Чаты"),  # Новая вкладка
                ft.NavigationDestination(icon=ft.Icons.PERSON, label="Профиль"),
            ],
            bgcolor=ft.Colors.BLACK,
            indicator_color=ft.Colors.RED_900
        )

    # --- ФОНОВАЯ ЗАДАЧА ЧАТА ---
    async def chat_loop(msg_list):
        while state["is_chatting"]:
            try:
                my_email = state["user"]["email"]
                p_email = state["partner"]["email"]
                query = f"or=(and(sender_email.eq.{my_email},receiver_email.eq.{p_email}),and(sender_email.eq.{p_email},receiver_email.eq.{my_email}))&order=created_at.asc"

                msgs = await api_get("messages", query)
                if msgs and len(msg_list.controls) != len(msgs):
                    msg_list.controls.clear()
                    for m in msgs:
                        is_me = m['sender_email'] == my_email
                        # Сообщение
                        msg_bubble = ft.Container(
                            content=ft.Text(m['text'], color="white"),
                            bgcolor=ft.Colors.RED_900 if is_me else ft.Colors.GREY_900,
                            padding=10, border_radius=10,
                            width=250 if len(m['text']) > 30 else None
                        )
                        msg_list.controls.append(
                            ft.Row([msg_bubble],
                                   alignment=ft.MainAxisAlignment.END if is_me else ft.MainAxisAlignment.START)
                        )
                    await page.update_async()
            except:
                pass
            await asyncio.sleep(2)

    # --- ROUTING ---
    async def route_change(route):
        state["is_chatting"] = False
        page.views.clear()
        troute = page.route

        # 1. ВХОД
        if troute == "/":
            un = ft.TextField(label="Никнейм (@)", width=300)
            ps = ft.TextField(label="Пароль", password=True, width=300)

            async def login_click(e):
                if not un.value: return
                users = await api_get("profiles", f"username=eq.{un.value}")
                if users and str(users[0]['password']) == ps.value:
                    state["user"] = users[0]
                    await page.push_route_async("/feed")
                else:
                    await show_snack("Ошибка входа")

            page.views.append(ft.View("/", [
                ft.Column([
                    ft.Icon(ft.Icons.FAVORITE, color="red", size=80),
                    ft.Text("FindCoup", size=32, weight="bold"),
                    un, ps,
                    ft.ElevatedButton("ВОЙТИ", on_click=login_click, width=300, bgcolor="red", color="white"),
                    ft.TextButton("Регистрация", on_click=lambda _: page.push_route_async("/reg"))
                ], horizontal_alignment="center", alignment="center")
            ], horizontal_alignment="center", vertical_alignment="center"))

        # 2. РЕГИСТРАЦИЯ (ИСПРАВЛЕНО)
        elif troute == "/reg":
            state["upload_file_bytes"] = None  # Сброс

            # Глобальные переменные для доступа из on_file_picked
            global img_preview, btn_upload

            r_un = ft.TextField(label="Никнейм (без @)", width=300)
            r_ps = ft.TextField(label="Пароль", password=True, width=300)
            r_fn = ft.TextField(label="Имя", width=300)
            r_gn = ft.Dropdown(label="Пол", width=300,
                               options=[ft.dropdown.Option("Парень"), ft.dropdown.Option("Девушка")])

            img_preview = ft.Image(src=f"https://api.dicebear.com/9.x/avataaars/svg?seed={random.randint(0, 1000)}",
                                   width=100, height=100, border_radius=50)

            # Кнопка вызывает pick_files_async
            async def upload_click(e):
                await file_picker.pick_files_async(allow_multiple=False, file_type=ft.FilePickerFileType.IMAGE)

            btn_upload = ft.ElevatedButton("Загрузить фото", icon=ft.Icons.UPLOAD, on_click=upload_click, width=300)

            async def reg_submit(e):
                if not r_un.value: return

                avatar_url = img_preview.src
                # Если файл выбран, загружаем
                if state["upload_file_bytes"]:
                    fname = f"{r_un.value}_{int(time.time())}.jpg"
                    res_url = await api_upload_file("avatars", fname, state["upload_file_bytes"])
                    if res_url: avatar_url = res_url

                data = {
                    "username": r_un.value, "password": r_ps.value, "first_name": r_fn.value,
                    "gender": r_gn.value, "email": f"{r_un.value}@local.test", "avatar_url": avatar_url
                }

                if await api_post_json("profiles", data):
                    state["user"] = data
                    await page.push_route_async("/feed")
                else:
                    await show_snack("Ошибка регистрации")

            page.views.append(ft.View("/reg", [
                ft.AppBar(title=ft.Text("Новый аккаунт"), bgcolor="black"),
                ft.Column([
                    ft.Container(img_preview, padding=10),
                    btn_upload,  # Кнопка теперь точно здесь
                    r_un, r_ps, r_fn, r_gn,
                    ft.ElevatedButton("ГОТОВО", on_click=reg_submit, width=300, bgcolor="red", color="white")
                ], horizontal_alignment="center", scroll=ft.ScrollMode.AUTO)
            ], horizontal_alignment="center"))

        # 3. ЛЕНТА
        elif troute == "/feed":
            card_col = ft.Column(horizontal_alignment="center")

            async def load_card():
                # Простая логика загрузки
                target = "Девушка" if state["user"]["gender"] == "Парень" else "Парень"
                users = await api_get("profiles", f"gender=eq.{target}&limit=30")
                if users:
                    # Убираем себя и перемешиваем
                    valid = [u for u in users if u['username'] != state["user"]['username']]
                    if valid:
                        u = random.choice(valid)  # Берем случайного
                        card_col.data = u
                        card_col.controls = [
                            ft.Container(ft.Image(src=u['avatar_url'], width=300, height=400, fit=ft.ImageFit.COVER,
                                                  border_radius=20)),
                            ft.Text(f"{u['first_name']}, {u['username']}", size=24, weight="bold")
                        ]
                    else:
                        card_col.controls = [ft.Text("Никого нет :(")]
                await page.update_async()

            async def do_like(e):
                if not card_col.data: return
                target = card_col.data
                await api_post_json("likes", {"from_email": state["user"]["email"], "to_email": target["email"]})
                # Проверка мэтча
                check = await api_get("likes", f"from_email=eq.{target['email']}&to_email=eq.{state['user']['email']}")
                if check: await show_snack("Это МЭТЧ!", ft.Colors.GREEN)
                await load_card()

            page.views.append(ft.View("/feed", [
                ft.AppBar(title=ft.Text("FindCoup"), automatically_imply_leading=False, bgcolor="black"),
                ft.Container(card_col, expand=True, alignment=ft.alignment.center),
                ft.Row([
                    ft.IconButton(ft.Icons.CLOSE, icon_size=40, on_click=lambda _: asyncio.create_task(load_card())),
                    ft.IconButton(ft.Icons.FAVORITE, icon_size=40, icon_color="red", on_click=do_like)
                ], alignment="center"),
                get_nav(0)
            ], bgcolor="black"))
            asyncio.create_task(load_card())

        # 4. МЭТЧИ (Просто список лиц)
        elif troute == "/matches":
            grid = ft.GridView(expand=True, runs_count=2, max_extent=150, spacing=10, run_spacing=10)

            my_likes = await api_get("likes", f"from_email=eq.{state['user']['email']}")
            for l in my_likes:
                mutual = await api_get("likes", f"from_email=eq.{l['to_email']}&to_email=eq.{state['user']['email']}")
                if mutual:
                    u_list = await api_get("profiles", f"email=eq.{l['to_email']}")
                    if u_list:
                        u = u_list[0]

                        async def to_chat(e, user=u):
                            state["partner"] = user
                            # При входе помечаем прочитанным
                            await api_mark_read(user['email'], state["user"]["email"])
                            await page.push_route_async("/chat")

                        grid.controls.append(ft.Container(
                            content=ft.Column([
                                ft.CircleAvatar(src=u['avatar_url'], radius=40),
                                ft.Text(u['first_name'], weight="bold")
                            ], horizontal_alignment="center"),
                            bgcolor=ft.Colors.GREY_900, border_radius=10, padding=10,
                            on_click=to_chat
                        ))

            page.views.append(ft.View("/matches", [
                ft.AppBar(title=ft.Text("Ваши пары"), automatically_imply_leading=False, bgcolor="black"),
                ft.Container(grid, expand=True, padding=10),
                get_nav(1)
            ], bgcolor="black"))
            await page.update_async()

        # 5. СПИСОК ЧАТОВ (НОВАЯ ВКЛАДКА)
        elif troute == "/chats_list":
            lv = ft.ListView(expand=True)

            # Получаем список тех, с кем есть мэтч
            my_likes = await api_get("likes", f"from_email=eq.{state['user']['email']}")
            matches = []

            # Собираем пользователей
            for l in my_likes:
                mutual = await api_get("likes", f"from_email=eq.{l['to_email']}&to_email=eq.{state['user']['email']}")
                if mutual:
                    u_list = await api_get("profiles", f"email=eq.{l['to_email']}")
                    if u_list: matches.append(u_list[0])

            # Для каждого мэтча считаем непрочитанные
            for m in matches:
                # Получаем все непрочитанные сообщения от этого пользователя ко мне
                unread_msgs = await api_get("messages",
                                            f"sender_email=eq.{m['email']}&receiver_email=eq.{state['user']['email']}&is_read=eq.false")
                count = len(unread_msgs) if unread_msgs else 0

                trailing = None
                if count > 0:
                    trailing = ft.Container(
                        content=ft.Text(str(count), color="white", size=12),
                        bgcolor="red", border_radius=10, padding=5, width=25, height=25, alignment=ft.alignment.center
                    )

                async def open_chat_wrapper(e, user=m):
                    state["partner"] = user
                    # Сразу помечаем прочитанным
                    await api_mark_read(user['email'], state["user"]["email"])
                    await page.push_route_async("/chat")

                lv.controls.append(ft.ListTile(
                    leading=ft.CircleAvatar(src=m['avatar_url']),
                    title=ft.Text(m['first_name']),
                    subtitle=ft.Text("Нажмите, чтобы открыть чат"),
                    trailing=trailing,
                    on_click=open_chat_wrapper
                ))

            if not matches:
                lv.controls.append(ft.Text("У вас пока нет активных пар", text_align="center"))

            page.views.append(ft.View("/chats_list", [
                ft.AppBar(title=ft.Text("Сообщения"), automatically_imply_leading=False, bgcolor="black"),
                lv,
                get_nav(2)
            ], bgcolor="black"))
            await page.update_async()

        # 6. ЧАТ
        elif troute == "/chat":
            state["is_chatting"] = True
            msgs = ft.ListView(expand=True, spacing=10, padding=10)
            tf = ft.TextField(hint_text="...", expand=True, border_radius=20)

            async def send_click(e):
                if not tf.value: return
                await api_post_json("messages", {
                    "sender_email": state["user"]["email"],
                    "receiver_email": state["partner"]["email"],
                    "text": tf.value,
                    "is_read": False
                })
                tf.value = ""
                await page.update_async()

            page.views.append(ft.View("/chat", [
                ft.AppBar(title=ft.Text(state["partner"]["first_name"]), bgcolor="black"),
                msgs,
                ft.Container(ft.Row([tf, ft.IconButton(ft.Icons.SEND, on_click=send_click)]), padding=10)
            ], bgcolor="black"))
            asyncio.create_task(chat_loop(msgs))

        # 7. ПРОФИЛЬ
        elif troute == "/profile":
            u = state["user"]
            page.views.append(ft.View("/profile", [
                ft.AppBar(title=ft.Text("Профиль"), automatically_imply_leading=False, bgcolor="black"),
                ft.Column([
                    ft.CircleAvatar(src=u['avatar_url'], radius=60),
                    ft.Text(u['first_name'], size=24),
                    ft.Text("@" + u['username'], color="grey"),
                    ft.ElevatedButton("Выйти", on_click=lambda _: page.push_route_async("/"), color="red")
                ], horizontal_alignment="center"),
                get_nav(3)
            ], bgcolor="black", horizontal_alignment="center"))

        await page.update_async()

    page.on_route_change = route_change
    await page.push_route_async("/")


ft.app(target=main, view=ft.AppView.WEB_BROWSER)
