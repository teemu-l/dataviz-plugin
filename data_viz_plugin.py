from yapsy.IPlugin import IPlugin
from core.api import Api
from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QStatusBar,
    QMenu,
    QAction,
)
from plugins.hexview_widget import HexViewWidget
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QCursor
import random


COLORS = [
    0xFDFEFE,
    0xECF0F1,
    0xB3B6B7,
    0x7B7D7D,
    0xEAECEE,
    0xABB2B9,
    0x566573,
    0x17202A,
    0xF2F3F4,
    0xBDC3C7,
    0x626567,
    0xFDC7CB,
    0xFA757D,
    0xFD0716,
    0xFBD4B0,
    0xFBB97A,
    0xFE7C02,
    0xBB8FCE,
    0x8E44AD,
    0x6C3483,
    0x6D6D86,
    0x3B3B83,
    0x000080,
    0xD6EAF8,
    0x3498DB,
    0x1B4F72,
    0xE9F7EF,
    0x27AE60,
    0x145A32,
    0xD5F5E3,
    0x2ECC71,
    0x186A3B,
    0xFCF3CF,
    0xF7DC6F,
    0xF1C40F,
    0xB7950B,
    0x7D6608,
    0xFEE8FE,
    0xFDB5FD,
    0xFA7EFA,
    0xFB39FA,
    0xFD03FC,
]


class HexPlugin(IPlugin):
    def execute(self, api: Api):

        self.api = api

        input_dlg_data = [
            {"label": "Memory address", "data": "0x0"},
            {"label": "Size", "data": 2000},
            {"label": "Source trace", "data": ["Full trace", "Filtered trace"]},
            {"label": "Byte order", "data": ["Little endian", "Big endian"]},
        ]
        options = api.get_values_from_user("Data visualizer", input_dlg_data)

        if not options:
            return

        self.address, self.mem_size, trace_id, byte_order = options
        self.address = self.str_to_int(self.address)

        if trace_id == 0:
            trace = api.get_full_trace()
        else:
            trace = api.get_filtered_trace()

        if not trace:
            print("Plugin error: empty trace.")
            return

        if byte_order == 0:
            self.byteorder = "little"
        else:
            self.byteorder = "big"

        self.color_counter = 0
        self.address_colors = {}
        self.mem_read_only = True
        self.show_first_mem_access = True

        data = self.prepare_data(trace)
        self.show_hex_window(data)

    def prepare_data(self, trace: list):
        reg_size = self.api.get_trace_data().pointer_size
        if reg_size < 1:
            reg_size = 4

        result = {}

        for row_index, t in enumerate(trace):
            for mem in t["mem"]:

                if self.mem_read_only and mem["access"] != "READ":
                    continue

                disasm = t["disasm"].lower()
                if "pop" in disasm:
                    data_size = reg_size
                elif "push" in disasm:
                    data_size = reg_size
                elif "qword" in disasm:
                    data_size = 8
                elif "dword" in disasm:
                    data_size = 4
                elif "word" in disasm:
                    data_size = 2
                elif "byte" in disasm:
                    data_size = 1

                # get instruction pointer and row id
                ip = t["ip"]
                row_id = t["id"]

                # slice value to bytes
                try:
                    data_bytes = (mem["value"]).to_bytes(
                        data_size, byteorder=self.byteorder
                    )
                except:
                    print("error:" + str(t))
                    print(f"datasize: {data_size}")
                    break

                # check if in wanted mem range
                if self.address <= mem["addr"] <= self.address + self.mem_size:
                    for i in range(data_size):
                        byte_offset = mem["addr"] - self.address + i

                        if self.show_first_mem_access and byte_offset in result:
                            result[byte_offset]["count"] = +1
                            continue

                        # get a new color if this address doesn't have one
                        if ip not in self.address_colors:
                            color = self.get_next_color()
                            self.address_colors[ip] = color
                        else:
                            color = self.address_colors[ip]

                        if byte_offset not in result:
                            result[byte_offset] = {
                                "ip": ip,
                                "row_index": row_index,
                                "row_id": row_id,
                                "value": data_bytes[i],
                                "count": 1,
                                "color": color,
                            }
                        else:
                            result[byte_offset]["ip"] = ip
                            result[byte_offset]["row_index"] = row_index
                            result[byte_offset]["row_id"] = row_id
                            result[byte_offset]["value"] = data_bytes[i]
                            result[byte_offset]["count"] += 1

                        if i == 0:  # first byte of value?
                            result[byte_offset]["start_block"] = True
        return result

    def show_hex_window(self, data: dict):
        self.window = QWidget()
        self.window.setStyleSheet("background-color:white;")
        self.window.setGeometry(300, 150, 880, 940)
        self.window.setWindowTitle("Data visualizer")

        layout = QVBoxLayout()
        hex_widget = HexViewWidget()
        hex_widget.set_data(data)
        layout.addWidget(hex_widget)

        self.window.statusBar = QStatusBar(self.window)
        self.window.statusBar.setStyleSheet("color:black;")
        layout.addWidget(self.window.statusBar)

        self.window.setLayout(layout)

        hex_widget.mouseLeftClicked.connect(self.mouse_left_clicked)
        hex_widget.mouseRightClicked.connect(self.mouse_right_clicked)
        hex_widget.mouseOver.connect(self.mouse_over_data)

        self.window.show()

    def mouse_over_data(self, item: dict):
        self.window.statusBar.showMessage(str(item))

    def mouse_left_clicked(self, item: dict):
        self.api.go_to_row_in_current_trace(item["row_id"])

    def mouse_right_clicked(self, item: dict):
        self.menu = QMenu(self.window)

        copy_action = QAction("Copy to clipboard", self.window)
        copy_action.triggered.connect(lambda: self.copy_to_clipboard(str(item)))
        self.menu.addAction(copy_action)

        go_action = QAction("Go to trace", self.window)
        go_action.triggered.connect(lambda: self.api.go_to_trace_row(item["row_id"]))
        self.menu.addAction(go_action)

        self.menu.popup(QCursor.pos())

    def copy_to_clipboard(self, text: str):
        QApplication.clipboard().setText(text)

    def get_next_color(self):
        if self.color_counter >= len(COLORS):
            return self.get_random_color()
        color = COLORS[self.color_counter]
        self.color_counter += 1
        return color

    def get_random_color(self):
        return int(random.random() * 0xFFFFFF)

    def str_to_int(self, s: str):
        result = 0
        if s:
            s = s.strip()
            if "0x" in s:
                result = int(s, 16)
            else:
                result = int(s)
        return result
