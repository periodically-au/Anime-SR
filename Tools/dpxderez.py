"""
python3 dpxderez.py {source directory} {destination directory}

Converts 1920x1080 HD DPX down to 720x480 and then back again

Based on:

https://gist.github.com/jackdoerner/1c9c48956a1e00a29dbc

Read Metadata and Image data from 10-bit DPX files in Python 3

Copyright (c) 2016 Jack Doerner

Tweaked to also work in Python 2 (fixed normalization code to ensure floating
point division) -- RJW 08/19/17

Hacked to brute-force copy the header information -- RJW 09/04/17

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
"""

import struct
import numpy as np
from skimage import transform as tf
import os
import sys

VERBOSE = False

test_filename = "test.dpx"

# Cache of DPX header information that we set when we read a file;
# used to write a file in the same format.

dpx_header = None
dpx_endian = None
dpx_meta = None
dpx_offset = -1

orientations = {
	0: "Left to Right, Top to Bottom",
	1: "Right to Left, Top to Bottom",
	2: "Left to Right, Bottom to Top",
	3: "Right to Left, Bottom to Top",
	4: "Top to Bottom, Left to Right",
	5: "Top to Bottom, Right to Left",
	6: "Bottom to Top, Left to Right",
	7: "Bottom to Top, Right to Left"
}

descriptors = {
	1: "Red",
	2: "Green",
	3: "Blue",
	4: "Alpha",
	6: "Luma (Y)",
	7: "Color Difference",
	8: "Depth (Z)",
	9: "Composite Video",
	50: "RGB",
	51: "RGBA",
	52: "ABGR",
	100: "Cb, Y, Cr, Y (4:2:2)",
	102: "Cb, Y, Cr (4:4:4)",
	103: "Cb, Y, Cr, A (4:4:4:4)"
}

packings = {
	0: "Packed into 32-bit words",
	1: "Filled to 32-bit words, Padding First",
	2: "Filled to 32-bit words, Padding Last"
}

encodings = {
	0: "No encoding",
	1: "Run Length Encoding"
}

transfers = {
	1: "Printing Density",
	2: "Linear",
	3: "Logarithmic",
	4: "Unspecified Video",
	5: "SMPTE 274M",
	6: "ITU-R 709-4",
	7: "ITU-R 601-5 system B or G",
	8: "ITU-R 601-5 system M",
	9: "Composite Video (NTSC)",
	10: "Composite Video (PAL)",
	11: "Z (Linear Depth)",
	12: "Z (Homogenous Depth)"
}

colorimetries = {
	1: "Printing Density",
	4: "Unspecified Video",
	5: "SMPTE 274M",
	6: "ITU-R 709-4",
	7: "ITU-R 601-5 system B or G",
	8: "ITU-R 601-5 system M",
	9: "Composite Video (NTSC)",
	10: "Composite Video (PAL)"
}

# (field name, offset, length, type)

