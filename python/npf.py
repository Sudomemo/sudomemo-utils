#!/usr/bin/python

# NPF image converter script for Sudomemo
# github.com/Sudomemo | www.sudomemo.net
#
# Written by James Daniel
# github.com/jaames | rakujira.jp
#
# Partially based on PBSDS' NBF script
# https://gist.github.com/pbsds/9c1c0fc417f49f7ef21d
# github.com/pbsds | pbsds.net
#
# Format documentation can be found on the Flipnote-Collective wiki:
# https://github.com/Flipnote-Collective/flipnote-studio-docs/wiki/.npf-image-format

from PIL import Image
import numpy as np
from sys import argv

#rgb555 to rgb888
def rgb555(value):
    r = (value       & 0x1f)
    g = (value >> 5  & 0x1f)
    b = (value >> 10 & 0x1f)
    r = r<<3 | (r>>2)
    g = g<<3 | (g>>2)
    b = b<<3 | (b>>2)
    # order of Red, Green, Blue, Alpha
    return ((r<<24) | (g<<16) | (b<<8) | 0xFF)

def getClipWidth(width):
    if width not in [256, 128, 96, 64, 32, 16, 8, 4]:
        p = 1
        while 1<<p < width:
            p += 1
        return 1<<p
    else:
        return width

def decode(inpath, outpath, width, height):
    f = open(inpath, 'rb')
    # skip first 8 bytes
    f.seek(8)
    # read length table
    paletteLength, imageLength = np.fromstring(f.read(8), dtype=np.uint32)
    # read pallete
    paletteData = np.fromstring(f.read(paletteLength), dtype=np.uint16)
    # read image data
    imageData = np.fromstring(f.read(imageLength), dtype=np.uint8)
    f.close()
    # convert palette to rgb888
    palette = np.array([rgb555(val) for val in paletteData], dtype=np.uint32)
    # get image data
    image = np.array([palette[j] if j > 0 else 0 for i in zip(np.bitwise_and(imageData, 0x0f), np.bitwise_and(imageData >> 4, 0x0f)) for j in i], dtype=">u4")
    # clip the image if necessary
    clipWidth = getClipWidth(width)
    image = Image.frombytes("RGBA", (clipWidth, height), image.tobytes("C"))
    if not width == clipWidth:
        image = image.crop((0, 0, width, height))
    image.save(outpath, "png")

def encode(inpath, outpath):
    # open image
    image = Image.open(inpath)
    # get image size
    width, height = image.size
    # image data width has to be a power of two
    clipWidth = getClipWidth(width)
    if not width == clipWidth:
        image = image.crop((0, 0, clipWidth, height))
    # get image alpha map
    alpha = np.reshape(image.split()[-1], (-1, 2))
    # convert image to 15-color palleted format
    image = image.convert("P", palette=Image.ADAPTIVE, colors=15)
    # get image pallette
    palette = np.reshape(image.getpalette()[0:15*3], (-1, 3))
    # get the image data as an array of pallette indecies
    image = np.reshape(image.getdata(), (-1, 2))
    # convert the pallete colors to RGB555
    paletteData = np.array([((col[0] >> 3) | ((col[1] & 0xF8) << 2) | ((col[2] & 0xF8) << 7) | 0x00) for col in palette], dtype=np.uint16)
    # write first palette entry (always 0)
    paletteData = np.insert(paletteData, 0, 0)
    # convert image data
    imageData = np.array([(pix[0]+1 if a[0] > 128 else 0) | ((pix[1]+1 if a[1] > 128 else 0) << 4) for a, pix in zip(alpha, image)], dtype=np.uint8)

    f = open(outpath, "wb")
    # write header
    f.write(b"UGAR")
    f.write(np.array([2, len(paletteData)*2, len(imageData)], dtype=np.uint32).tobytes())
    # write palette
    f.write(paletteData.tobytes())
    # write imagedata
    f.write(imageData.tobytes())
    f.close()

if __name__ == "__main__":

    if len(argv) < 3:
      print("Sudomemo NPF converter")
      print("\nUsage:")
      print("\n\timage -> npf:\n \tpython3 npf.py -e input.png output.npf")
      print("\n\tnpf -> image:\n \tpython3 npf.py -d input.npf output.png width height")

    elif argv[1] == "-e":
      encode(argv[2], argv[3])

    elif argv[1] == "-d":
      decode(argv[2], argv[3], argv[4], argv[5])
