import flet as ft
import httpx
import random
import asyncio
import time

# --- КОНФИГУРАЦИЯ ---
URL = "https://kgxvjlsojgkkhdaftncg.supabase.co"
KEY = "sb_publishable_2jhUvmgAKa-edfQyKSWlbA_nKxG65O0"
HEADERS = {
    "apikey": KEY,
    "Authorization": f"Bearer {KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

# Делаем main асинхронной
async def main(page: ft.Page):
    # 1. Настройки страницы
    page.title = "FindCoup Web"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = ft.Colors.BLACK
    page.window_width = 400
    page.window_height = 800
    
    # Глобальное состояние
    state = {
        "user": {},
        "partner": {},
        "is_chatting": False,
        "feed_data": []
    }

    # --- API ФУНКЦИИ ---
    async def api_get(table, params=""):
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(f"{URL}/rest/v1/{table}?{params}", headers=HEADERS)
                if r.status_code == 200: return r.json()
        except Exception as e:
            print(f"GET Error: {e}")
        return []

    async def api_post(table, data):
        try:
            async with httpx.AsyncClient() as client:
                r = await client.post(f"{URL}/rest/v1/{table}", headers=HEADERS, json=data)
                return r.status_code in [200, 201]
        except: return False

    def show_snack(text, color=ft.Colors.RED):
        page.snack_bar = ft.SnackBar(ft.Text(text), bgcolor=color)
        page.snack_bar.open = True
        page.update()

    # --- ИСПРАВЛЕННАЯ НАВИГАЦИЯ (Async Wrappers) ---
    # Flet в браузере требует явных асинхронных функций для событий
    async def go_home(e): await page.push_route("/")
    async def go_reg(e): await page.push_route("/reg")
    async def go_matches(e): await page.push_route("/matches")
    async def go_feed(e): await page.push_route("/feed")

    # Навигационный бар
    async def on_nav_change(e):
        idx = e.control.selected_index
        routes = ["/feed", "/matches", "/messages", "/profile"]
        if idx < len(routes):
            await page.push_route(routes[idx])

    def get_nav(idx):
        return ft.NavigationBar(
            selected_index=idx,
            on_change=on_nav_change,
            destinations=[
                ft.NavigationDestination(icon=ft.Icons.EXPLORE, label="Лента"),
                ft.NavigationDestination(icon=ft.Icons.FAVORITE, label="Мэтчи"),
                ft.NavigationDestination(icon=ft.Icons.CHAT_BUBBLE, label="Чаты"),
                ft.NavigationDestination(icon=ft.Icons.PERSON, label="Профиль"),
            ],
            bgcolor=ft.Colors.BLACK,
            indicator_color=ft.Colors.RED_900
        )

    # --- ЛОГИКА ЧАТА ---
    async def chat_loop(msg_list):
        while True:
            if state["is_chatting"]:
                try:
                    my_email = state["user"]["email"]
                    p_email = state["partner"]["email"]
                    # Формируем запрос сообщений между двумя людьми
                    query = f"or=(and(sender_email.eq.{my_email},receiver_email.eq.{p_email}),and(sender_email.eq.{p_email},receiver_email.eq.{my_email}))&order=created_at.asc"
                    
                    msgs = await api_get("messages", query)
                    
                    if msgs:
                        # Обновляем только если количество изменилось
                        if len(msg_list.controls) != len(msgs):
                            msg_list.controls.clear()
                            for m in msgs:
                                is_me = m['sender_email'] == my_email
                                msg_list.controls.append(
                                    ft.Row(
                                        [ft.Container(
                                            content=ft.Text(m['text'], color="white"),
                                            bgcolor=ft.Colors.RED_700 if is_me else ft.Colors.GREY_900,
                                            padding=10, border_radius=10,
                                            width=200 if len(m['text']) > 30 else None
                                        )],
                                        alignment=ft.MainAxisAlignment.END if is_me else ft.MainAxisAlignment.START
                                    )
                                )
                            page.update()
                except Exception as e:
                    print(f"Chat loop error: {e}")
            
            await asyncio.sleep(3)

    # --- МАРШРУТИЗАЦИЯ ---
    async def route_change(route):
        state["is_chatting"] = False
        page.views.clear()
        
        troute = page.route
        
        # 1. ВХОД
        if troute == "/":
            un = ft.TextField(label="Никнейм (@)", width=300, border_radius=10)
            ps = ft.TextField(label="Пароль", password=True, width=300, border_radius=10)
            
            async def login_click(e):
                if not un.value or "@" not in un.value:
                    show_snack("Никнейм должен содержать @")
                    return
                
                btn_login.text = "Входим..."
                btn_login.disabled = True
                page.update()
                
                users = await api_get("profiles", f"username=eq.{un.value}")
                
                if users and str(users[0]['password']) == ps.value:
                    state["user"] = users[0]
                    await page.push_route("/feed") # ВАЖНО: await
                else:
                    show_snack("Неверные данные")
                    btn_login.text = "ВОЙТИ"
                    btn_login.disabled = False
                    page.update()

            btn_login = ft.ElevatedButton("ВОЙТИ", on_click=login_click, width=300, bgcolor="red", color="white")

            page.views.append(ft.View("/", [
                ft.Column([
                    ft.Icon(ft.Icons.FAVORITE, color="red", size=80),
                    ft.Text("FindCoup Web", size=30, weight="bold"),
                    un, ps,
                    btn_login,
                    ft.TextButton("Регистрация", on_click=go_reg)
                ], horizontal_alignment="center", alignment="center")
            ], horizontal_alignment="center", vertical_alignment="center"))

        # 2. РЕГИСТРАЦИЯ
        elif troute == "/reg":
            r_un = ft.TextField(label="Никнейм (@)", width=300)
            r_ps = ft.TextField(label="Пароль", password=True, width=300)
            r_fn = ft.TextField(label="Имя", width=300)
            r_gn = ft.Dropdown(label="Пол", width=300, options=[ft.dropdown.Option("Парень"), ft.dropdown.Option("Девушка")])
            
            def get_random_avatar():
                seed = str(time.time())
                return f"https://api.dicebear.com/9.x/avataaars/svg?seed={seed}"

            temp_avatar = get_random_avatar()
            img_preview = ft.Image(src=temp_avatar, width=100, height=100, border_radius=50)

            def refresh_avatar(_):
                nonlocal temp_avatar
                temp_avatar = get_random_avatar()
                img_preview.src = temp_avatar
                page.update()

            async def reg_click(_):
                if not r_un.value or not r_ps.value: return
                data = {
                    "username": r_un.value, "password": r_ps.value,
                    "first_name": r_fn.value, "gender": r_gn.value,
                    "email": f"{r_un.value.replace('@','')}@local.test",
                    "avatar_url": temp_avatar, "bio": "Я новенький!", "grade": "Новичок"
                }
                success = await api_post("profiles", data)
                if success:
                    state["user"] = data
                    await page.push_route("/feed") # ВАЖНО: await
                else:
                    show_snack("Ошибка регистрации")

            page.views.append(ft.View("/reg", [
                ft.Column([
                    ft.Text("Регистрация", size=24, weight="bold"),
                    img_preview,
                    ft.TextButton("Другой аватар", on_click=refresh_avatar),
                    r_un, r_ps, r_fn, r_gn,
                    ft.ElevatedButton("СОЗДАТЬ", on_click=reg_click, width=300, bgcolor="red", color="white"),
                    ft.TextButton("Назад", on_click=go_home)
                ], horizontal_alignment="center", scroll=ft.ScrollMode.AUTO)
            ], horizontal_alignment="center"))

        # 3. ЛЕНТА
        elif troute == "/feed":
            card_col = ft.Column(horizontal_alignment="center")
            
            async def load_next(_=None):
                target = "Девушка" if state["user"]["gender"] == "Парень" else "Парень"
                if not state["feed_data"]:
                    users = await api_get("profiles", f"gender=eq.{target}&limit=20")
                    if users:
                        # Фильтруем себя
                        state["feed_data"] = [u for u in users if u['username'] != state["user"]['username']]
                        random.shuffle(state["feed_data"])
                
                if state["feed_data"]:
                    u = state["feed_data"].pop()
                    card_col.data = u 
                    card_col.controls = [
                        ft.Container(
                            content=ft.Image(src=u.get('avatar_url'), fit="cover"),
                            width=300, height=400, border_radius=20, border=ft.border.all(2, "grey")
                        ),
                        ft.Text(f"{u['first_name']}, {u['username']}", size=24, weight="bold"),
                    ]
                else:
                    card_col.controls = [ft.Text("Анкеты закончились!", size=20)]
                page.update()

            async def like_click(_):
                if not getattr(card_col, 'data', None): return
                target = card_col.data
                await api_post("likes", {"from_email": state["user"]["email"], "to_email": target["email"]})
                # Проверка взаимности
                check = await api_get("likes", f"from_email=eq.{target['email']}&to_email=eq.{state['user']['email']}")
                if check: show_snack(f"Мэтч с {target['first_name']}!", ft.Colors.GREEN)
                await load_next()

            page.views.append(ft.View("/feed", [
                ft.AppBar(title=ft.Text("Лента"), bgcolor="black", automatically_imply_leading=False),
                ft.Container(card_col, expand=True, alignment=ft.alignment.center),
                ft.Row([
                    ft.IconButton(ft.Icons.CLOSE, icon_size=40, on_click=load_next),
                    ft.IconButton(ft.Icons.FAVORITE, icon_size=40, icon_color="red", on_click=like_click)
                ], alignment="center", height=80),
                get_nav(0)
            ], bgcolor="black"))
            
            if not card_col.controls:
                await asyncio.sleep(0.1)
                await load_next()

        # 4. МЭТЧИ
        elif troute == "/matches":
            lst = ft.ListView(expand=True)
            page.views.append(ft.View("/matches", [
                ft.AppBar(title=ft.Text("Ваши пары"), bgcolor="black", automatically_imply_leading=False),
                lst,
                get_nav(1)
            ], bgcolor="black"))
            
            likes = await api_get("likes", f"to_email=eq.{state['user']['email']}")
            for l in likes:
                mutual = await api_get("likes", f"from_email=eq.{state['user']['email']}&to_email=eq.{l['from_email']}")
                if mutual:
                    u = await api_get("profiles", f"email=eq.{l['from_email']}")
                    if u:
                        # Замыкание для передачи данных в обработчик
                        def open_chat_closure(clicked_user):
                            async def handler(_):
                                state["partner"] = clicked_user
                                await page.push_route("/chat")
                            return handler

                        lst.controls.append(ft.ListTile(
                            leading=ft.CircleAvatar(src=u[0]['avatar_url']),
                            title=ft.Text(u[0]['first_name']),
                            subtitle=ft.Text(f"@{u[0]['username']}"),
                            on_click=open_chat_closure(u[0])
                        ))
            page.update()
        
        # 5. MESSAGES
        elif troute == "/messages":
             await page.push_route("/matches")

        # 6. ЧАТ
        elif troute == "/chat":
            state["is_chatting"] = True
            msg_list = ft.ListView(expand=True, auto_scroll=True, spacing=10)
            txt_in = ft.TextField(hint_text="...", expand=True, border_radius=20)
            
            async def send_click(_):
                if not txt_in.value: return
                val = txt_in.value
                txt_in.value = ""
                page.update()
                await api_post("messages", {
                    "sender_email": state["user"]["email"],
                    "receiver_email": state["partner"]["email"],
                    "text": val,
                    "is_read": False
                })

            page.views.append(ft.View("/chat", [
                ft.AppBar(title=ft.Text(state["partner"].get("first_name", "Чат")), bgcolor="black", 
                         leading=ft.IconButton(ft.Icons.ARROW_BACK, on_click=go_matches)),
                ft.Container(msg_list, expand=True, padding=10),
                ft.Container(ft.Row([txt_in, ft.IconButton(ft.Icons.SEND, icon_color="red", on_click=send_click)]), padding=10)
            ], bgcolor="black"))
            
            # Запускаем фоновую задачу чата
            asyncio.create_task(chat_loop(msg_list))

        elif troute == "/profile":
            u = state["user"]
            page.views.append(ft.View("/profile", [
                ft.AppBar(title=ft.Text("Профиль"), bgcolor="black", automatically_imply_leading=False),
                ft.Container(ft.Column([
                    ft.CircleAvatar(src=u['avatar_url'], radius=60),
                    ft.Text(u['first_name'], size=20, weight="bold"),
                    ft.Text("@" + u['username'], color="grey"),
                    ft.TextButton("Выход", on_click=go_home)
                ], horizontal_alignment="center", spacing=20), padding=20),
                get_nav(3)
            ], bgcolor="black"))

        page.update()

    page.on_route_change = route_change
    # Запускаем начальный маршрут с await
    await page.push_route("/")

# Запуск приложения (предупреждение будет, но оно безопасно)
ft.app(target=main, view=ft.AppView.WEB_BROWSER, web_renderer="html")
