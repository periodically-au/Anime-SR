# Miscellaneous Notes & Todos

Apple Compressor (both old and current versions) have significant issues with reverse telecine on older anime,
because the actual anime is 8 or 12 frames per second, so if there isn't gross cell or background movement,
visible interlace wont happen 2 frames out of 5, but 2 frames out of 10.

JES Deinterlacer seems to work around this issue: https://jeschot.home.xs4all.nl/home.html Also, it seems to generate
output files that are 720x480 or 486 with square pixels, which is what we want to avoid scaling to 640x480 in
Final Cut and Compressor.

- On Input tab, Choose... file to deinterlace, check Top Field first
- On Project tab, select Inverse telecine, check Detect cadence breaks, Output frame rate 23.976
- On Output tab, use Export -> Quicktime Movie and select encoding. Set Size to the specific
size you want, which should match the import size.
- You can also output DPX. It has the same problem as Compressor 4 (see below)

Older version of Compressor (3.5.3) seems to do a better job of Quicktime to DPX conversion than the current Compressor 4.
However, unless you set the output size to match the original input size and pixel aspect ratio (say, 720x486, DV),
it will scale the output DPX images to square pixels (640x486), which is obviously not what you want.

Compressor 4 generates DPX that look weird when viewed in GraphicConverter (as does JES). They have blue bar in the center of the screen and the colors are distorted and clipped. This may be a GraphicConverter issue, but another utility (DJV) also has the same issue.

Old Analog transfers are often going to have edge sharpening artifacts. Need to investigate how to remove these before
upconversion.