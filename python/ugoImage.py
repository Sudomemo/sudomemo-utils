#!/usr/bin/python3

# =========================
# ugoImage.py version 1.0.0
# =========================
#
# Convert images to and from Flipnote Studio's proprietary image formats (NFTF, NPF and NBF)
# Originally written for Sudomemo (github.com/Sudomemo | www.sudomemo.net)
# Implementation by Jaames (github.com/jaames | rakujira.jp)
# Support for NTFT and NBF formats based on work by PBSDS (github.com/pbsds | pbsds.net)
#
# Usage:
# ======
#
# Convert an NTFT, NBF or NPF to a standard image format like PNG:
# Python3 ugoImage.py -i input_path image_width image_height -o output_path
#
# Convert a standard image format like PNG to NTFT, NBF, or NPF:
# Python3 ugoImage.py -i input_path -o output_path
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
#   - The Pillow Image Library (https://python-pillow.org/)
#       Installation: http://pillow.readthedocs.io/en/3.0.x/installation.html
#   - NumPy (http://www.numpy.org/)
#       Installation: https://www.scipy.org/install.html

from PIL import Image, ImageOps
import numpy as np

VERSION = "1.0.0"

# Round up a number to the nearest power of two
# Flipnote's image formats really like power of twos
def roundToPower(value):
    if value not in [256, 128, 64, 32, 16, 8, 4, 2, 1]:
        p = 1
        while 1 << p < value:
            p += 1
        return 1 << p
    else:
        return value

# Unpack an abgr1555 color
# value = 16-bit uint [1 bit - alpha][5 bits - blue][5 bits - green][5 bits - red]
# useAlpha = use True to read the alpha bit, else False
# Returns a 32-bit uint [8 bits - red][8 bits - green][8 bits - blue][8 bits - alpha]
def unpackColor(value, useAlpha=True):
    r = (value       & 0x1f)
    g = (value >> 5  & 0x1f)
    b = (value >> 10 & 0x1f)
    a = (value >> 15 & 0x1)
    r = r << 3 | (r >> 2)
    g = g << 3 | (g >> 2)
    b = b << 3 | (b >> 2)
    return ((r << 24) | (g << 16) | (b << 8) | (0x00 if useAlpha and a == 0 else 0xFF))

# Output is a 16-bit integer:
# color = [r, g, b, a (optional)]
# useAlpha = use True to use the alpha value, else False
# Returns [blue - 5 bits][green - 5 bits][red - 5 bits][alpha - 1 bit]
def packColor(color, useAlpha=True):
    # Limit each color channel to 5 bits, by removing the last 3 bits
    r = color[0] & 0xF8
    g = color[1] & 0xF8
    b = color[2] & 0xF8
    # Combine them together into one 16-bit integer
    return ((b << 7) | (g << 2) | (r >> 3) | (0 if useAlpha and color[3] < 128 else 1))

# Convenience method to apply unpackColor over an array
unpackColors = np.vectorize(unpackColor, otypes=[">u4"])

# Convenience method to apply packColor over an array of colors
def packColors(colors, useAlpha=True):
    return np.apply_along_axis(packColor, 1, colors, useAlpha=useAlpha).astype(np.uint16)

