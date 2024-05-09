"""
 :file: virtual_screen.py
 :author: Paulo Santos (pauloroberto.santos@edge.ufal.br)
 :brief: Simulates a screen from a device connected via SWD.
 :version: 0.1
 :date: 08-05-2024

 :copyright: Copyright (c) 2024
"""

import sys
import pylink
import argparse

from PyQt5 import QtCore, QtGui, QtWidgets

# Define as cores do display
BLACK = (0, 0, 0, 255)
WHITE = (255, 255, 255, 255)


class VirtualScreen(QtWidgets.QMainWindow):
    SCALE = 2
    PIXEL_COLOR = WHITE
    BG_COLOR = BLACK

    def __init__(self, *, fps=60, vram_size: tuple[int, int] = (128, 64), mode: str = "mono"):
        """
        Inicialize the virtual screen.

        :param framerate: Escala do tamanho original da tela.
        :param vram_size: Tamanho original da tela a ser emulada
        :param mode: Frame rate da atualização da tela emulada
        """

        super().__init__()

        self.mode = mode
        self.vram_w, self.vram_h = vram_size

        self.timer = QtCore.QTimer()
        self.timer.setInterval(1000 // fps)
        self.timer.start()
        if mode == "mono":
            self.vram_pages: int = self.vram_h // 8
            self.timer.timeout.connect(self.draw_screen_mono)
        elif mode == "rgb565":
            self.pixel_depth = 2
            self.timer.timeout.connect(self.draw_screen_rgb565)

        window_size = (self.vram_w * VirtualScreen.SCALE, self.vram_h * VirtualScreen.SCALE)
        self.canvas = QtGui.QPixmap(*window_size)
        self.label = QtWidgets.QLabel()
        self.label.setPixmap(self.canvas)

        self.setFixedSize(*window_size)
        self.setWindowTitle("Virtual Screen")
        self.setCentralWidget(self.label)
        self.setMouseTracking(False)

        self.painter = QtGui.QPainter(self.label.pixmap())
        self.pen = QtGui.QPen()
        self.set_pixel_color_rgb()

    def set_pixel_color_rgb(self, color=PIXEL_COLOR, *, size=SCALE):
        """
        Sets the pixel color.

        :param size: Size of pixel, in scale.
        :param color: Pixel color, as an RGB tuple.
        """

        self.pen.setWidth(size)
        self.pen.setColor(QtGui.QColor(*tuple(color)))
        self.painter.setPen(self.pen)

    def set_pixel_color_16(self, pixel_16: int, *, size=SCALE):
        b_val = (pixel_16 & 0b00000_000000_11111) * 8
        g_val = ((pixel_16 & 0b00000_111111_00000) >> 5) * 4
        r_val = ((pixel_16 & 0b11111_000000_00000) >> (5 + 6)) * 8

        self.pen.setWidth(size)
        self.pen.setColor(QtGui.QColor(r_val, g_val, b_val))
        self.painter.setPen(self.pen)

    def clear_screen(self, bg_color=BG_COLOR):
        """
        Clears the drawn screen.

        :param bg_color: Color for bg filling.
        """

        self.set_pixel_color_rgb(size=self.canvas.height(), color=bg_color)
        self.painter.drawLine(0, self.canvas.height() // 2, self.canvas.width(), self.canvas.height() // 2)
        self.set_pixel_color_rgb(size=VirtualScreen.SCALE, color=VirtualScreen.PIXEL_COLOR)

    def draw_screen_mono(self):
        """
        Draws the screen, based on the mono-vRAM of the device.
        """

        vram = jlink.memory_read(addr=DISPLAY_VRAM_OFFSET, num_units=self.vram_w * self.vram_pages, nbits=8)

        self.clear_screen()
        for page in range(self.vram_pages):
            for column in range(self.vram_w):
                byte = vram[(column + (page * self.vram_w))]
                for bit_pos in range(8):
                    if byte & (1 << bit_pos):
                        self.painter.drawPoint(column * VirtualScreen.SCALE,
                                               (bit_pos + (page * self.vram_pages)) * VirtualScreen.SCALE)

        self.update()

    def draw_screen_rgb565(self):
        """
        Draws the screen, based on the RGB565-vRAM of the device.
        """

        vram = jlink.memory_read(addr=DISPLAY_VRAM_OFFSET, num_units=self.vram_w * self.vram_h,
                                 nbits=8 * self.pixel_depth)

        self.clear_screen()
        for row in range(self.vram_h):
            for column in range(self.vram_w):
                pixel = vram[(column + (row * self.vram_w))]
                self.set_pixel_color_16(pixel)
                self.painter.drawPoint(column * VirtualScreen.SCALE, row * VirtualScreen.SCALE)

        self.update()


def get_params():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mcu", metavar="mcu", help="MCU to be connected.")
    parser.add_argument("-i", "--interface", metavar="<interface>", help="Debug interface.", choices=["swd", "jtag"],
                        default="swd")
    parser.add_argument("-d", "--display", metavar="<display type>", help="Type of display to emulate.",
                        choices=["mono", "rgb565"], default="mono")
    parser.add_argument("--width", metavar="<display width>", help="Width of the display.", default=128)
    parser.add_argument("--height", metavar="<display height>", help="Height of the display.", default=64)
    parser.add_argument("-f", "--fps", metavar="<frame rate>", help="Emulated framerate.", default=60)

    mcu: str = parser.parse_args().mcu
    dbg: str = parser.parse_args().interface
    draw_mode: str = parser.parse_args().display
    disp_size: tuple[int, int] = (parser.parse_args().width, parser.parse_args().height)
    fps: int = parser.parse_args().fps

    return mcu.upper(), dbg.strip().lower(), draw_mode.strip().lower(), disp_size, fps


if __name__ == "__main__":
    target_mcu, debug_interface, display_type, display_size, framerate = get_params()

    # Opens JLink interface.
    jlink = pylink.JLink()
    jlink.open()
    jlink.rtt_start()
    print(jlink.product_name)

    # Connects with the MCU.
    jlink.set_tif(
        pylink.enums.JLinkInterfaces.JTAG if debug_interface == "jtag" else pylink.enums.JLinkInterfaces.SWD)
    jlink.connect(target_mcu)

    # Get the display framebuffer location.
    rtt_out = []
    while len(rtt_out) < 1:
        rtt_out = jlink.rtt_read(0, 200)

    rtt_buffer_data = ''.join(chr(val) for val in rtt_out).split("\n")

    for data in rtt_buffer_data:
        if data.startswith("D-VRAM:"):
            DISPLAY_VRAM_OFFSET = int(data[8:], 16)
            print(f"D-VRAM (display data buffer) reported at: 0x{DISPLAY_VRAM_OFFSET:X}")
            break
    else:
        raise NameError("The code must send via RTT the address of the display frame buffer ('D-VRAM').\n"
                        "The message should follow the pattern: 'D-VRAM: <address>'\n"
                        "e.g.: 'D-VRAM: 0xDEADBEEF'")

    # Starts the virtual screen.
    emulator = QtWidgets.QApplication(sys.argv)

    screen = VirtualScreen(vram_size=display_size, mode=display_type, fps=framerate)
    screen.show()

    emulator.exec_()
