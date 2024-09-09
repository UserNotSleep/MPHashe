import flet as ft
from yandex_music import Client
import requests
import io
import threading
import time
from pydub import AudioSegment
import simpleaudio as sa
import os
import json

AudioSegment.converter = os.path.join(os.path.dirname(__file__), "ffmpeg.exe")
AudioSegment.ffmpeg = os.path.join(os.path.dirname(__file__), "ffmpeg.exe")
AudioSegment.ffprobe = os.path.join(os.path.dirname(__file__), "ffprobe.exe")

CHART_ID = 'world'
CONFIG_FILE = 'config.json'

class MPHash:
    def __init__(self, page: ft.Page):
        self.page = page
        self.load_config()
        self.client = None
        self.initialize_client()
        self.chart = None
        self.current_track_index = 0
        self.is_playing = False
        self.volume = 0.5
        self.current_position = 0
        self.is_loading = False
        self.audio_data = None
        self.audio_segment = None
        self.play_obj = None
        self.current_loading_index = None
        self.setup_ui()
        self.load_chart()

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                self.config = json.load(f)
        else:
            self.config = {"token": ""}

    def save_config(self):
        with open(CONFIG_FILE, 'w') as f:
            json.dump(self.config, f)

    def initialize_client(self):
        if self.config["token"]:
            try:
                self.client = Client(self.config["token"]).init()
            except Exception as e:
                print(f"Error initializing client: {str(e)}")
                self.client = None

    def load_chart(self):
        if self.client:
            try:
                self.chart = self.client.chart(CHART_ID).chart
                self.load_current_track()
            except Exception as e:
                print(f"Error loading chart: {str(e)}")
                self.update_track_info("Error: Unable to load chart")

    def load_current_track(self):
        if not self.chart:
            self.update_track_info("Error: Chart not loaded")
            return

        self.stop_playback()
        self.is_loading = True
        self.play_button.disabled = True
        self.previous_button.disabled = True
        self.next_button.disabled = True
        self.audio_data = None
        self.audio_segment = None
        self.page.update()

        try:
            track_short = self.chart.tracks[self.current_track_index]
            self.track = track_short.track
            
            artists = ' - ' + ', '.join(artist.name for artist in self.track.artists) if self.track.artists else ''
            self.track_text = f'{self.track.title}{artists}'
            
            self.update_track_info(f"Загрузка: {self.track_text}")
            self.current_loading_index = self.current_track_index
            threading.Thread(target=self.preload_track).start()
            
        except Exception as e:
            self.update_track_info(f"Error: нельзя загрузить {self.track_text}")
            self.is_loading = False
            self.play_button.disabled = True
            self.page.update()

    def update_track_info(self, message):
        self.track_info.value = message
        self.page.update()

    def preload_track(self, retries=3):
        for attempt in range(retries):
            try:
                info = self.track.get_download_info()[0]
                stream_url = info.get_direct_link()
                response = requests.get(stream_url)
                if response.status_code == 200 and self.current_loading_index == self.current_track_index:
                    self.audio_data = response.content
                    if self.verify_audio_data():
                        self.update_track_info(f"Готово к воспроизведению: {self.track_text}")
                        self.play_button.disabled = False
                        self.previous_button.disabled = False
                        self.next_button.disabled = False
                        self.is_loading = False
                        self.page.update()
                        return
                    else:
                        self.update_track_info(f"Error: Invalid audio data (Attempt {attempt + 1}/{retries})")
                        self.audio_data = None
                        time.sleep(1)
                else:
                    self.update_track_info(f"Error: Unable to stream the track (Attempt {attempt + 1}/{retries})")
                    time.sleep(1)
            except Exception as e:
                self.update_track_info(f"Error: {str(e)} (Attempt {attempt + 1}/{retries})")
                time.sleep(1)

        self.update_track_info("Error: Failed to load track after multiple attempts")
        self.play_button.disabled = True
        self.is_loading = False
        self.page.update()

    def verify_audio_data(self):
        if not self.audio_data:
            return False
        try:
            self.audio_segment = AudioSegment.from_file(io.BytesIO(self.audio_data), format="mp3")
            return True
        except Exception as e:
            print(f"Error verifying audio data: {str(e)}")
            return False

    def play_pressed(self, e):
        if self.is_loading or not self.audio_data:
            return
        
        if self.is_playing:
            self.pause_track()
        else:
            self.play_track()
        self.page.update()

    def pause_track(self):
        if self.play_obj:
            self.play_obj.stop()
        self.play_button.icon = ft.icons.PLAY_ARROW
        self.is_playing = False

    def play_track(self, from_current_position=False):
        if self.is_loading or not self.audio_segment:
            return

        try:
            if from_current_position:
                current_position = self.current_position
            else:
                current_position = 0

            audio_segment = self.audio_segment[current_position:]
            audio_segment = audio_segment.apply_gain(self.volume * 30 - 15)  # Adjust volume range

            if self.play_obj and self.play_obj.is_playing():
                self.play_obj.stop()

            self.play_obj = sa.play_buffer(
                audio_segment.raw_data,
                num_channels=audio_segment.channels,
                bytes_per_sample=audio_segment.sample_width,
                sample_rate=audio_segment.frame_rate
            )
            self.is_playing = True
            self.play_button.icon = ft.icons.PAUSE
            self.update_track_info(f"Сейчас играет: {self.track_text}")

            threading.Thread(target=self.update_position, daemon=True).start()

        except Exception as e:
            self.update_track_info(f"Error playing track: {str(e)}")
            self.audio_data = None
            self.play_button.disabled = True
            self.reload_track()

    def update_position(self):
        while self.is_playing and self.play_obj and self.play_obj.is_playing():
            time.sleep(0.1)
            self.current_position += 100
        if self.is_playing:
            self.current_position = 0
            self.play_button.icon = ft.icons.PLAY_ARROW
            self.is_playing = False
            self.page.update()

    def stop_playback(self):
        if self.is_playing and self.play_obj:
            self.play_obj.stop()
        self.is_playing = False
        self.play_button.icon = ft.icons.PLAY_ARROW
        self.current_position = 0
        self.page.update()

    def next_track(self, e):
        if self.is_loading:
            return
        self.current_track_index = (self.current_track_index + 1) % len(self.chart.tracks)
        self.load_current_track()

    def previous_track(self, e):
        if self.is_loading:
            return
        self.current_track_index = (self.current_track_index - 1) % len(self.chart.tracks)
        self.load_current_track()

    def change_volume(self, e):
        self.volume = e.control.value
        self.apply_volume()

    def apply_volume(self):
        if self.is_playing:
            current_position = self.current_position
            self.play_obj.stop()
            self.play_track(from_current_position=True)

    def reload_track(self):
        self.update_track_info(f"Reloading track: {self.track_text}")
        self.is_loading = True
        self.play_button.disabled = True
        self.previous_button.disabled = True
        self.next_button.disabled = True
        self.page.update()
        threading.Thread(target=self.preload_track).start()

    def setup_ui(self):
        self.page.title = "MPHash"
        self.page.bgcolor = "#121212"
        self.page.window_width = 400
        self.page.window_height = 700
        self.page.window_resizable = False

        self.track_info = ft.Text(
            value="",
            text_align=ft.TextAlign.CENTER,
            size=16,
            color="#FFFFFF",
            weight=ft.FontWeight.W_500,
        )

        self.play_button = ft.IconButton(
            icon=ft.icons.PLAY_ARROW,
            icon_color="#1DB954",
            icon_size=48,
            on_click=self.play_pressed,
            disabled=True
        )

        self.previous_button = ft.IconButton(
            icon=ft.icons.SKIP_PREVIOUS,
            icon_color="#FFFFFF",
            icon_size=32,
            on_click=self.previous_track,
            disabled=True
        )

        self.next_button = ft.IconButton(
            icon=ft.icons.SKIP_NEXT,
            icon_color="#FFFFFF",
            icon_size=32,
            on_click=self.next_track,
            disabled=True
        )

        self.volume_slider = ft.Slider(
            min=0,
            max=1,
            value=self.volume,
            thumb_color="#1DB954",
            active_color="#1DB954",
            inactive_color="#535353",
            on_change=self.change_volume
        )

        self.album_art = ft.Stack(
            [
                ft.Container(
                    width=300,
                    height=300,
                    border_radius=10,
                    bgcolor="#282828",
                ),
                ft.Container(
                    content=ft.Text("MPHash", color="#FFFFFF", size=48, text_align=ft.TextAlign.CENTER),
                    alignment=ft.alignment.center,
                    width=300,
                    height=300,
                )
            ]
        )

        self.playButton = ft.Container( 
            content=ft.Column(
                [
                    ft.Row(
                        [self.previous_button, self.play_button, self.next_button],
                        alignment=ft.MainAxisAlignment.CENTER,
                    ),
                    ft.Row(
                        [
                            ft.Icon(name=ft.icons.VOLUME_DOWN, color="#FFFFFF", size=20),
                            self.volume_slider,
                            ft.Icon(name=ft.icons.VOLUME_UP, color="#FFFFFF", size=20),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                    ),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=20,
            ),
            padding=20,
        )

        self.content_container = ft.Container(
            content=ft.Column(
                [
                    self.album_art,
                    self.track_info,
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=20,
            ),
            alignment=ft.alignment.center,
            expand=True
        )

        self.app_bar = ft.Row(
            [
                ft.IconButton(icon=ft.icons.BAR_CHART, icon_color="#FFFFFF", on_click=self.on_charts_click),
                ft.IconButton(icon=ft.icons.FAVORITE, icon_color="#FFFFFF", on_click=self.on_favorites_click),
                ft.IconButton(icon=ft.icons.SETTINGS, icon_color="#FFFFFF", on_click=self.on_settings_click),
                ft.IconButton(icon=ft.icons.LOGOUT, icon_color="#FFFFFF", on_click=self.on_logout_click),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
        )

        self.page.add(
            self.app_bar,
            ft.Container(
                content=ft.Column(
                    [
                        self.content_container,
                        self.playButton,
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    expand=True
                ),
                padding=20,
                expand=True
            )
        )

    def on_charts_click(self, e):
        self.content_container.content = ft.Column(
            [
                self.album_art,
                self.track_info,
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=20,
        )
        self.update_track_info(f"Сейчас играет: {self.track_text}" if self.is_playing else f"Готово к воспроизведению: {self.track_text}")
        self.play_button.disabled = self.is_loading or not self.audio_data
        self.page.update()

    def on_favorites_click(self, e):
        self.content_container.content = ft.Text(
            "Здесь будет список избранных треков",
            size=16,
            color="#FFFFFF",
            text_align=ft.TextAlign.CENTER
        )
        self.page.update()

    def on_settings_click(self, e):
        self.token_input = ft.TextField(
            label="Токен Яндекс Музыки",
            value=self.config["token"],
            password=True,
            can_reveal_password=True
        )
        self.save_button = ft.ElevatedButton("Сохранить", on_click=self.save_token)
        
        self.content_container.content = ft.Column(
            [
                ft.Text("Настройки", size=24, color="#FFFFFF", text_align=ft.TextAlign.CENTER),
                self.token_input,
                self.save_button
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=20,
        )
        self.page.update()

    def save_token(self, e):
        new_token = self.token_input.value
        if new_token != self.config["token"]:
            self.config["token"] = new_token
            self.save_config()
            self.initialize_client()
            self.load_chart()
        self.page.show_snack_bar(ft.SnackBar(content=ft.Text("Токен сохранен")))

    def on_logout_click(self, e):
        self.config["token"] = ""
        self.save_config()
        self.client = None
        self.chart = None
        self.stop_playback()
        self.update_track_info("Выполнен выход из аккаунта")
        self.page.update()

def main(page: ft.Page):
    MPHash(page)

if __name__ == "__main__":
    ft.app(target=main)