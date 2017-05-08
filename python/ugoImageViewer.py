#!/usr/bin/python3

# ===============================
# ugoImageViewer.py version 1.0.0
# ===============================
#
# Experimental image viewer Flipnote Studio's proprietary image formats (NFTF, NPF and NBF)
# Implementation by Jaames (github.com/jaames | rakujira.jp)
# Support for NTFT and NBF formats based on work by PBSDS (github.com/pbsds | pbsds.net)
#
# Usage:
# ======
#
# python3 ugoImageViewer.py input_path input_width input_width view_scale(optional)
#
# Issues:
# =======
#
# If you find any bugs in this script, please report them here:
# https://github.com/Sudomemo/sudomemo-utils/issues
#
# Format documentation can be found on the Flipnote-Collective wiki:
#   - nbf: https://github.com/Flipnote-Collective/flipnote-studio-docs/wiki/.nbf-image-format
#   - npf: https://github.com/Flipnote-Collective/flipnote-studio-docs/wiki/.npf-image-format
#   - nntft: https://github.com/Flipnote-Collective/flipnote-studio-docs/wiki/.ntft-image-format
#
# Requirements:
#   - Python 3
#       Installation: https://www.python.org/downloads/
#   - Pygame
#       Installation: http://www.pygame.org/download.shtml
#   - NumPy (http://www.numpy.org/)
#       Installation: https://www.scipy.org/install.html

from pygame import Surface, pixelcopy, transform
import numpy as np

VERSION = "1.0.0"

class baseImageSurface:
    # Round up a number to the nearest power of two
    # Flipnote's image formats really like power of twos
    def round_to_power(self, value):
        if value not in [256, 128, 64, 32, 16, 8, 4, 2, 1]:
            p = 1
            while 1 << p < value:
                p += 1
            return 1 << p
        else:
            return value

    # Return width and height values with padding added to fit the image data width, which is always a power of 2
    def get_size(self, size):
        width, height = size
        return (self.round_to_power(width), height)

    # Unpack an abgr1555 color
    # color = 16-bit uint [1 bit - alpha][5 bits - blue][5 bits - green][5 bits - red]
    # useAlpha = use True to read the alpha bit, else False
    # Returns a 32-bit uint [8 bits - alpha][8 bits - red][8 bits - green][8 bits - blue]
    def unpack_color(self, color, useAlpha=True):
        r = (color       & 0x1f)
        g = (color >> 5  & 0x1f)
        b = (color >> 10 & 0x1f)
        a = (color >> 15 & 0x1)
        r = r << 3 | (r >> 2)
        g = g << 3 | (g >> 2)
        b = b << 3 | (b >> 2)
        return ((0x00 if useAlpha and a == 0 else 0xFF) << 24 | (r << 16) | (g << 8) | (b))

    # Convenience method to apply unpack_color over an array
    def unpack_colors(self, colorArray, useAlpha=True):
        unpack = np.vectorize(self.unpack_color, otypes=[np.uint32])
        return unpack(colorArray, useAlpha=useAlpha)

    def unpack_palette(self, palette):
        palette = self.unpack_colors(palette)
        return np.array([(((color >> 16) & 0xFF), ((color >> 8) & 0xFF), ((color) & 0xFF)) for color in palette], dtype=np.uint8)

    # Read an UGAR header from buffer
    # https://github.com/Flipnote-Collective/flipnote-studio-docs/wiki/.nbf-image-format#header
    # Returns a np array of section lengths
    def read_ugar_header(self, buffer):
        # Skip the magic
        buffer.seek(4)
        sectionCount = np.fromstring(buffer.read(4), dtype=np.uint32)[0]
        sectionTable = np.fromstring(buffer.read(4 * sectionCount), dtype=np.uint32)
        return sectionTable

    # Draw the image to a surface, as pos (x, y), optionally upscaling
    def blit_to(self, surface, pos, scale=1):
        width, height = self.size
        width *= scale
        height *= scale
        self.surface = transform.scale(self.surface, (width, height))
        surface.blit(self.surface, pos, area=(0, 0, width, height))

