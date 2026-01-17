import flet as ft
import httpx
import random
import asyncio
import time

# --- КОНФИГУРАЦИЯ SUPABASE ---
URL = "https://kgxvjlsojgkkhdaftncg.supabase.co"
KEY = "sb_publishable_2jhUvmgAKa-edfQyKSWlbA_nKxG65O0"
HEADERS = {
    "apikey": KEY,
    "Authorization": f"Bearer {KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

async def main(page: ft.Page):
    # Настройки страницы
    page.title = "FindCoup Web"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = ft.Colors.BLACK
    
    # Глобальное состояние приложения
    state = {
        "user": {},
        "partner": {},
        "is_chatting": False,
        "feed_data": []
    }

    # --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ API ---
    async def api_get(table, params=""):
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(f"{URL}/rest/v1/{table}?{params}", headers=HEADERS)
                if r.status_code == 200:
                    return r.json()
        except Exception as e:
            print(f"Ошибка запроса: {e}")
        return []

    async def api_post(table, data):
        try:
            async with httpx.AsyncClient() as client:
                r = await client.post(f"{URL}/rest/v1/{table}", headers=HEADERS, json=data)
                return r.status_code in [200, 201]
        except:
            return False

    async def show_snack(text, color=ft.Colors.RED):
        page.snack_bar = ft.SnackBar(ft.Text(text), bgcolor=color)
        page.snack_bar.open = True
        await page.update_async()

    # --- НАВИГАЦИОННЫЕ ФУНКЦИИ (Исправляют ошибки с await) ---
    async def go_home(e): await page.push_route_async("/")
    async def go_reg(e): await page.push_route_async("/reg")
    async def go_matches(e): await page.push_route_async("/matches")
    async def go_feed(e): await page.push_route_async("/feed")

    async def on_nav_change(e):
        idx = e.control.selected_index
        routes = ["/feed", "/matches", "/messages", "/profile"]
        await page.push_route_async(routes[idx])

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
                        msg_list.controls.append(
                            ft.Row(
                                [ft.Container(
                                    content=ft.Text(m['text'], color="white"),
                                    bgcolor=ft.Colors.RED_700 if is_me else ft.Colors.GREY_900,
                                    padding=10, border_radius=10,
                                )],
                                alignment=ft.MainAxisAlignment.END if is_me else ft.MainAxisAlignment.START
                            )
                        )
                    await page.update_async()
            except: pass
            await asyncio.sleep(2)

    # --- ОБРАБОТЧИК МАРШРУТОВ (ГЛАВНАЯ ЛОГИКА) ---
    async def route_change(route):
        state["is_chatting"] = False # Останавливаем чат при смене экрана
        page.views.clear()
        
        # 1. ЭКРАН ВХОДА
        if page.route == "/":
            un = ft.TextField(label="Никнейм (@)", width=300)
            ps = ft.TextField(label="Пароль", password=True, width=300)
            
            async def login_click(e):
                if not un.value: return
                users = await api_get("profiles", f"username=eq.{un.value}")
                if users and str(users[0]['password']) == ps.value:
                    state["user"] = users[0]
                    await page.push_route_async("/feed")
                else:
                    await show_snack("Неверные данные")

            page.views.append(ft.View("/", [
                ft.Column([
                    ft.Icon(ft.Icons.FAVORITE, color="red", size=80),
                    ft.Text("FindCoup", size=32, weight="bold"),
                    un, ps,
                    ft.ElevatedButton("ВОЙТИ", on_click=login_click, width=300, bgcolor="red", color="white"),
                    ft.TextButton("Нет аккаунта? Регистрация", on_click=go_reg)
                ], horizontal_alignment="center", alignment="center")
            ], horizontal_alignment="center", vertical_alignment="center"))

        # 2. ЭКРАН РЕГИСТРАЦИИ
        elif page.route == "/reg":
            r_un = ft.TextField(label="Никнейм (@)", width=300)
            r_ps = ft.TextField(label="Пароль", width=300)
            r_fn = ft.TextField(label="Имя", width=300)
            r_gn = ft.Dropdown(label="Пол", width=300, options=[ft.dropdown.Option("Парень"), ft.dropdown.Option("Девушка")])
            
            async def reg_submit(e):
                data = {
                    "username": r_un.value, "password": r_ps.value, "first_name": r_fn.value,
                    "gender": r_gn.value, "email": f"{r_un.value}@fcup.local",
                    "avatar_url": f"https://api.dicebear.com/9.x/avataaars/svg?seed={r_un.value}"
                }
                if await api_post("profiles", data):
                    state["user"] = data
                    await page.push_route_async("/feed")
                else:
                    await show_snack("Ошибка регистрации")

            page.views.append(ft.View("/reg", [
                ft.AppBar(title=ft.Text("Создать аккаунт"), bgcolor="black"),
                ft.Column([r_un, r_ps, r_fn, r_gn, 
                          ft.ElevatedButton("ГОТОВО", on_click=reg_submit, width=300, bgcolor="red", color="white")],
                          horizontal_alignment="center")
            ], horizontal_alignment="center"))

        # 3. ЛЕНТА
        elif page.route == "/feed":
            card_res = ft.Column(horizontal_alignment="center")
            
            async def load_user():
                target = "Девушка" if state["user"]["gender"] == "Парень" else "Парень"
                users = await api_get("profiles", f"gender=eq.{target}&limit=1")
                if users:
                    u = users[0]
                    card_res.data = u
                    card_res.controls = [
                        ft.Container(ft.Image(src=u['avatar_url'], width=300, height=400, fit="cover"), border_radius=20),
                        ft.Text(f"{u['first_name']}, @{u['username']}", size=24, weight="bold")
                    ]
                else:
                    card_res.controls = [ft.Text("Никого не нашли :(")]
                await page.update_async()

            async def on_like(e):
                if hasattr(card_res, "data"):
                    await api_post("likes", {"from_email": state["user"]["email"], "to_email": card_res.data["email"]})
                    await load_user()

            page.views.append(ft.View("/feed", [
                ft.AppBar(title=ft.Text("FindCoup"), automatically_imply_leading=False),
                ft.Container(card_res, expand=True, alignment=ft.alignment.center),
                ft.Row([
                    ft.IconButton(ft.Icons.CLOSE, icon_size=40, on_click=lambda _: asyncio.create_task(load_user())),
                    ft.IconButton(ft.Icons.FAVORITE, icon_size=40, icon_color="red", on_click=on_like)
                ], alignment="center"),
                get_nav(0)
            ]))
            asyncio.create_task(load_user())

        # 4. МЭТЧИ
        elif page.route == "/matches":
            lst = ft.ListView(expand=True)
            page.views.append(ft.View("/matches", [
                ft.AppBar(title=ft.Text("Ваши симпатии"), automatically_imply_leading=False),
                lst, get_nav(1)
            ]))
            
            res = await api_get("likes", f"to_email=eq.{state['user']['email']}")
            for l in res:
                u = await api_get("profiles", f"email=eq.{l['from_email']}")
                if u:
                    async def open_chat(e, p=u[0]):
                        state["partner"] = p
                        await page.push_route_async("/chat")
                    
                    lst.controls.append(ft.ListTile(
                        leading=ft.CircleAvatar(src=u[0]['avatar_url']),
                        title=ft.Text(u[0]['first_name']),
                        on_click=open_chat
                    ))
            await page.update_async()

        # 5. ЧАТ
        elif page.route == "/chat":
            state["is_chatting"] = True
            msg_list = ft.ListView(expand=True, spacing=10)
            field = ft.TextField(hint_text="Сообщение...", expand=True)
            
            async def send_msg(e):
                if not field.value: return
                await api_post("messages", {
                    "sender_email": state["user"]["email"],
                    "receiver_email": state["partner"]["email"],
                    "text": field.value
                })
                field.value = ""
                await page.update_async()

            page.views.append(ft.View("/chat", [
                ft.AppBar(title=ft.Text(state["partner"]["first_name"])),
                msg_list,
                ft.Row([field, ft.IconButton(ft.Icons.SEND, on_click=send_msg)])
            ]))
            asyncio.create_task(chat_loop(msg_list))

        await page.update_async()

    page.on_route_change = route_change
    await page.push_route_async("/")

# Запуск
if __name__ == "__main__":
    ft.app(target=main, view=ft.AppView.WEB_BROWSER)
