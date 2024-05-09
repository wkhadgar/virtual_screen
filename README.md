# virtual_screen

Get a copy of your virtual ram into the big screen! This repo aims to help embedded devs to access screen buffers and
display them just as the real hardware.

# How to use

Type `python virtual_screen -h` for detailed usage.

## Jlink

- Connect your device via SWD with SEGGER J-Link
- In your code, send via RTT, as early as possible, the display frame buffer address with the template: `D-VRAM: <adrr>`
- Run the virtual screen: `python virtual_screen.py <device> <params>`
    - Example: `python virtual_screen.py efr32bg22cxxxf352` (mono 128x64 Screen [default] on Silabs Thunderboard target)

## OpenOCD

- Connect your device via JTAG
- Locate the frame buffer address
- Start the OpenOCD server.
- Run the virtual screen: `python virtual_screen.py openocd <params>`
    - Example: `python virtual_screen.py openocd -d rgb565 --width 240 --height 320 -a 0xDEADBEEF` (RGB565 240x320
      Screen @ `0xDEADBEEF`)
