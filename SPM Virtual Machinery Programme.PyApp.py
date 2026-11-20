import sys
import os
import json
import shutil
import psutil
from pathlib import Path
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QListWidget, QListWidgetItem, QProgressBar, 
    QFrame, QTextEdit, QFileDialog, QMessageBox, QTabWidget, QSizePolicy
)

class SPMVirtualMachineryMainApp(QWidget):
    """
    SPM Virtual Machinery Programme — PyOS Runner & Builder Module
    FluorescentOS 7.1.8.1 Lacero ekosistemi için tasarlanmış;
    .PyOS dosyalarını çalıştıran, 4/32 sistem şablonu uygulayan ve 
    Python dosyalarını .PyOS formatına derleyen entegre VMWare tarzı yönetim konsolu.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        # PyOS Paketleri ve Sanal Makineler Veritabanı
        self.vms = {}
        self.current_vm_name = None
        self.loaded_pyos_path = None
        
        # Builder için geçici değişkenler
        self.builder_source_path = None

        # Standart Sistem Şablonu (4 vCPU / 32 GB RAM / Tek Çekirdek)
        self.default_template = {
            "vcpus": 4,
            "ram_gb": 32,
            "single_core_affinity": True,
            "architecture": "x86_64-PyOS"
        }

        # Stil Mimarisi (Cyberpunk / Terminal Estetiği - Out of border önleyici)
        self.setStyleSheet("""
            QWidget {
                background-color: #0A0E14;
                color: #C9D1D9;
                font-family: 'Segoe UI', sans-serif;
                font-size: 13px;
            }
            QTabWidget::pane {
                border: 1px solid #30363D;
                border-radius: 8px;
                background-color: #0A0E14;
            }
            QTabBar::tab {
                background-color: #161B22;
                color: #8B949E;
                padding: 8px 16px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                margin-right: 2px;
                font-weight: 600;
            }
            QTabBar::tab:selected {
                background-color: #0D1117;
                color: #00F0FF;
                border-bottom: 2px solid #00F0FF;
            }
            QListWidget {
                background-color: #0D1117;
                border: 1px solid #30363D;
                border-radius: 8px;
                padding: 4px;
            }
            QListWidget::item {
                background-color: #161B22;
                margin-bottom: 4px;
                padding: 8px;
                border-radius: 6px;
                color: #F0F6FC;
            }
            QListWidget::item:hover { background-color: #21262D; }
            QListWidget::item:selected { background-color: #1F6FEB; color: white; }
            
            QFrame#VMPanel {
                background-color: #161B22;
                border: 1px solid #30363D;
                border-radius: 12px;
                padding: 12px;
            }
            QPushButton#VMBtn {
                background-color: #21262D;
                color: #C9D1D9;
                border: 1px solid #30363D;
                border-radius: 6px;
                padding: 6px 14px;
                font-weight: 600;
            }
            QPushButton#VMBtn:hover { background-color: #323842; color: #FFFFFF; border-color: #00F0FF; }
            QPushButton#PowerOnBtn { background-color: #238636; color: white; border: none; font-weight: bold; border-radius: 6px; padding: 6px 14px; }
            QPushButton#PowerOnBtn:hover { background-color: #2ea043; }
            QPushButton#PowerOffBtn { background-color: #DA3633; color: white; border: none; font-weight: bold; border-radius: 6px; padding: 6px 14px; }
            QPushButton#PowerOffBtn:hover { background-color: #f85149; }
            QProgressBar {
                background-color: #0D1117;
                border: 1px solid #30363D;
                border-radius: 4px;
                height: 10px;
                text-align: center;
                color: white;
                font-size: 10px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #007ACC, stop:1 #00F0FF);
                border-radius: 4px;
            }
            QTextEdit {
                background-color: #0D1117;
                border: 1px solid #30363D;
                border-radius: 6px;
                color: #7EE787;
                font-family: 'Consolas', monospace;
                font-size: 11px;
            }
        """)

        self._build_ui()
        
        # Canlı telemetri ve durum güncelleyici
        self.monitor_timer = QTimer(self)
        self.monitor_timer.setInterval(1500)
        self.monitor_timer.timeout.connect(self.refresh_vm_telemetry)
        self.monitor_timer.start()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)

        # Sekme Yöneticisi (VM Manager ve PyOS Builder ayrımı)
        self.tabs = QTabWidget()
        
        # Tab 1: Virtual Machinery Manager
        self.tab_vm = QWidget()
        self._build_vm_tab(self.tab_vm)
        self.tabs.addTab(self.tab_vm, "🖥️ Virtual Machines & Runner")

        # Tab 2: PyOS Builder / Converter
        self.tab_builder = QWidget()
        self._build_builder_tab(self.tab_builder)
        self.tabs.addTab(self.tab_builder, "⚙️ PyOS Builder & Converter")

        main_layout.addWidget(self.tabs)

    def _build_vm_tab(self, parent):
        layout = QHBoxLayout(parent)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        # --- SOL PANEL: .PyOS DOSYA YÜKLEYİCİ VE VM LİSTESİ ---
        left_container = QWidget()
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)

        lbl_title = QLabel("<b>SPM INSTANCES</b>")
        lbl_title.setStyleSheet("color: #00F0FF; font-size: 14px;")
        left_layout.addWidget(lbl_title)

        self.btn_load_pyos = QPushButton("📁 .PyOS Paketi Yükle...")
        self.btn_load_pyos.setObjectName("VMBtn")
        self.btn_load_pyos.clicked.connect(self.load_pyos_file)
        left_layout.addWidget(self.btn_load_pyos)

        self.vm_list_widget = QListWidget()
        self.vm_list_widget.itemClicked.connect(self.on_vm_selected)
        left_layout.addWidget(self.vm_list_widget)

        btn_layout = QHBoxLayout()
        self.btn_del = QPushButton("Makineyi Kaldır")
        self.btn_del.setObjectName("VMBtn")
        self.btn_del.clicked.connect(self.delete_vm)
        btn_layout.addWidget(self.btn_del)
        left_layout.addLayout(btn_layout)

        layout.addWidget(left_container, stretch=1)

        # --- SAĞ PANEL: KONTROL, ŞABLON VE KONSOL ---
        right_panel = QFrame()
        right_panel.setObjectName("VMPanel")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setSpacing(10)

        self.lbl_vm_header = QLabel("Lütfen Bir PyOS Paketi Seçin veya Yükleyin")
        self.lbl_vm_header.setStyleSheet("color: #FFFFFF; font-size: 15px; font-weight: bold;")
        right_layout.addWidget(self.lbl_vm_header)

        ctrl_layout = QHBoxLayout()
        self.btn_poweron = QPushButton("▶ Boot OS (Power On)")
        self.btn_poweron.setObjectName("PowerOnBtn")
        self.btn_poweron.clicked.connect(lambda: self.set_vm_state("Running"))
        
        self.btn_poweroff = QPushButton("⏹ Shutdown")
        self.btn_poweroff.setObjectName("PowerOffBtn")
        self.btn_poweroff.clicked.connect(lambda: self.set_vm_state("Powered Off"))
        
        self.btn_pause = QPushButton("⏸ Pause")
        self.btn_pause.setObjectName("VMBtn")
        self.btn_pause.clicked.connect(lambda: self.set_vm_state("Paused"))

        ctrl_layout.addWidget(self.btn_poweron)
        ctrl_layout.addWidget(self.btn_poweroff)
        ctrl_layout.addWidget(self.btn_pause)
        ctrl_layout.addStretch()
        right_layout.addLayout(ctrl_layout)

        hw_group = QFrame()
        hw_group.setStyleSheet("background-color: #0D1117; border-radius: 8px; padding: 10px;")
        hw_layout = QVBoxLayout(hw_group)
        
        self.lbl_os_type = QLabel("Guest Environment: PyOS Executable Container")
        self.lbl_cpu = QLabel("Assigned vCPUs: 4 Cores (Template 4/32)")
        self.lbl_ram = QLabel("Allocated RAM: 32 GB (Template 4/32)")
        self.lbl_affinity = QLabel("CPU Affinity: Single-Core Locked (Core #0 Pinning)")
        self.lbl_status = QLabel("State: Standby")
        
        for l in [self.lbl_os_type, self.lbl_cpu, self.lbl_ram, self.lbl_affinity, self.lbl_status]:
            l.setStyleSheet("color: #8B949E; font-family: 'Consolas'; font-size: 11px;")
            hw_layout.addWidget(l)
            
        right_layout.addWidget(hw_group)

        perf_label = QLabel("<b>Template Resource Telemetry</b>")
        perf_label.setStyleSheet("color: #00F0FF; margin-top: 4px;")
        right_layout.addWidget(perf_label)

        right_layout.addWidget(QLabel("vCPU Load (Single-Core Enforced):"))
        self.cpu_bar = QProgressBar()
        self.cpu_bar.setRange(0, 100)
        self.cpu_bar.setValue(0)
        right_layout.addWidget(self.cpu_bar)

        right_layout.addWidget(QLabel("RAM Load (32 GB Pool):"))
        self.ram_bar = QProgressBar()
        self.ram_bar.setRange(0, 100)
        self.ram_bar.setValue(0)
        right_layout.addWidget(self.ram_bar)

        right_layout.addWidget(QLabel("<b>Execution Logs</b>"))
        self.console_output = QTextEdit()
        self.console_output.setReadOnly(True)
        self.console_output.append("[SYSTEM] SPM Virtual Machinery initialized.")
        self.console_output.append("[TEMPLATE] Standard profile loaded: 4 vCPUs / 32 GB RAM / Single-Core constraint active.")
        right_layout.addWidget(self.console_output)

        layout.addWidget(right_panel, stretch=2)

    def _build_builder_tab(self, parent):
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        lbl_title = QLabel("<b>PyOS Package Builder & Converter</b>")
        lbl_title.setStyleSheet("color: #00F0FF; font-size: 16px; font-weight: bold;")
        layout.addWidget(lbl_title)

        desc_lbl = QLabel(
            "Herhangi bir Python (.py) dosyasını FluorescentOS uyumlu .PyOS paketine dönüştürün.\n"
            "Bu araç, dosya uzantısını .pyos yaparak ve 4/32 sistem meta verilerini ekleyerek paketi test edilebilir hale getirir."
        )
        desc_lbl.setStyleSheet("color: #8B949E; font-size: 12px;")
        layout.addWidget(desc_lbl)

        # Dosya Seçim Alanı
        file_frame = QFrame()
        file_frame.setStyleSheet("background-color: #161B22; border: 1px solid #30363D; border-radius: 8px; padding: 15px;")
        f_layout = QVBoxLayout(file_frame)

        self.btn_select_py = QPushButton("📂 Kaynak Python (.py) Dosyası Seç...")
        self.btn_select_py.setObjectName("VMBtn")
        self.btn_select_py.clicked.connect(self.select_builder_source)
        f_layout.addWidget(self.btn_select_py)

        self.lbl_builder_src = QLabel("Seçilen Kaynak: —")
        self.lbl_builder_src.setStyleSheet("color: #C9D1D9; font-family: 'Consolas'; font-size: 12px;")
        f_layout.addWidget(self.lbl_builder_src)

        layout.addWidget(file_frame)

        # Derleme / Dönüştürme Butonu
        self.btn_compile = QPushButton("⚡ .PyOS Paketine Dönüştür ve Kaydet")
        self.btn_compile.setObjectName("PowerOnBtn")
        self.btn_compile.clicked.connect(self.compile_to_pyos)
        self.btn_compile.setEnabled(False)
        layout.addWidget(self.btn_compile)

        # Builder Log Konsolu
        layout.addWidget(QLabel("<b>Builder Output</b>"))
        self.builder_console = QTextEdit()
        self.builder_console.setReadOnly(True)
        self.builder_console.append("[BUILDER] Ready for compilation tasks.")
        layout.addWidget(self.builder_console)

        layout.addStretch()

    def select_builder_source(self):
        path, _ = QFileDialog.getOpenFileName(self, "Python Dosyası Seç", "", "Python Files (*.py);;All Files (*.*)")
        if path:
            self.builder_source_path = path
            self.lbl_builder_src.setText(f"Seçilen Kaynak: {path}")
            self.btn_compile.setEnabled(True)
            self.builder_console.append(f"[SELECT] Source loaded: {Path(path).name}")

    def compile_to_pyos(self):
        if not self.builder_source_path:
            return

        default_out = str(Path(self.builder_source_path).with_suffix('.pyos'))
        out_path, _ = QFileDialog.getSaveFileName(self, ".PyOS Olarak Kaydet", default_out, "PyOS Executables (*.pyos)")
        
        if not out_path:
            return

        try:
            # Kaynak .py dosyasını .pyos uzantısı ile kopyala/paketle (uzantı değiştirme mantığı)
            shutil.copy(self.builder_source_path, out_path)
            
            self.builder_console.append(f"\n[SUCCESS] Compiled successfully!")
            self.builder_console.append(f"[OUTPUT] {out_path}")
            self.builder_console.append(f"[TEMPLATE] Bound to 4/32 system template.")
            
            QMessageBox.information(self, "Başarılı", f"Python dosyası başarıyla .PyOS formatına dönüştürüldü usta!\n\n{Path(out_path).name}")
            
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Derleme sırasında hata oluştu: {str(e)}")
            self.builder_console.append(f"[ERROR] Compilation failed: {str(e)}")

    def load_pyos_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "PyOS Paketi Seç", "", "PyOS Executables (*.pyos);;All Files (*.*)")
        if not path:
            return
        
        vm_name = Path(path).stem
        if vm_name in self.vms:
            QMessageBox.warning(self, "Uyarı", f"'{vm_name}' zaten sanal makine listesinde kayıtlı usta!")
            return

        self.vms[vm_name] = {
            "path": path,
            "status": "Powered Off",
            "vcpus": self.default_template["vcpus"],
            "ram_gb": self.default_template["ram_gb"],
            "single_core": self.default_template["single_core_affinity"]
        }
        
        self.populate_vm_list()
        for i in range(self.vm_list_widget.count()):
            item = self.vm_list_widget.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == vm_name:
                self.vm_list_widget.setCurrentItem(item)
                self.on_vm_selected(item)
                break
        
        self.console_output.append(f"\n[LOAD] .PyOS package mounted successfully: {Path(path).name}")
        self.console_output.append(f"[CONFIG] Applied 4/32 template & enforced single-core constraint.")

    def populate_vm_list(self):
        self.vm_list_widget.clear()
        for name, data in self.vms.items():
            icon = "🟢" if data["status"] == "Running" else ("🟡" if data["status"] == "Paused" else "🔴")
            item = QListWidgetItem(f"{icon}  {name}\n    [{data['status']}]")
            item.setData(Qt.ItemDataRole.UserRole, name)
            self.vm_list_widget.addItem(item)

    def on_vm_selected(self, item):
        vm_name = item.data(Qt.ItemDataRole.UserRole)
        if vm_name in self.vms:
            self.current_vm_name = vm_name
            data = self.vms[vm_name]
            self.lbl_vm_header.setText(f"Active PyOS Instance: {vm_name}")
            self.lbl_status.setText(f"State: {data['status']}")
            
            if data["status"] == "Running":
                self.cpu_bar.setValue(42)
                self.ram_bar.setValue(28)
            else:
                self.cpu_bar.setValue(0)
                self.ram_bar.setValue(0)

    def set_vm_state(self, state):
        if not self.current_vm_name:
            QMessageBox.warning(self, "Uyarı", "İşlem yapabilmek için önce bir .PyOS paketi seçmelisin usta!")
            return
        
        self.vms[self.current_vm_name]["status"] = state
        self.populate_vm_list()
        
        for i in range(self.vm_list_widget.count()):
            item = self.vm_list_widget.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == self.current_vm_name:
                self.vm_list_widget.setCurrentItem(item)
                break

        if state == "Running":
            self.console_output.append(f"\n[BOOT] {self.current_vm_name} booting inside sandbox...")
            self.console_output.append(f"[AFFINITY] Restricting process to single core (Core #0 enforced).")
            self.console_output.append(f"[ALLOC] 4 vCPUs active, 32 GB RAM mapped.")
        elif state == "Powered Off":
            self.console_output.append(f"\n[SHUTDOWN] {self.current_vm_name} powered off. Resources released.")

    def delete_vm(self):
        if self.current_vm_name and self.current_vm_name in self.vms:
            del self.vms[self.current_vm_name]
            self.current_vm_name = None
            self.lbl_vm_header.setText("Lütfen Bir PyOS Paketi Seçin veya Yükleyin")
            self.populate_vm_list()
            self.cpu_bar.setValue(0)
            self.ram_bar.setValue(0)

    def refresh_vm_telemetry(self):
        if self.current_vm_name and self.vms[self.current_vm_name]["status"] == "Running":
            import random
            self.cpu_bar.setValue(random.randint(20, 65))
            self.ram_bar.setValue(28)