propertymap = [

	# Generic Header

    ('magic', 0, 4, 'magic'),
    ('offset', 4, 4, 'I'),
    ('dpx_version', 8, 8, 'utf8'),
    ('file_size', 16, 4, 'I'),
    ('ditto', 20, 4, 'I'),
	('generic_size', 24, 4, 'I'),
	('industry_size', 28, 4, 'I'),
	('user_size', 32, 4, 'I'),
    ('filename', 36, 100, 'utf8'),
    ('timestamp', 136, 24, 'utf8'),
    ('creator', 160, 100, 'utf8'),
    ('project_name', 260, 200, 'utf8'),
    ('copyright', 460, 200, 'utf8'),
    ('encryption_key', 660, 4, 'I'),
	('generic_reserved', 664, 104, 's'),

	# Image Header

    ('orientation', 768, 2, 'H'),
    ('image_element_count', 770, 2, 'H'),
    ('width', 772, 4, 'I'),
    ('height', 776, 4, 'I'),

	# Only first image element  decoded

    ('data_sign', 780, 4, 'I'),
	('low_data', 784, 4, 'I'),
	('low_quantity', 788, 4, 'f'),
	('high_data', 792, 4, 'I'),
	('high_quantity', 796, 4, 'f'),
    ('descriptor', 800, 1, 'B'),
    ('transfer_characteristic', 801, 1, 'B'),
    ('colorimetry', 802, 1, 'B'),
    ('depth', 803, 1, 'B'),
    ('packing', 804, 2, 'H'),
    ('encoding', 806, 2, 'H'),
    ('line_padding', 812, 4, 'I'),
    ('image_padding', 816, 4, 'I'),
    ('image_element_description', 820, 32, 'utf8'),
	('image_reserved', 852, 556, 's'),

	# Orientation header

	('x_offset', 1408, 4, 'I'),
	('y_offset', 1412, 4, 'I'),
	('x_center', 1416, 4, 'f'),
	('y_center', 1420, 4, 'f'),
	('x_originalsize', 1424, 4, 'I'),
	('y_originalsize', 1428, 4, 'I'),
	('source_filename', 1432, 100, 'utf8'),
	('source_timestamp', 1532, 24, 'utf8'),
    ('input_device_name', 1556, 32, 'utf8'),
    ('input_device_sn', 1588, 32, 'utf8'),
	('border_xl', 1620, 2, 'H'),
	('border_xr', 1622, 2, 'H'),
	('border_yt', 1624, 2, 'H'),
	('border_yb', 1626, 2, 'H'),
	('aspect_h', 1628, 4, 'I'),
	('aspect_v', 1632, 4, 'I'),
	('orientation_reserved', 1636, 28, 's'),

	# Film industry info

	('film_industry_header', 1664, 256, 's'),

	# Television industry info

	('timecode', 1920, 4, 'I'),
	('user_bits', 1924, 4, 'I'),
	('interlace', 1928, 1, 'B'),
	('field_number', 1929, 1, 'B'),
	('video_signal', 1930, 1, 'B'),
	('tv_padding', 1931, 1, 'B'),
	('h_sample_rate', 1932, 4, 'f'),
	('v_sample_rate', 1936, 4, 'f'),
	('frame_rate', 1940, 4, 'f'),
	('time_offset', 1944, 4, 'f'),
    ('gamma', 1948, 4, 'f'),
    ('black_level', 1952, 4, 'f'),
    ('black_gain', 1956, 4, 'f'),
    ('break_point', 1960, 4, 'f'),
    ('white_level', 1964, 4, 'f'),
	('integration_times', 1968, 4, 'f'),
	('tv_reserved', 1972, 76, 's')

]

def readDPXMetaData(f):

	global dpx_header
	global dpx_endian
	global dpx_offset
	global dpx_meta

	f.seek(0)
	bytes = f.read(4)
	magic = bytes.decode(encoding='UTF-8')
	if magic != "SDPX" and magic != "XPDS":
		return None
	endianness = ">" if magic == "SDPX" else "<"

	meta = {}

	for p in propertymap:
		f.seek(p[1])
		bytes = f.read(p[2])
		if p[0] in meta:
			print('Duplicate map field',p[0])
		if p[3] == 'magic':
			meta[p[0]] = bytes.decode(encoding='UTF-8')
			meta['endianness'] = "be" if magic == "SDPX" else "le"
		elif p[3] == 'utf8':
			meta[p[0]] = bytes.decode(encoding='UTF-8')
		elif p[3] == 'B':
			meta[p[0]] = struct.unpack(endianness + 'B', bytes)[0]
		elif p[3] == 'H':
			meta[p[0]] = struct.unpack(endianness + 'H', bytes)[0]
		elif p[3] == 'I':
			meta[p[0]] = struct.unpack(endianness + 'I', bytes)[0]
		elif p[3] == 'f':
			meta[p[0]] = struct.unpack(endianness + 'f', bytes)[0]
		elif p[3] == 's':
			meta[p[0]] = struct.unpack(endianness + str(p[2]) + 's', bytes)[0]

	# Save header values

	dpx_endian = endianness
	dpx_offset = meta['offset']
	f.seek(0)
	dpx_header = f.read(dpx_offset)
	dpx_meta = meta

	return meta

def readDPXImageData(f, meta):
	if meta['depth'] != 10 or meta['packing'] != 1 or meta['encoding'] != 0 or meta['descriptor'] != 50:
		return None

	width = meta['width']
	height = meta['height']
	image = np.empty((height, width, 3), dtype=float)

	f.seek(meta['offset'])
	raw = np.fromfile(f, dtype=np.dtype(np.int32), count=width*height, sep="")
	raw = raw.reshape((height,width))

	if meta['endianness'] == 'be':
		raw = raw.byteswap()

	# extract and normalize color channel values to 0..1 inclusive.

	image[:,:,0] = ((raw >> 22) & 0x000003FF) / 1023.0
	image[:,:,1] = ((raw >> 12) & 0x000003FF) / 1023.0
	image[:,:,2] = ((raw >> 2) & 0x000003FF) / 1023.0

	return image

