#!/usr/bin/python

# NBF image converter script for Sudomemo
# github.com/Sudomemo | www.sudomemo.net
#
# Written by James Daniel
# github.com/jaames | rakujira.jp
#
# Based on PBSDS' NBF script
# https://gist.github.com/pbsds/9c1c0fc417f49f7ef21d
# github.com/pbsds | pbsds.net
#
# Format documentation can be found on the Flipnote-Collective wiki:
# https://github.com/Flipnote-Collective/flipnote-studio-docs/wiki/.nbf-image-format

import sys, numpy as np
from PIL import Image

def decode(input, output):
    f = open(input, "rb").read()
    # Read the palette data length from the header
    paletteLength = np.fromstring(f[8:12], dtype=np.uint32)[0]
    # Read the image length from the header
    imageLength = np.fromstring(f[12:16], dtype=np.uint32)[0]
    # Check the image size
    if imageLength <> 256*192:
        print "Image must be 256 by 192 pixels"
        return
    # Get the palette data
    paletteData = np.fromstring(f[16:16+paletteLength], dtype="<u2")
    # Get the image data
    imageData = np.fromstring(f[16+paletteLength:16+paletteLength+imageLength], dtype=np.uint8)
    # Set up the palette
    palette = np.zeros(256, dtype=">u4")
    # Convert the palette from ARGB555
    for i in xrange(paletteLength/2):
		r = (paletteData[i]       & 0x1f)
		g = (paletteData[i] >> 5  & 0x1f)
		b = (paletteData[i] >> 10 & 0x1f)
		r = r<<3 | (r>>2)
		g = g<<3 | (g>>2)
		b = b<<3 | (b>>2)
		palette[i] = (r<<24) | (g<<16) | (b<<8) | 0xFF
    # Prepare the image data
    image = np.zeros(256*192, dtype=">u4")
    # Write the image + save it
    image[:] = palette[imageData]
    outputFile = image.tostring("C")
    outputFile = Image.fromstring("RGBA", (256, 192), outputFile)
    outputFile.save(output, output[output.rfind(".")+1:])

def encode(input, output):
    # Open the image
    image = Image.open(input)
    # Convert the image to a paletted format with 256 colors
    image = image.convert("P", palette=Image.ADAPTIVE, colors=256)
    # Get image palette
    palette = image.getpalette()
    # Get the image data (which is an array of palette indecies)
    imageData = np.array(image.getdata(), dtype=np.uint8)
    # Prepare for the pallete data
    paletteData = np.zeros(256, dtype="<u2")
    # Convert the pallete colors to ARGB1555
    for i in xrange(256):
        paletteData[i] = (((palette[i*3] >> 3) | ((palette[(i*3)+1] & 0xF8) << 2) | (palette[(i*3)+2] & 0xF8) << 7) | 0x0000)
    # Open the output file
    f = open(output, "wb")
    # Write the header
    f.write("UGAR\2\0\0\0")
    # Write the length table
    f.write(np.array((512, 256*192), dtype=np.uint32).tostring())
    # Write the palette data
    f.write(paletteData.tostring())
    # Write the image data
    f.write(imageData.tostring())
    # Close
    f.close()

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "-d":
        decode(sys.argv[2], sys.argv[3])
    elif len(sys.argv) > 1 and sys.argv[1] == "-e":
        encode(sys.argv[2], sys.argv[3])
    else:
        print "Usage:\n\tnbf.py <-d/-e> <input> <output>\n\t"
