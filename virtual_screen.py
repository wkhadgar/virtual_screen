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
import openocd

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

    @staticmethod
    def get_frame_buffer(dbg: pylink.JLink | openocd.OpenOcd, *, amount: int, unit_size: int):
        if isinstance(dbg, openocd.OpenOcd):
            dbg.halt()
            fb = dbg.read_memory(address=DISPLAY_VRAM_OFFSET, count=amount, width=unit_size)
            dbg.resume()
            return fb
        elif isinstance(dbg, pylink.JLink):
            return dbg.memory_read(addr=DISPLAY_VRAM_OFFSET, num_units=amount, nbits=unit_size)

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

        vram = self.get_frame_buffer(debugger, amount=self.vram_w * self.vram_pages, unit_size=8)

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

        vram = self.get_frame_buffer(debugger, amount=(self.vram_w * self.vram_h) // 4, unit_size=16 * 4)

        row_offset = self.vram_w // 4
        self.clear_screen()
        for p_y in range(self.vram_h):
            i_x = p_x = 0
            i_y = p_y * row_offset
            while p_x < self.vram_w:
                pixel_quartet = vram[i_x + i_y]

                pixel_0 = (pixel_quartet & 0x0000_0000_0000_FFFF)
                pixel_1 = (pixel_quartet & 0x0000_0000_FFFF_0000) >> 16
                pixel_2 = (pixel_quartet & 0x0000_FFFF_0000_0000) >> 32
                pixel_3 = (pixel_quartet & 0xFFFF_0000_0000_0000) >> 48

                self.set_pixel_color_16(pixel_0)
                self.painter.drawPoint(p_x * VirtualScreen.SCALE, p_y * VirtualScreen.SCALE)
                self.set_pixel_color_16(pixel_1)
                self.painter.drawPoint((p_x + 1) * VirtualScreen.SCALE, p_y * VirtualScreen.SCALE)
                self.set_pixel_color_16(pixel_2)
                self.painter.drawPoint((p_x + 2) * VirtualScreen.SCALE, p_y * VirtualScreen.SCALE)
                self.set_pixel_color_16(pixel_3)
                self.painter.drawPoint((p_x + 3) * VirtualScreen.SCALE, p_y * VirtualScreen.SCALE)

                i_x += 1
                p_x += 4

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
    parser.add_argument("-a", "--address", metavar="<address>", help="Frame buffer address, only used if mcu=OpenOCD.",
                        default="0")

    mcu: str = parser.parse_args().mcu
    dbg: str = parser.parse_args().interface
    draw_mode: str = parser.parse_args().display
    disp_size = (int(parser.parse_args().width), int(parser.parse_args().height))
    fps = int(parser.parse_args().fps)
    addr = int(parser.parse_args().address, 16)

    return mcu.strip().upper(), dbg.strip().lower(), draw_mode.strip().lower(), disp_size, fps, addr


if __name__ == "__main__":
    target_mcu, debug_interface, display_type, display_size, framerate, address = get_params()

    if target_mcu == "OPENOCD":
        if address == 0:
            sys.exit("Parameter <address> must be specified if mcu=OpenOCD (-h for help).")

        debugger = openocd.OpenOcd()

        try:
            debugger.connect()
        except ConnectionRefusedError:
            sys.exit("Failed to connect to OpenOCD device. Did you started the OpenOCD server?")

        cores = debugger.targets()
        debugger.execute(f"targets {cores[0]}")

        # Get the address of the display buffer. (this should be manually updated)
        DISPLAY_VRAM_OFFSET = address
    else:

        # Opens JLink interface.
        debugger = pylink.JLink()
        debugger.open()
        debugger.rtt_start()
        print(debugger.product_name)

        # Connects with the MCU.
        debugger.set_tif(
            pylink.enums.JLinkInterfaces.JTAG if debug_interface == "jtag" else pylink.enums.JLinkInterfaces.SWD)
        debugger.connect(target_mcu)

        # Get the display framebuffer location.
        rtt_out = []
        while len(rtt_out) < 1:
            rtt_out = debugger.rtt_read(0, 200)

        rtt_buffer_data = ''.join(chr(val) for val in rtt_out).split("\n")

        for data in rtt_buffer_data:
            if data.startswith("D-VRAM:"):
                DISPLAY_VRAM_OFFSET = int(data[8:], 16)
                print(f"D-VRAM (display data buffer) reported at: 0x{DISPLAY_VRAM_OFFSET:X}")
                break
        else:
            raise NameError("The device must send via RTT the address of the display frame buffer ('D-VRAM').\n"
                            "The message must be sent in boot (asap) and follow the pattern: 'D-VRAM: <address>'\n"
                            "e.g.: 'D-VRAM: 0xDEADBEEF'")

    # Starts the virtual screen.
    emulator = QtWidgets.QApplication(sys.argv)

    screen = VirtualScreen(vram_size=display_size, mode=display_type, fps=framerate)
    screen.show()

    emulator.exec_()
