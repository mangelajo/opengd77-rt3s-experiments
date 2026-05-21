#!/usr/bin/env python3
#
# opengd77_custom_data.py - backup / restore / clear the OpenGD77 custom-data
# region (themes, boot image, custom beep, satellite TLE) on a running radio.
#
# Talks to the firmware via USB CDC in CPS mode (which is the default). The
# radio must be powered on and connected via USB; no special menu mode needed.
#
# Region layout (from firmware/application/include/functions/codeplug.h):
#   FLASH_ADDRESS_OFFSET = 0x20000  (128 KB into SPI flash)
#   Size                  = 0x10000 (64 KB, 16 sectors of 4 KB)
#   First 8 bytes         = "OpenGD77" signature
#
# Subcommands:
#   backup  --output FILE   read 64 KB from 0x20000, save to FILE
#   restore --input  FILE   write 64 KB from FILE back into the region
#   clear                   invalidate the signature (8 bytes -> 0xFF) so the
#                           firmware's boot-time check re-formats the region
#                           on next boot. Use this to test the auto-recovery.
#
# Requires: pyserial  (pip install pyserial)

import argparse
import glob
import struct
import sys
import time

try:
    import serial
    from serial.tools import list_ports
except ImportError:
    sys.exit("error: pyserial not installed. Run: pip install pyserial")


FLASH_ADDR     = 0x20000          # FLASH_ADDRESS_OFFSET for STM32 platforms
REGION_SIZE    = 0x10000          # 64 KB
SECTOR_SIZE    = 0x1000           # 4 KB
SECTOR_FIRST   = FLASH_ADDR // SECTOR_SIZE          # 32
SECTOR_COUNT   = REGION_SIZE // SECTOR_SIZE         # 16
READ_CHUNK     = 1024             # well under firmware cap of 1533
WRITE_CHUNK    = 1024             # well under firmware cap of 1528

CPS_ACCESS_FLASH = 1

# STM32 USB CDC: ST Microelectronics
STM_VID = 0x0483


# ---------- serial port plumbing ----------

def find_port():
    """Best-effort auto-detect. Return single device path or exit with hint."""
    candidates = []
    for p in list_ports.comports():
        if p.vid == STM_VID:
            candidates.append(p.device)
    if not candidates:
        # Fall back to platform conventions
        candidates = (glob.glob('/dev/cu.usbmodem*')
                      or glob.glob('/dev/ttyACM*')
                      or [])
    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        sys.exit("error: no OpenGD77 serial port found. Pass --port explicitly.")
    sys.exit(f"error: multiple candidate ports found, pick one with --port: {candidates}")


def open_port(path):
    return serial.Serial(path, baudrate=115200, timeout=2.0, write_timeout=2.0)


# ---------- protocol primitives ----------

def _read_exact(ser, n):
    buf = b''
    while len(buf) < n:
        chunk = ser.read(n - len(buf))
        if not chunk:
            raise IOError(f"timeout reading {n - len(buf)} more bytes (got {len(buf)}/{n})")
        buf += chunk
    return buf


def read_flash(ser, address, length):
    """Read `length` bytes from SPI flash starting at `address`."""
    out = bytearray()
    while length > 0:
        n = min(length, READ_CHUNK)
        req = struct.pack('>BBIH', ord('R'), CPS_ACCESS_FLASH, address, n)
        ser.write(req)
        hdr = _read_exact(ser, 1)
        if hdr != b'R':
            raise IOError(f"read failed at 0x{address:06X}: reply byte 0x{hdr[0]:02X}")
        ln = struct.unpack('>H', _read_exact(ser, 2))[0]
        out += _read_exact(ser, ln)
        if ln != n:
            raise IOError(f"short read at 0x{address:06X}: asked {n} got {ln}")
        address += n
        length  -= n
    return bytes(out)


def _expect_ack(ser, expected_first, expected_second=None):
    a = _read_exact(ser, 1)
    if a != expected_first:
        raise IOError(f"write nack: got 0x{a[0]:02X} expected 0x{expected_first[0]:02X}")
    if expected_second is not None:
        b = _read_exact(ser, 1)
        if b[0] != expected_second:
            raise IOError(f"write nack subcmd: got 0x{b[0]:02X} expected 0x{expected_second:02X}")


