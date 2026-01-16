import flet as ft
import httpx
import time
import random

# --- НАСТРОЙКИ (БЕЗ ИЗМЕНЕНИЙ) ---
URL = "https://kgxvjlsojgkkhdaftncg.supabase.co"
KEY = "sb_publishable_2jhUvmgAKa-edfQyKSWlbA_nKxG65O0"
HEADERS = {"apikey": KEY, "Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}

def main(page: ft.Page):
    page.title = "FindCoup Light"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = ft.Colors.BLACK
    page.window_width, page.window_height = 400, 800
    
    # Состояние приложения
    user_state = {"email": "", "username": "", "gender": "", "avatar_url": ""}

    def api_get(table, params=""):
        try:
            r = httpx.get(f"{URL}/rest/v1/{table}?{params}", headers=HEADERS)
            return r.json()
        except: return None

    def api_post(table, data):
        try:
            httpx.post(f"{URL}/rest/v1/{table}", headers=HEADERS, json=data)
            return True
        except: return False

    def route_change(route):
        page.views.clear()
        
        # --- СТРАНИЦА ВХОДА ---
        if page.route == "/":
            un = ft.TextField(label="Никнейм (@)", width=280)
            ps = ft.TextField(label="Пароль", password=True, width=280)

            def login(_):
                res = api_get("profiles", f"username=eq.{un.value}")
                if res and len(res) > 0 and str(res[0]['password']) == ps.value:
                    user_state.update(res[0])
                    page.go("/feed")
                else:
                    page.snack_bar = ft.SnackBar(ft.Text("Ошибка входа!"))
                    page.snack_bar.open = True
                    page.update()

            page.views.append(ft.View("/", [
                ft.Icon(ft.Icons.FAVORITE, color="red", size=80),
                ft.Text("FindCoup v5", size=30, weight="bold"),
                un, ps,
                ft.ElevatedButton("ВОЙТИ", on_click=login, bgcolor="red", color="white", width=280),
                ft.TextButton("Регистрация", on_click=lambda _: page.go("/reg"))
            ], horizontal_alignment="center", vertical_alignment="center"))

        # --- ЛЕНТА ---
        elif page.route == "/feed":
            card = ft.Column(horizontal_alignment="center")
            
            def load_next():
                target = "Девушка" if user_state["gender"] == "Парень" else "Парень"
                users = api_get("profiles", f"gender=eq.{target}&limit=10")
                if users:
                    u = random.choice(users)
                    card.controls = [
                        ft.Image(src=u.get("avatar_url"), width=300, height=400, fit="cover", border_radius=20),
                        ft.Text(f"{u['first_name']}, {u['username']}", size=20, weight="bold"),
                        ft.Row([
                            ft.IconButton(ft.Icons.CLOSE, on_click=lambda _: load_next(), icon_size=40),
                            ft.IconButton(ft.Icons.FAVORITE, on_click=lambda _: load_next(), icon_color="red", icon_size=40)
                        ], alignment="center")
                    ]
                    page.update()

            page.views.append(ft.View("/feed", [
                ft.Text("Лента анкет", size=20, color="red"),
                card,
                ft.BottomAppBar(content=ft.Row([
                    ft.IconButton(ft.Icons.EXPLORE, on_click=lambda _: page.go("/feed")),
                    ft.IconButton(ft.Icons.CHAT, on_click=lambda _: page.go("/chats")),
                    ft.IconButton(ft.Icons.PERSON, on_click=lambda _: page.go("/"))
                ], alignment="spaceAround"))
            ], horizontal_alignment="center"))
            load_next()

        page.update()

    # Настройка навигации
    page.on_route_change = route_change
    page.go("/")

if __name__ == "__main__":
    # Запуск в режиме веб-сервера
    ft.app(target=main, view=ft.AppView.WEB_BROWSER)
