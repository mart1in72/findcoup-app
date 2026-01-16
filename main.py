import flet as ft
import time
import httpx

# Константы вынесены отдельно
URL = "https://kgxvjlsojgkkhdaftncg.supabase.co"
KEY = "sb_publishable_2jhUvmgAKa-edfQyKSWlbA_nKxG65O0"

def main(page: ft.Page):
    # 1. Настройки страницы (срабатывают мгновенно)
    page.title = "FindCoup v1.0"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = "#000000"
    page.vertical_alignment = ft.MainAxisAlignment.CENTER
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER

    # 2. Переменные для хранения данных
    user_data = {"name": "", "logged_in": False}

    # 3. Функция для переключения экранов (простая смена контента)
    def show_screen(screen_type):
        page.controls.clear()
        
        if screen_type == "login":
            # ЭКРАН ЛОГИНА
            login_input = ft.TextField(label="Никнейм", width=280, border_radius=10)
            pass_input = ft.TextField(label="Пароль", password=True, can_reveal_password=True, width=280, border_radius=10)
            
            def on_login_click(e):
                if login_input.value:
                    user_data["name"] = login_input.value
                    show_screen("feed")
                else:
                    page.snack_bar = ft.SnackBar(ft.Text("Введите никнейм"))
                    page.snack_bar.open = True
                    page.update()

            page.add(
                ft.Icon(ft.Icons.FAVORITE, color="red", size=60),
                ft.Text("FindCoup", size=30, weight="bold"),
                ft.Text("Вход в систему", color="grey"),
                ft.Container(height=20),
                login_input,
                pass_input,
                ft.Container(height=10),
                ft.ElevatedButton(
                    "ВОЙТИ", 
                    width=280, 
                    bgcolor="red", 
                    color="white", 
                    on_click=on_login_click
                ),
                ft.TextButton("Регистрация", on_click=lambda _: show_screen("reg"))
            )
            
        elif screen_type == "feed":
            # ЭКРАН ЛЕНТЫ
            page.add(
                ft.AppBar(title=ft.Text(f"Привет, {user_data['name']}!"), bgcolor="#1a1a1a"),
                ft.Container(
                    content=ft.Column([
                        ft.Container(
                            width=300, height=400, bgcolor="#222222", border_radius=20,
                            content=ft.Icon(ft.Icons.PERSON, size=100, color="grey")
                        ),
                        ft.Text("Поиск анкет...", size=20),
                        ft.Row([
                            ft.IconButton(ft.Icons.CLOSE, icon_size=40, on_click=lambda _: show_screen("feed")),
                            ft.IconButton(ft.Icons.FAVORITE, icon_size=40, icon_color="red", on_click=lambda _: show_screen("feed")),
                        ], alignment="center")
                    ], horizontal_alignment="center"),
                    expand=True, alignment=ft.alignment.center
                ),
                ft.TextButton("Выход", on_click=lambda _: show_screen("login"))
            )

        elif screen_type == "reg":
            # ЭКРАН РЕГИСТРАЦИИ
            page.add(
                ft.Text("Регистрация", size=25, weight="bold"),
                ft.TextField(label="Имя", width=280),
                ft.TextField(label="Никнейм (@)", width=280),
                ft.ElevatedButton("Создать", on_click=lambda _: show_screen("feed")),
                ft.TextButton("Назад", on_click=lambda _: show_screen("login"))
            )

        page.update()

    # Запуск первого экрана
    show_screen("login")

# Точка входа для веба
ft.app(main)