# ugoImage class
class ugoImage:

    def __init__(self, imageBuffer=None, imageFormat=None, imageWidth=0, imageHeight=0):
        if imageBuffer:
            self.load(imageBuffer, imageWidth, imageHeight, imageFormat)

    def load(self, imageBuffer, imageFormat=None, imageWidth=0, imageHeight=0):
        # Some prefer uppercase extentions over lowercase... I don't :P
        imageFormat = imageFormat.lower()
        if not imageFormat or imageFormat not in ["npf", "nbf", "ntft"]:
            self.image = Image.open(imageBuffer)
        elif imageFormat == "npf":
            self.image = self.parseNpf(imageBuffer, imageWidth, imageHeight)
        elif imageFormat == "nbf":
            self.image = self.parseNbf(imageBuffer, imageWidth, imageHeight)
        elif imageFormat == "ntft":
            self.image = self.parseNtft(imageBuffer, imageWidth, imageHeight)

    def save(self, outputBuffer, imageFormat):
        imageFormat = imageFormat.lower()
        if not imageFormat or imageFormat not in ["npf", "nbf", "ntft"]:
            self.image.save(outputBuffer, imageFormat)
        elif imageFormat == "npf":
            self.writeNpf(outputBuffer)
        elif imageFormat == "nbf":
            self.writeNbf(outputBuffer)
        elif imageFormat == "ntft":
            self.writeNtft(outputBuffer)

    # Write an UGAR header to an outputBuffer
    # https://github.com/Flipnote-Collective/flipnote-studio-docs/wiki/.nbf-image-format#header
    def _writeUgarHeader(self, outputBuffer, *sectionLengths):
        # Start the section table from the section lengths given
        sectionTable = np.array(sectionLengths, dtype=np.uint32)
        # Insert the section count to the start of the section table
        sectionTable = np.insert(sectionTable, 0, len(sectionTable))
        # Write to the buffer
        outputBuffer.write(b"UGAR")
        outputBuffer.write(sectionTable.tobytes())

    # Read an UGAR header from buffer
    # https://github.com/Flipnote-Collective/flipnote-studio-docs/wiki/.nbf-image-format#header
    # Returns a np array of section lengths
    def _readUgarHeader(self, buffer):
        # Skip the magic
        buffer.seek(4)
        sectionCount = np.fromstring(buffer.read(4), dtype=np.uint32)[0]
        sectionTable = np.fromstring(buffer.read(4 * sectionCount), dtype=np.uint32)
        return sectionTable

    # If the image width isn't a power-of-two, then add padding until it is
    # imageData = 1-D array of pixels
    # imageSize = (width, height)
    # Returns 1-D array of pixels, with padding added in
    def _padImageData(self, imageData, imageSize):
        width, height = imageSize
        clipWidth = roundToPower(width)
        # We use the "edge" padding mode to repeat the edge of each side until the image is the correct size
        # Hatena's encoder did this, and they sometimes made use of this effect in theme images
        if clipWidth != width:
            # Reshape the image data into a 2D array
            imageData = np.reshape(imageData, (-1, width))
            imageData = np.pad(imageData, ((0, 0), (0, clipWidth - width)), "edge")
            # Flatten back to a 1d array
            return imageData.flatten()
        # Else just return the imageData
        return imageData

    # Clip an image out of a power-of-two width image
    # imageData = 1-D array of pixels
    # imageSize = (width, height)
    # Returns 2-D array of pixels
    def _clipImageData(self, imageData, imageSize):
        width, height = imageSize
        # Round the width up to the nearest power of two
        clipWidth = roundToPower(width)
        # Reshape the image array to make a 2D array with the "real" image width / height
        imageData = np.reshape(imageData, (-1, clipWidth))
        # Clip the "requested" image size out of the "real" image
        return imageData[0:height, 0:width]

    # Limit the colors of an image
    # image = PIL Image object
    # paletteSlots = the number of colors to use
    # Returns PIL Image with palette mode
    def _limitImageColors(self, image, paletteSlots=0):
        # Convert the image to RGB, then posterize to clamp the color channels to 5 bit values
        image = image.convert("RGB")
        image = ImageOps.posterize(image, 5)
        return image.convert("P", palette=Image.ADAPTIVE, colors=paletteSlots)

    # Reads an npf image from buffer, and returns an array of RGBA pixels
    def parseNpf(self, buffer, imageWidth, imageHeight):
        # Read the header
        sectionLengths = self._readUgarHeader(buffer)
        # Read the palette data (section number 1)
        paletteData = np.frombuffer(buffer.read(roundToPower(sectionLengths[0])), dtype=np.uint16)
        # Read the image data (section number 2)
        imageData = np.frombuffer(buffer.read(sectionLengths[1]), dtype=np.uint8)
        # NPF image data uses 1 byte per 2 pixels, so we need to split that byte into two
        imageData = np.stack((np.bitwise_and(imageData, 0x0f), np.bitwise_and(imageData >> 4, 0x0f)), axis=-1).flatten()
        # Unpack palette colors
        palette = unpackColors(paletteData, useAlpha=False)
        # Convert each pixel from a palette index to full color
        pixels = np.fromiter((palette[i] if i > 0 else 0 for i in imageData), dtype=">u4")
        # Clip the image data and create a Pillow image from it
        return Image.fromarray(self._clipImageData(pixels, (imageWidth, imageHeight)), mode="RGBA")

    # Write the image as an npf to buffer
    def writeNpf(self, outputBuffer):
        alphamap = np.reshape(self.image.split()[-1], (-1, 2))
        # Convert the image to a paletted format with 15 slots
        image = self._limitImageColors(self.image, paletteSlots=15)
        # Get the image palette
        palette = np.reshape(image.getpalette(), (-1, 3))[0:15]
        paletteData = packColors(palette, useAlpha=False)
        # Get the image data and pad it
        imageData = np.array(image.getdata(), dtype=np.uint8)
        imageData = self._padImageData(imageData, image.size)
        # Reshape image data so each item = 2 pixels
        imageData = np.reshape(imageData, (-1, 2))
        # Combine those groups of two pixels together into a single byte
        imageData = np.array([(pix[0]+1 if a[0] > 128 else 0) | ((pix[1]+1 if a[1] > 128 else 0) << 4) for a, pix in zip(alpha, imageData)], dtype=np.uint8)
        # Write to buffer
        self._writeUgarHeader(outputBuffer, paletteData.nbytes, imageData.nbytes)
        outputBuffer.write(paletteData.tobytes())
        outputBuffer.write(imageData.tobytes())

    # Reads an nbf image from buffer, and returns an array of RGBA pixels
    def parseNbf(self, buffer, imageWidth, imageHeight):
        # Read the header
        sectionLengths = self._readUgarHeader(buffer)
        # Read the palette data (section number 1)
        paletteData = np.frombuffer(buffer.read(sectionLengths[0]), dtype=np.uint16)
        # Read the image data (section number 2)
        imageData = np.frombuffer(buffer.read(sectionLengths[1]), dtype=np.uint8)
        # Convert the palette to rgb888
        palette = unpackColors(paletteData, useAlpha=False)
        # Convert each pixel from a palette index to full color
        pixels = np.fromiter((palette[pixel] for pixel in imageData), dtype=">u4")
        # Clip the image data and create a Pillow image from it
        return Image.fromarray(self._clipImageData(pixels, (imageWidth, imageHeight)), mode="RGBA")

    # Write the image as an nbf to buffer
    def writeNbf(self, outputBuffer):
        image = self._limitImageColors(self.image, paletteSlots=256)
        # Get the image palette
        palette = np.reshape(image.getpalette(), (-1, 3))
        # Pack the palette colors
        paletteData = packColors(palette, useAlpha=False)
        # Get the image data and add padding
        imageData = np.array(image.getdata(), dtype=np.uint8)
        imageData = self._padImageData(imageData, image.size)
        # Write to file
        self._writeUgarHeader(imageData, paletteData.nbytes, imageData.nbytes)
        imageData.write(paletteData.tobytes())
        imageData.write(imageData.tobytes())

    # Reads an ntft image from buffer, and returns an array of RGBA pixels
    def parseNtft(self, buffer, imageWidth, imageHeight):
        # Read the image data to an array
        imageData = np.fromfile(buffer, dtype=np.uint16)
        # Convert the image data from rgba5551 to rgba8888
        pixels = unpackColors(imageData, useAlpha=True)
        # Clip the image data and create a Pillow image from it
        return Image.fromarray(self._clipImageData(pixels, (imageWidth, imageHeight)), mode="RGBA")

    # Write the image as an btft to buffer
    def writeNtft(self, outputBuffer):
        imageData = self.image.getdata()
        # Convert the pixel data to rgb
        imageData = packColors(imageData, useAlpha=True)
        imageData = self._padImageData(imageData, self.image.size)
        outputBuffer.write(imageData.tobytes())