class ntftSurface(baseImageSurface):
    def __init__(self, imageBuffer, size):
        width, height = self.get_size(size)
        self.size = size
        self.surface = Surface((width, height), depth=32)
        # Unpack the pixel colors
        pixels = self.unpack_colors(np.fromfile(imageBuffer, dtype=np.uint16))
        pixels = np.swapaxes(np.reshape(pixels, (-1, width)), 0, 1)
        pixelcopy.array_to_surface(self.surface, pixels)

class nbfSurface(baseImageSurface):
    def __init__(self, imageBuffer, size):
        width, height = self.get_size(size)
        self.size = size
        self.surface = Surface((width, height), depth=8)
        # Read the header
        paletteLength, imageDataLength = self.read_ugar_header(imageBuffer)
        # Read the image palette and unpack
        palette = self.unpack_palette(np.fromstring(imageBuffer.read(paletteLength), dtype=np.uint16))
        self.surface.set_palette(palette)
        # Read the pixels
        pixels = np.fromstring(imageBuffer.read(imageDataLength), dtype=np.uint8)
        pixels = np.swapaxes(np.reshape(pixels, (-1, width)), 0, 1)
        pixelcopy.array_to_surface(self.surface, pixels)

class npfSurface(baseImageSurface):
    def __init__(self, imageBuffer, size):
        width, height = self.get_size(size)
        self.size = size
        self.surface = Surface((width, height), depth=8)
        # Read the header
        paletteLength, imageDataLength = self.read_ugar_header(imageBuffer)
        # Read the image palette and unpack
        palette = self.unpack_palette(np.fromstring(imageBuffer.read(self.round_to_power(paletteLength)), dtype=np.uint16))
        self.surface.set_palette(palette)
        # All pixels with the index of 0 are transparent
        self.surface.set_colorkey(0)
        # Read the pixel data bytes
        pixelData = np.fromstring(imageBuffer.read(imageDataLength), dtype=np.uint8)
        # Split each byte into 2 pixels
        pixels = np.stack((np.bitwise_and(pixelData, 0x0f), np.bitwise_and(pixelData >> 4, 0x0f)), axis=-1).flatten()
        pixels = np.swapaxes(np.reshape(pixels, (-1, width)), 0, 1)
        pixelcopy.array_to_surface(self.surface, pixels)

if __name__ == "__main__":
    from pygame import display, event, time
    from sys import argv
    import os

    def printhelp():
        print("\n".join([
            "",
            "===============================",
            "ugoImageViewer.py version " + str(VERSION),
            "===============================",
            "",
            "Experimental image viewer Flipnote Studio's proprietary image formats (NFTF, NPF and NBF)",
            "Support for NTFT and NBF formats based on work by PBSDS (github.com/pbsds | pbsds.net)",
            "Implementation by Jaames (github.com/jaames | rakujira.jp)",
            "",
            "Usage:",
            "======",
            "",
            "python3 ugoImageViewer.py input_path input_width input_width view_scale(optional)",
            "",
            "Issues:",
            "=======",
            "",
            "If you find any bugs in this script, please report them here:",
            "https://github.com/Sudomemo/sudomemo-utils/issues",
            ""
        ]))

    args = argv[1::]

    if "-v" in args:
        print(VERSION)
        sys.exit()


    if "-h" in args:
        printhelp()
        sys.exit()

    if len(args) > 2:
        path = args[0]
        filename, extension = os.path.splitext(path)
        size = (int(args[1]), int(args[2]))
        scale = int(args[3]) if len(args) > 3 else 1

        screen = display.set_mode((size[0] * scale, size[1] * scale))

        with open(path, "rb") as imageBuffer:
            extension = extension.lower()
            if extension == ".ntft":
                image = ntftSurface(imageBuffer, size)
            if extension == ".nbf":
                image = nbfSurface(imageBuffer, size)
            if extension == ".npf":
                image = npfSurface(imageBuffer, size)
            image.blit_to(screen, (0, 0), scale=scale)
            display.flip()
            display.set_caption(filename + extension)

        done = False
        while not done:
            for e in event.get():
                if event.event_name(e.type) == "Quit":
                    done = True
            # Slow down the script because it really doesn't need to loop very fast
            time.wait(300)

    else:
        printhelp()
