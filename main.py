import flet as ft
from yandex_music import Client
import pygame
import os
import tempfile
import shutil

CHART_ID = 'world'
client = Client('').init()

class MPHash:
    def __init__(self, page: ft.Page):
        self.page = page
        self.chart = client.chart(CHART_ID).chart
        self.current_track_index = 0
        self.is_playing = False
        self.volume = 0.5
        self.temp_dir = tempfile.mkdtemp()
        self.current_position = 0
        pygame.mixer.init()
        pygame.mixer.music.set_volume(self.volume)
        self.setup_ui()
        self.load_current_track()

    def load_current_track(self):
        try:
            # Получаем информацию о текущем треке
            track_short = self.chart.tracks[self.current_track_index]
            self.track = track_short.track
            
            # Обновляем название трека и исполнителей
            artists = ' - ' + ', '.join(artist.name for artist in self.track.artists) if self.track.artists else ''
            self.track_text = f'{self.track.title}{artists}'
            
            # Скачиваем и сохраняем файл трека во временную директорию
            temp_file = os.path.join(self.temp_dir, f'track_{self.current_track_index}.mp3')
            self.track.download(temp_file)
            self.current_track_file = temp_file  # Сохраняем путь к текущему файлу
            
            # Обновляем информацию в интерфейсе
            self.update_track_info(f"Сейчас играет: {self.track_text}")
            
        except Exception as e:
            # Обрабатываем ошибки, если не удалось скачать трек
            self.current_track_file = None
            self.update_track_info(f"Error: нельзя скачать {self.track_text}")



    def update_track_info(self, message):
        self.track_info.value = message
        self.page.update()

    def play_pressed(self, e):
        if self.is_playing:
            self.pause_track()
        else:
            self.play_track()
        self.page.update()

    def pause_track(self):
        pygame.mixer.music.pause()
        self.current_position = pygame.mixer.music.get_pos() / 1000
        self.play_button.icon = ft.icons.PLAY_ARROW
        self.is_playing = False

    def play_track(self):
        if self.current_track_file and os.path.exists(self.current_track_file):
            try:
                if not pygame.mixer.music.get_busy():
                    # Загружаем файл текущего трека в pygame для воспроизведения
                    pygame.mixer.music.load(self.current_track_file)
                    pygame.mixer.music.play(start=self.current_position)
                else:
                    # Если трек уже играет, снимаем паузу
                    pygame.mixer.music.unpause()
                
                # Обновляем кнопку на "Пауза"
                self.play_button.icon = ft.icons.PAUSE
                self.is_playing = True
                
            except pygame.error as e:
                # Обрабатываем ошибки pygame
                self.update_track_info(f"Error: {str(e)}")
        else:
            self.update_track_info("Error: No track file available")


    def stop_playback(self):
        if self.is_playing:
            pygame.mixer.music.stop()
            self.is_playing = False
            self.play_button.icon = ft.icons.PLAY_ARROW
            self.current_position = 0
            self.page.update()

    def next_track(self, e):
        self.stop_playback()
        self.current_track_index = (self.current_track_index + 1) % len(self.chart.tracks)
        self.load_current_track()

    def previous_track(self, e):
        self.stop_playback()
        self.current_track_index = (self.current_track_index - 1) % len(self.chart.tracks)
        self.load_current_track()

    def change_volume(self, e):
        self.volume = e.control.value
        pygame.mixer.music.set_volume(self.volume)

    def setup_ui(self):
        self.page.title = "MPHash"
        self.page.bgcolor = "#f2f2f2"
        self.page.window.width = 600
        self.page.window.height = 400
        self.page.window.resizable = False

        self.track_info = ft.Text(
            value="",
            text_align=ft.TextAlign.CENTER,
            size=20,
            color=ft.colors.PURPLE,
            weight=ft.FontWeight.W_100,
        )

        self.play_button = ft.IconButton(
            icon=ft.icons.PLAY_ARROW,
            icon_color=ft.colors.PURPLE,
            on_click=self.play_pressed
        )

        self.volume_slider = ft.Slider(
            min=0,
            max=1,
            value=self.volume,
            thumb_color=ft.colors.PURPLE,
            secondary_active_color=ft.colors.PURPLE,
            active_color=ft.colors.PURPLE,
            on_change=self.change_volume
        )

        self.playButton = ft.Container( 
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.IconButton(icon=ft.icons.SKIP_PREVIOUS, icon_color=ft.colors.PURPLE, on_click=self.previous_track),
                            self.play_button,
                            ft.IconButton(icon=ft.icons.SKIP_NEXT, icon_color=ft.colors.PURPLE, on_click=self.next_track),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                    ),
                    ft.Row(
                        [
                            ft.Icon(name=ft.icons.VOLUME_DOWN, color=ft.colors.PURPLE),
                            self.volume_slider,
                            ft.Icon(name=ft.icons.VOLUME_UP, color=ft.colors.PURPLE),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                    ),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            height=100,
        )

        self.content_container = ft.Container(
            content=self.track_info,
            alignment=ft.alignment.center,
            expand=True
        )

        # Добавляем NavigationRail
        self.navigation_rail = ft.NavigationRail(
            selected_index=0,
            bgcolor=ft.colors.PURPLE,
            destinations=[
                ft.NavigationRailDestination(icon=ft.icons.MUSIC_NOTE, label="Чарты"),
                ft.NavigationRailDestination(icon=ft.icons.INFO, label="О программе")
            ],
            on_change=self.on_navigation_change,
            label_type=ft.NavigationRailLabelType.ALL,
        )

        self.page.add(
            ft.Row(
                [
                    self.navigation_rail,
                    ft.VerticalDivider(),
                    ft.Column(
                        [
                            self.content_container,
                            self.playButton,
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        expand=True
                    ),
                ],
                expand=True,
            )
        )

    def on_navigation_change(self, e):
        selected_index = e.control.selected_index
        if selected_index == 0:  # Чарты
            # Обновляем контейнер и выводим название текущего трека
            self.content_container.content = self.track_info
            self.update_track_info(f"Сейчас играет: {self.track_text}")  # Обновляем информацию о треке
        elif selected_index == 1:  # О программе
            self.content_container.content = ft.Text("MPHash - музыкальный плеер\nАвторы: Гарифуллин Ильзат и Галимов Ильназ", size=20, color=ft.colors.PURPLE)
        self.page.update()


    def __del__(self):
        if hasattr(self, 'temp_dir') and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

def main(page: ft.Page):
    MPHash(page)

if __name__ == "__main__":
    ft.app(target=main)
