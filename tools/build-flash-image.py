#!/usr/bin/env python3
"""
Build a flash image containing MicroPython *and* our firmware, for headless simulation.

The problem this solves: Wokwi's CLI simulates a flash image, and the MicroPython download is
only the interpreter. On real hardware you copy your .py files over USB afterwards; a headless
simulator has no "afterwards". So the files have to already be in the image.

MicroPython's ESP32 partition table stops after `factory`, and the comment in its own
partitions-4MiBplus.csv says the rest of the flash is the user filesystem — so the filesystem
starts at 0x200000 and runs to the end of a 4 MB flash. This writes a littlefs image of our
firmware there and concatenates the two.

    python3 tools/build-flash-image.py

The littlefs parameters are the ones MicroPython's ESP32 port uses. If they are wrong the
simulated board boots to a bare REPL with no main.py, which is the symptom to look for.
"""

import sys
from pathlib import Path

from littlefs import LittleFS

REPO = Path(__file__).resolve().parent.parent
FIRMWARE = REPO / "firmware" / "micropython"
SIM = FIRMWARE / "sim"

MICROPYTHON_IMAGE = SIM / "micropython-c6.bin"
OUTPUT_IMAGE = SIM / "flash-with-firmware.bin"

FLASH_SIZE = 4 * 1024 * 1024        # the XIAO ESP32-C6 has 4 MB
FILESYSTEM_OFFSET = 0x200000        # where MicroPython looks, per partitions-4MiBplus.csv
BLOCK_SIZE = 4096

# MicroPython's own littlefs2 settings, read from its source rather than guessed:
#   extmod/vfs_lfs.c   readsize / progsize / lookahead all default to 32
#   extmod/vfs_lfsx.c  cache_size = min(block_size, 4 * max(read, prog)) = 128, block_cycles = 100
# These must match or the board mounts nothing, boots to a bare REPL, and never runs main.py.
LITTLEFS_SETTINGS = dict(
    block_size=BLOCK_SIZE,
    read_size=32,
    prog_size=32,
    cache_size=4 * 32,
    lookahead_size=32,
    block_cycles=100,
    disk_version=0x00020000,        # littlefs 2.0, which MicroPython writes
)

# What goes on the simulated board: the package, its configuration, and the two boot files.
def files_to_include():
    yield from sorted((FIRMWARE / "smartbin").glob("*.py"))
    yield FIRMWARE / "config.py"
    yield FIRMWARE / "main.py"
    yield FIRMWARE / "boot.py"


def build_filesystem() -> bytes:
    block_count = (FLASH_SIZE - FILESYSTEM_OFFSET) // BLOCK_SIZE
    filesystem = LittleFS(block_count=block_count, **LITTLEFS_SETTINGS)
    filesystem.mkdir("/smartbin")

    total = 0
    for source in files_to_include():
        destination = (
            f"/smartbin/{source.name}" if source.parent.name == "smartbin" else f"/{source.name}"
        )
        content = source.read_bytes()
        with filesystem.open(destination, "wb") as handle:
            handle.write(content)
        total += len(content)
        print(f"  {destination:<28} {len(content):>6} bytes")

    print(f"  {'':<28} {total:>6} bytes in {block_count} blocks of {BLOCK_SIZE}")
    return filesystem.context.buffer


def main() -> int:
    if not MICROPYTHON_IMAGE.exists():
        print(f"missing {MICROPYTHON_IMAGE}")
        print("download a build from https://micropython.org/download/ESP32_GENERIC_C6/")
        return 1

    print("firmware files:")
    filesystem = build_filesystem()

    interpreter = MICROPYTHON_IMAGE.read_bytes()
    if len(interpreter) > FILESYSTEM_OFFSET:
        print(f"the MicroPython image is larger than {FILESYSTEM_OFFSET:#x}; it would be overwritten")
        return 1

    image = bytearray(b"\xff" * FLASH_SIZE)
    image[: len(interpreter)] = interpreter
    image[FILESYSTEM_OFFSET : FILESYSTEM_OFFSET + len(filesystem)] = filesystem
    OUTPUT_IMAGE.write_bytes(image)

    print(
        f"\nwrote {OUTPUT_IMAGE.relative_to(REPO)}: "
        f"{len(image) // 1024} KB "
        f"(MicroPython to {len(interpreter):#x}, filesystem at {FILESYSTEM_OFFSET:#x})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
