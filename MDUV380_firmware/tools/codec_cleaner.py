#!/usr/bin/env python3
#
# codec_cleaner.py - portable re-implementation of the codec_cleaner build tool.
#
# This replaces the prebuilt x86_64-Linux-only `codec_cleaner.Linux` ELF (and the
# Windows `codec_cleaner.exe`) so the firmware build runs natively on any host with
# Python 3 - no podman container required.
#
# The original tool, reverse-engineered from tools/codec_cleaner.Linux, does exactly
# two things:
#
#   -C                     Create the codec placeholder file `codec_bin_section_1.bin`
#                          in the current directory: CODEC_REGION_SIZE bytes of 0xFF.
#
#   -i in.bin -o out.bin   Copy in.bin to out.bin, overwriting the codec region
#                          [CODEC_REGION_OFFSET, +CODEC_REGION_SIZE) with 0xFF
#                          ("erased flash") - i.e. strip any proprietary AMBE codec
#                          before distribution.
#
# Behaviour and console messages are kept faithful to the original.

import sys

# --- firmware constants ------------------------------------------------------
# Offset of the codec blob within the raw firmware .bin:
#   CODEC_LOCATION_1 (0x807537C) - app flash base (0x800C000) = 0x6937C
# (see application/include/dmr_codec/codec.h and STM32F405VGTX_FLASH.ld)
CODEC_REGION_OFFSET = 0x6937C
# Size of the .codec_bin_section_1 blob (297904 bytes).
CODEC_REGION_SIZE = 0x48BB0
FILL = 0xFF
PLACEHOLDER_NAME = "codec_bin_section_1.bin"

USAGE = """Usage: codec_cleaner [OPTION]
Options:
         -i <inputfile.bin>   : clear the codec regions of the <inputfile.bin>.
         -o <outfile.bin>     : write to resulting cleaned inputfile (see -i) to <outfile.bin>.
         -C                   : create dummy codec region files.
"""


def create_placeholder():
    print(" - Creating file %s" % PLACEHOLDER_NAME)
    with open(PLACEHOLDER_NAME, "wb") as f:
        f.write(bytes([FILL]) * CODEC_REGION_SIZE)
    print("File '%s' created" % PLACEHOLDER_NAME)


def clean(input_file, output_file):
    print("Input file: '%s'" % input_file)
    print("Output file: '%s'" % output_file)

    try:
        with open(input_file, "rb") as f:
            data = bytearray(f.read())
    except OSError as e:
        print("ERROR: cannot read '%s': %s" % (input_file, e.strerror))
        return 1

    region_end = CODEC_REGION_OFFSET + CODEC_REGION_SIZE
    if len(data) < region_end:
        print("ERROR: '%s' is too small (%d bytes, codec region ends at %d)"
              % (input_file, len(data), region_end))
        return 1

    data[CODEC_REGION_OFFSET:region_end] = bytes([FILL]) * CODEC_REGION_SIZE

    try:
        with open(output_file, "wb") as f:
            f.write(data)
    except OSError as e:
        print("ERROR: cannot write '%s': %s" % (output_file, e.strerror))
        return 1

    print("File '%s' created" % output_file)
    return 0


def main(argv):
    import getopt

    try:
        opts, _ = getopt.getopt(argv[1:], "Ci:o:h")
    except getopt.GetoptError as e:
        print(str(e))
        print(USAGE)
        return 1

    create = False
    input_file = None
    output_file = None

    for opt, arg in opts:
        if opt == "-h":
            print(USAGE)
            return 0
        elif opt == "-C":
            create = True
        elif opt == "-i":
            input_file = arg
        elif opt == "-o":
            output_file = arg

    if create:
        create_placeholder()
        return 0

    if input_file is None and output_file is None:
        print(USAGE)
        return 1
    if input_file is None:
        print("ERROR: inputfile is not specified")
        return 1
    if output_file is None:
        print("ERROR: outputfile is not specified")
        return 1

    return clean(input_file, output_file)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
