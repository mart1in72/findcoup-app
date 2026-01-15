import flet as ft
import random
import time
import httpx 
from postgrest import SyncPostgrestClient

# Данные Supabase
URL = "https://kgxvjlsojgkkhdaftncg.supabase.co"
KEY = "sb_publishable_2jhUvmgAKa-edfQyKSWlbA_nKxG65O0"

# Клиент с выключенным HTTP/2
custom_session = httpx.Client(http2=False)
supabase = SyncPostgrestClient(
    f"{URL}/rest/v1", 
    headers={"apikey": KEY, "Authorization": f"Bearer {KEY}"},
    http_client=custom_session
)

def main(page: ft.Page):
    # Даем браузеру 0.5 сек на подготовку
    time.sleep(0.5)
    
    page.title = "FindCoup"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = ft.Colors.BLACK
    page.padding = 0

    user_state = {"email": "", "username": "", "avatar_url": ""}

    def route_change(e):
        page.views.clear()
        
        # ЭКРАН ВХОДА (ЛОГИН)
        if page.route == "/" or page.route == "":
            un = ft.TextField(label="Никнейм (@)", width=300)
            ps = ft.TextField(label="Пароль", password=True, width=300)

            def login_click(_):
                # Упрощенная логика для теста: входим сразу
                user_state["username"] = un.value
                page.go("/feed")

            page.views.append(
                ft.View(
                    "/",
                    [
                        ft.Container(height=100),
                        ft.Icon(ft.Icons.FAVORITE, color="red", size=80),
                        ft.Text("FindCoup", size=30, weight="bold"),
                        ft.Container(height=20),
                        un, 
                        ps,
                        ft.ElevatedButton("ВОЙТИ", width=300, on_click=login_click),
                    ],
                    horizontal_alignment="center",
                )
            )
        
        # ЭКРАН ЛЕНТЫ
        elif page.route == "/feed":
            page.views.append(
                ft.View(
                    "/feed",
                    [
                        ft.AppBar(title=ft.Text("Лента"), bgcolor=ft.Colors.SURFACE_VARIANT),
                        ft.Container(
                            content=ft.Column([
                                ft.Icon(ft.Icons.PERSON, size=100),
                                ft.Text("Добро пожаловать!", size=20)
                            ], horizontal_alignment="center"),
                            expand=True,
                            alignment=ft.alignment.center
                        ),
                        ft.ElevatedButton("Назад", on_click=lambda _: page.go("/"))
                    ]
                )
            )
        page.update()

    # Привязываем события
    page.on_route_change = route_change
    
    # ПРИНУДИТЕЛЬНЫЙ запуск первого экрана
    page.go("/")

# Запуск приложения
if __name__ == "__main__":
    ft.app(target=main)
