import string
from math import ceil
from PyQt5.QtWidgets import QAbstractScrollArea, QWidget
from PyQt5.QtCore import Qt, QPoint, QRect, QEvent, pyqtSignal
from PyQt5.QtGui import QCursor, QColor, QFont, QPainter, QBrush


class HexViewWidget(QAbstractScrollArea):

    mouseLeftClicked = pyqtSignal(dict)
    mouseRightClicked = pyqtSignal(dict)
    mouseOver = pyqtSignal(dict)

    def __init__(self, parent=None):
        QWidget.__init__(self, parent=parent)
        self.data = None
        self.init_ui()

    def init_ui(self):

        self.rows = 0
        self.bytes_per_row = 16
        self.first_row_y = 20
        self.row_height = 20
        self.byte_width = 30
        self.ascii_width = 16

        self.addr_table_x = 10

        self.hex_table_x = 80
        self.hex_table_width = self.byte_width * self.bytes_per_row

        self.ascii_table_x = self.hex_table_x + self.hex_table_width + 20
        self.ascii_table_width = self.ascii_width * self.bytes_per_row

        self.setMouseTracking(True)
        self.installEventFilter(self)

        self.show()

    def eventFilter(self, source, event: QEvent):
        if self.data is not None:
            if event.type() == QEvent.MouseButtonRelease:
                pos = event.pos()
                data = self.get_data_at(pos.x(), pos.y())
                if data is not None:
                    if event.button() == Qt.LeftButton:
                        self.mouseLeftClicked.emit(data)
                    elif event.button() == Qt.RightButton:
                        self.mouseRightClicked.emit(data)
            elif event.type() == QEvent.MouseMove:
                pos = event.pos()
                data = self.get_data_at(pos.x(), pos.y())
                if data is not None:
                    self.mouseOver.emit(data)
                    self.viewport().setCursor(Qt.PointingHandCursor)
                else:
                    self.viewport().setCursor(Qt.ArrowCursor)

        return QWidget.eventFilter(self, source, event)

    def paintEvent(self, event: QEvent):
        if self.data is None:
            return

        painter = QPainter()
        painter.begin(self.viewport())

        self.draw_adresses(painter)
        self.draw_hex_and_ascii(painter)

        painter.end()

    def resizeEvent(self, event: QEvent):
        self.setup_scrollbar()
        return QWidget.resizeEvent(self, event)

    def setup_scrollbar(self):
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.verticalScrollBar().setRange(
            0, max(0, 1 + self.rows - self.visible_rows())
        )
        self.verticalScrollBar().setPageStep(self.visible_rows())

    def set_data(self, data: dict):
        self.data = data
        if data:
            self.max_data_index = int(max(self.data, key=int))
            self.rows = int(self.max_data_index / self.bytes_per_row) + 1
        else:
            self.max_data_index = 0
            self.rows = 0

        self.setup_scrollbar()

    def visible_rows(self):
        return int(ceil(float(self.viewport().height()) / self.row_height))

    def luminance(self, color: int):
        r = (color & 0xFF0000) >> 16
        g = (color & 0x00FF00) >> 8
        b = color & 0x0000FF
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    def invert_color(self, color: int, bw: bool = False):
        if bw:  # black / white
            if self.luminance(color) < 128:
                return 0xFFFFFF
            else:
                return 0x0
        return color ^ 0x00FFFFFF

    def get_data_at(self, x: int, y: int):
        if y < self.first_row_y:
            return
        if self.hex_table_x < x < self.hex_table_x + self.hex_table_width:
            x_index = int((x - self.hex_table_x) / self.byte_width)
        elif self.ascii_table_x < x < self.ascii_table_x + self.ascii_table_width:
            x_index = int((x - self.ascii_table_x) / self.ascii_width)
        else:
            return None

        scroll_value = self.verticalScrollBar().value()

        y_index = int((y - self.first_row_y - 4) / self.row_height)
        index = (y_index + scroll_value) * self.bytes_per_row + x_index
        if index in self.data:
            return self.data[index]

    def draw_adresses(self, painter: QPainter):
        first_row = self.verticalScrollBar().value()
        last_row = min(first_row + self.visible_rows(), self.rows)
        x = self.addr_table_x
        y = self.first_row_y + 15
        for row in range(first_row, last_row):
            addr_hex = hex(row * self.bytes_per_row)
            self.draw_text(
                painter, addr_hex, x, y, 0x0,
            )
            y += self.row_height

        # draw horizontal 0-f
        for i in range(16):
            x = self.hex_table_x + i * self.byte_width + 10
            self.draw_text(painter, hex(i)[-1], x, 10, 0x0)

    def int_to_hex(self, value: int):
        hex_str = hex(value)[2:]
        if len(hex_str) < 2:
            hex_str = "0" + hex_str
        return hex_str

    def draw_hex_and_ascii(self, painter: QPainter):
        scroll_value = self.verticalScrollBar().value()
        first_index = scroll_value * self.bytes_per_row
        last_index = min(
            self.max_data_index + 1,
            (scroll_value + self.visible_rows()) * self.bytes_per_row,
        )

        for i, byte_index in enumerate(range(first_index, last_index)):
            if byte_index in self.data:

                bg_color = self.data[byte_index]["color"]
                text_color = self.invert_color(bg_color, bw=True)

                byte_hex = self.int_to_hex(self.data[byte_index]["value"]).upper()
                byte_ascii = chr(self.data[byte_index]["value"])

                if byte_ascii not in string.printable:
                    byte_ascii = "."

                start_block = False
                if "start_block" in self.data[byte_index]:
                    start_block = True

                y = self.first_row_y + int(i / self.bytes_per_row) * self.row_height

                # draw hex
                x = self.hex_table_x + (i % self.bytes_per_row) * self.byte_width
                rect = QRect(x, y, self.byte_width, self.row_height)
                self.draw_bg_rect(painter, rect, bg_color)
                self.draw_text(painter, byte_hex, x + 6, y + 15, text_color)
                if start_block:
                    painter.drawLine(rect.x(), rect.top() + 1, rect.x(), rect.bottom())

                # draw ascii
                x = self.ascii_table_x + (i % self.bytes_per_row) * self.ascii_width
                rect = QRect(x, y, self.ascii_width, self.row_height)
                self.draw_bg_rect(painter, rect, bg_color)
                self.draw_text(painter, byte_ascii, x + 3, y + 15, text_color)
                if start_block:
                    painter.drawLine(rect.x(), rect.top() + 1, rect.x(), rect.bottom())

    def draw_bg_rect(self, painter: QPainter, rect: QRect, color: int):
        painter.setPen(Qt.NoPen)
        brush = QBrush(QColor(color))
        painter.setBrush(brush)
        painter.drawRect(rect)

        # draw line at bottom of the rect
        painter.setPen(QColor(self.invert_color(color, bw=True)))
        painter.drawLine(rect.x(), rect.bottom(), rect.right(), rect.bottom())

    def draw_text(self, painter: QPainter, text: str, x: int, y: int, color: int):
        painter.setPen(QColor(color))
        painter.setFont(QFont("Courier", 10))
        painter.drawText(QPoint(x, y), text)