# Assumes a file has already been read, so dpx_header has been initialized

def writeDPX(f, image):

	global dpx_header
	global dpx_endian
	global dpx_offset

	f.seek(0)
	f.write(dpx_header)

	raw = ((((image[:,:,0] * 1023.0).astype(np.dtype(np.int32)) & 0x000003FF) << 22)
			| (((image[:,:,1] * 1023.0).astype(np.dtype(np.int32)) & 0x000003FF) << 12)
			| (((image[:,:,2] * 1023.0).astype(np.dtype(np.int32)) & 0x000003FF) << 2)
		)

	if dpx_endian == 'be':
		raw = raw.byteswap()

	f.seek(dpx_offset)
	raw.tofile(f, sep="")

if __name__ == "__main__":
	fromdir = sys.argv[1]
	todir = sys.argv[2]

	fnames = []
	for (dirpath, dirnames, filenames) in os.walk(fromdir):
		fnames.extend(filenames)
		break

	# print(fnames)

	ONCEONLY = True

	for filename in fnames:
		if not os.path.exists(todir + "/" + filename):
			print("Processing: " + fromdir + "/" + filename)
			with open(fromdir + "/" + filename, "rb") as f:
				meta = readDPXMetaData(f)
				if meta is None:
					print("Invalid File")
				else:
					import binascii
					if VERBOSE or ONCEONLY:
						ONCEONLY = False
						print("\nFILE INFORMATION HEADER")

						print("Endianness:","Big Endian" if meta['endianness'] == ">" else "Little Endian")
						print("Image Offset (Bytes):",meta['offset'])
						print("DPX Version:",meta['dpx_version'])
						print("File Size (Bytes):",meta['file_size'])
						print("Ditto Flag:","New Frame" if meta['ditto'] else "Same as Previous Frame")
						print("Image Filename:",meta['filename'])
						print("Creation Timestamp:",meta['timestamp'])
						print("Creator:",meta['creator'])
						print("Project Name:",meta['project_name'])
						print("Copyright:",meta['copyright'])
						print("Encryption Key:","Unencrypted" if meta['encryption_key'] == 0xFFFFFFFF else binascii.hexlify(bin(meta['encryption_key'])))


						print("\nIMAGE INFORMATION HEADER")
						print("Orientation:", orientations[meta['orientation']] if meta['orientation'] in orientations else "unknown")
						print("Image Element Count:", meta['image_element_count'])
						print("Width:", meta['width'])
						print("Height:", meta['height'])

						print("\nIMAGE ELEMENT 1")
						print("Data Sign:", "signed" if meta['data_sign'] == 1 else "unsigned")
						print("Descriptor:", descriptors[meta['descriptor']] if meta['descriptor'] in descriptors else "unknown")
						print("Transfer:",transfers[meta['transfer_characteristic']] if meta['transfer_characteristic'] in transfers else "unknown")
						print("Colorimetry:",colorimetries[meta['colorimetry']] if meta['colorimetry'] in colorimetries else "unknown")
						print("Bit Depth:",meta['depth'])
						print("Packing:",packings[meta['packing']] if meta['packing'] in packings else "unknown")
						print("Encoding:",encodings[meta['encoding']] if meta['encoding'] in encodings else "unknown")
						print("End of Line Padding:",meta['line_padding'])
						print("End of Image Padding:",meta['image_padding'])
						print("Image Element Description:",meta['image_element_description'])

						print("\nIMAGE SOURCE INFORMATION HEADER")
						print("Input Device Name:",meta['input_device_name'])
						print("Input Device Serial Number:",meta['input_device_sn'])

						print("\n")

					image = readDPXImageData(f, meta)

					if image is None:
						print("DPX Type not Implemented")
					else:

						# image is 1920x1080. Scale down to 960x480 (which is 720x480 with
						# the black edge bars still attached)

						downrez = tf.resize(image, (480, 960, 3), order=1, mode='constant')

						if VERBOSE:
							from matplotlib import pyplot as plt
							lt.imshow(downrez, interpolation='nearest')
							plt.show()

						# Scale up again, back to 1920x1080, simulating the upresolution process

						uprez = tf.resize(downrez, (1080, 1920, 3), order=1, mode='constant')

						# write file

						with open(todir + "/" + filename, "wb") as o:
							writeDPX(o,uprez)
