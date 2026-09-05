import sys
import requests
import vlc
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QLabel, QListWidget
from PyQt6.QtCore import Qt

class SimpleStreamApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Basit IPTV Oynatıcı")
        self.resize(800, 600)

        layout = QVBoxLayout(self)

        # Kanal Listesi
        self.channel_list = QListWidget()
        self.channels = {
            "TRT 1": "https://tv-trt1.medya.trt.com.tr/master_720.m3u8",
            "ATV": "https://trkvz-live.daioncdn.net/atv/atv.m3u8"
        }
        for name in self.channels:
            self.channel_list.addItem(name)
        layout.addWidget(self.channel_list)

        # Video Görüntü Alanı
        self.video_frame = QWidget()
        self.video_frame.setStyleSheet("background-color: black;")
        layout.addWidget(self.video_frame)

        # Oynat Butonu
        self.play_btn = QPushButton("▶ Oynat")
        self.play_btn.clicked.connect(self.play_stream)
        layout.addWidget(self.play_btn)

        # VLC Tanımlamaları
        self.vlc_instance = vlc.Instance(['--no-xlib', '--quiet'])
        self.media_player = self.vlc_instance.media_player_new()

    def play_stream(self):
        selected_item = self.channel_list.currentItem()
        if not selected_item:
            return
        
        url = self.channels[selected_item.text()]
        media = self.vlc_instance.media_new(url)
        self.media_player.set_media(media)

        # Pencereyi VLC'ye bağla
        if sys.platform.startswith('win'):
            self.media_player.set_hwnd(int(self.video_frame.winId()))
        elif sys.platform.startswith('darwin'):
            self.media_player.set_nsobject(int(self.video_frame.winId()))
        else:
            self.media_player.set_xwindow(int(self.video_frame.winId()))

        self.media_player.play()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SimpleStreamApp()
    window.show()
    sys.exit(app.exec())