if __name__ == "__main__":

    import sys, os

    def representsInt(s):
        try:
            int(s)
            return True
        except ValueError:
            return False

    args = sys.argv[1::]
    argIndex = 0

    image = ugoImage()

    if "-v" in args:
        print(VERSION)
        sys.exit()


    if "-h" in args:
        print("\n".join([
            "",
            "=========================",
            "ugoImage.py version " + str(VERSION),
            "=========================",
            "",
            "Convert images to and from Flipnote Studio's proprietary image formats (NFTF, NPF and NBF)",
            "Originally written for Sudomemo (github.com/Sudomemo | www.sudomemo.net)",
            "Implementation by Jaames (github.com/jaames | rakujira.jp)",
            "Support for NTFT and NBF formats based on work by PBSDS (github.com/pbsds | pbsds.net)",
            "",
            "Usage:",
            "======",
            "",
            "Convert an NTFT, NBF or NPF to a standard image format like PNG:",
            "Python3 ugoImage.py -i input_path image_width image_height -o output_path",
            "",
            "Convert a standard image format like PNG to NTFT, NBF, or NPF:",
            "Python3 ugoImage.py -i input_path -o output_path",
            "",
            "Issues:",
            "=======",
            "",
            "If you find any bugs in this script, please report them here:",
            "https://github.com/Sudomemo/sudomemo-utils/issues",
            ""
        ]))
        sys.exit()

    if "-i" not in args:
        print("No input specified")
        sys.exit()

    if "-o" not in args:
        print("No output specified")
        sys.exit()

    while argIndex < len(args):

        arg = args[argIndex]

        # Input path
        if arg == "-i":

            path = args[argIndex + 1]
            filename, extension = os.path.splitext(path)
            extension = extension.split(".")[1]

            if extension.lower() in ["nbf", "ntft", "npf"]:

                if not representsInt(args[argIndex + 2]) or not representsInt(args[argIndex + 3]):
                    print("Error: width and height must be specified for " + filename + "." + extension)
                    sys.exit()

                else:
                    width = int(args[argIndex + 2])
                    height = int(args[argIndex + 3])

                    with open(path, "rb") as infile:
                        image.load(infile, imageFormat=extension, imageWidth=width, imageHeight=height)

                argIndex += 4

            else:
                with open(path, "rb") as infile:
                    image.load(infile, imageFormat=extension)

                argIndex += 2

        # Output path
        elif arg == "-o":
            path = args[argIndex + 1]
            filename, extension = os.path.splitext(path)
            extension = extension.split(".")[1]

            with open(path, "wb") as outfile:
                image.save(outfile, imageFormat=extension)

            argIndex += 2

# James is really cool, btw