def write_sector(ser, sector_number, data):
    """Erase + program one 4 KB sector. `data` must be exactly SECTOR_SIZE bytes."""
    assert len(data) == SECTOR_SIZE, f"sector data must be {SECTOR_SIZE} bytes"

    # 1) prepare sector: X | 1 | sector (BE24)
    sb = sector_number.to_bytes(3, 'big')
    ser.write(b'X' + bytes([1]) + sb)
    _expect_ack(ser, b'X', 1)

    # 2) send data in chunks: X | 2 | addr (BE32) | len (BE16) | data
    address = sector_number * SECTOR_SIZE
    offset = 0
    while offset < SECTOR_SIZE:
        n = min(WRITE_CHUNK, SECTOR_SIZE - offset)
        pkt = struct.pack('>BBIH', ord('X'), 2, address + offset, n) + data[offset:offset + n]
        ser.write(pkt)
        _expect_ack(ser, b'X', 2)
        offset += n

    # 3) commit: X | 3
    ser.write(b'X' + bytes([3]))
    _expect_ack(ser, b'X', 3)


# ---------- subcommand handlers ----------

def cmd_backup(ser, args):
    print(f"Reading {REGION_SIZE} bytes from 0x{FLASH_ADDR:06X}...")
    t0 = time.time()
    data = read_flash(ser, FLASH_ADDR, REGION_SIZE)
    dt = time.time() - t0
    with open(args.output, 'wb') as f:
        f.write(data)
    sig = data[:8]
    print(f"  wrote {len(data)} bytes to {args.output} in {dt:.1f}s")
    print(f"  signature bytes: {sig!r}", '(valid)' if sig == b'OpenGD77' else '(MISSING/INVALID)')


def cmd_restore(ser, args):
    data = open(args.input, 'rb').read()
    if len(data) != REGION_SIZE:
        sys.exit(f"error: input file is {len(data)} bytes, expected {REGION_SIZE}")
    print(f"Writing {REGION_SIZE} bytes to 0x{FLASH_ADDR:06X} ({SECTOR_COUNT} sectors)...")
    t0 = time.time()
    for i in range(SECTOR_COUNT):
        sec = SECTOR_FIRST + i
        write_sector(ser, sec, data[i * SECTOR_SIZE:(i + 1) * SECTOR_SIZE])
        print(f"  sector {sec} (0x{sec * SECTOR_SIZE:06X}) ok")
    dt = time.time() - t0
    print(f"  done in {dt:.1f}s")


def cmd_clear(ser, args):
    print(f"Invalidating signature at 0x{FLASH_ADDR:06X}...")
    # Read current first sector, zero the signature, write it back.
    # This preserves the rest of the sector data; the firmware's boot check
    # only inspects the first 8 bytes and will trigger a full reformat anyway
    # on next boot, but reading-modifying-writing avoids surprising the user
    # by trashing more than necessary on the rare path where they re-run this.
    sector = read_flash(ser, FLASH_ADDR, SECTOR_SIZE)
    cleared = bytearray(sector)
    cleared[:8] = b'\xff' * 8
    write_sector(ser, SECTOR_FIRST, bytes(cleared))
    print(f"  signature cleared. Reboot the radio to trigger the auto-format.")


# ---------- main ----------

def main():
    ap = argparse.ArgumentParser(
            description='Backup / restore / clear the OpenGD77 custom-data region (themes, boot image, beep, TLE) on a running radio.',
            formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--port', help='serial port (default: auto-detect)')
    sub = ap.add_subparsers(dest='cmd', required=True)

    sp = sub.add_parser('backup', help='read region to file')
    sp.add_argument('--output', '-o', required=True)
    sp.set_defaults(func=cmd_backup)

    sp = sub.add_parser('restore', help='write region from file')
    sp.add_argument('--input', '-i', required=True)
    sp.set_defaults(func=cmd_restore)

    sp = sub.add_parser('clear', help='invalidate signature (for testing the boot auto-format)')
    sp.set_defaults(func=cmd_clear)

    args = ap.parse_args()
    port = args.port or find_port()
    print(f"Using serial port: {port}")
    with open_port(port) as ser:
        args.func(ser, args)


if __name__ == '__main__':
    main()
