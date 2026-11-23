#!/usr/bin/env python3
"""
Vishnu OS — Bootable UEFI ISO Image Generator

Builds an ISO 9660 image with an embedded FAT EFI System Partition
so the ISO can boot on any UEFI PC (or in QEMU with OVMF).

Usage:
    python tools/build_iso.py          # outputs vishnu-os.iso
    python tools/build_iso.py -o out.iso
"""

import argparse
import hashlib
import os
import struct
import sys
import time
import datetime

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SECTOR = 512
ISO_SECTOR = 2048
FAT_SECTORS = 2880           # 1.44 MB FAT image (standard floppy size)
FAT_BYTES = FAT_SECTORS * SECTOR

# ---------------------------------------------------------------------------
# FAT12 image builder (minimal EFI System Partition)
# ---------------------------------------------------------------------------

def build_fat_image(files: dict[str, bytes]) -> bytes:
    """Return a FAT12 floppy-sized image containing *files*.

    *files* maps paths like 'EFI/BOOT/BOOTX64.EFI' to raw bytes.
    Only one level of nesting under root directories is supported, which
    is all we need for the standard EFI boot path.
    """
    img = bytearray(FAT_BYTES)

    # --- BPB / Boot Sector ---------------------------------------------------
    bytes_per_sector = 512
    sectors_per_cluster = 1
    reserved_sectors = 1
    num_fats = 2
    root_entry_count = 224
    total_sectors = FAT_SECTORS
    media_type = 0xF0
    sectors_per_fat = 9
    sectors_per_track = 18
    num_heads = 2

    # Jump + OEM
    img[0:3] = b'\xEB\x3C\x90'
    img[3:11] = b'VISHNUOS'
    struct.pack_into('<H', img, 11, bytes_per_sector)
    img[13] = sectors_per_cluster
    struct.pack_into('<H', img, 14, reserved_sectors)
    img[16] = num_fats
    struct.pack_into('<H', img, 17, root_entry_count)
    struct.pack_into('<H', img, 19, total_sectors)
    img[21] = media_type
    struct.pack_into('<H', img, 22, sectors_per_fat)
    struct.pack_into('<H', img, 24, sectors_per_track)
    struct.pack_into('<H', img, 26, num_heads)
    # Extended BPB
    img[38] = 0x29  # extended boot sig
    struct.pack_into('<I', img, 39, 0x56495348)  # volume serial 'VISH'
    img[43:54] = b'VISHNU OS  '
    img[54:62] = b'FAT12   '
    # Boot signature
    img[510] = 0x55
    img[511] = 0xAA

    # --- FAT tables -----------------------------------------------------------
    fat_start = reserved_sectors * bytes_per_sector
    fat_size = sectors_per_fat * bytes_per_sector

    # Initialise both FAT copies with media byte
    for f in range(num_fats):
        off = fat_start + f * fat_size
        img[off] = media_type
        img[off + 1] = 0xFF
        img[off + 2] = 0xFF

    # --- Root directory -------------------------------------------------------
    root_dir_start = fat_start + num_fats * fat_size
    root_dir_size = root_entry_count * 32

    # --- Data area ------------------------------------------------------------
    data_start = root_dir_start + root_dir_size
    next_cluster = 2  # first usable cluster

    def set_fat12(cluster, value):
        """Write a 12-bit FAT entry."""
        for f in range(num_fats):
            base = fat_start + f * fat_size
            byte_off = base + (cluster * 3) // 2
            if cluster % 2 == 0:
                img[byte_off] = value & 0xFF
                img[byte_off + 1] = (img[byte_off + 1] & 0xF0) | ((value >> 8) & 0x0F)
            else:
                img[byte_off] = (img[byte_off] & 0x0F) | ((value & 0x0F) << 4)
                img[byte_off + 1] = (value >> 4) & 0xFF

    def cluster_offset(c):
        return data_start + (c - 2) * bytes_per_sector * sectors_per_cluster

    def write_data(data: bytes) -> int:
        """Write *data* into consecutive clusters, returns first cluster."""
        nonlocal next_cluster
        first = next_cluster
        remaining = data
        prev = None
        while remaining:
            chunk = remaining[:bytes_per_sector * sectors_per_cluster]
            remaining = remaining[len(chunk):]
            off = cluster_offset(next_cluster)
            img[off:off + len(chunk)] = chunk
            if prev is not None:
                set_fat12(prev, next_cluster)
            prev = next_cluster
            next_cluster += 1
        set_fat12(prev, 0xFFF)  # end-of-chain
        return first

    def make_dir_entry(name_8_3: bytes, attr: int, cluster: int, size: int) -> bytes:
        entry = bytearray(32)
        entry[0:11] = name_8_3
        entry[11] = attr
        # Create time/date (use a fixed timestamp)
        struct.pack_into('<H', entry, 14, 0x8000)  # create time
        struct.pack_into('<H', entry, 16, 0x5B17)  # create date
        struct.pack_into('<H', entry, 18, 0x5B17)  # access date
        struct.pack_into('<H', entry, 20, 0)        # high cluster (FAT12 = 0)
        struct.pack_into('<H', entry, 22, 0x8000)  # write time
        struct.pack_into('<H', entry, 24, 0x5B17)  # write date
        struct.pack_into('<H', entry, 26, cluster & 0xFFFF)
        struct.pack_into('<I', entry, 28, size)
        return bytes(entry)

    def to_8_3(name: str) -> bytes:
        """Convert a filename to 8.3 format, padded with spaces."""
        name = name.upper()
        if '.' in name:
            base, ext = name.rsplit('.', 1)
        else:
            base, ext = name, ''
        return (base.ljust(8) + ext.ljust(3)).encode('ascii')[:11]

    # Organise files by directory
    root_entries_data = bytearray()
    # Volume label entry
    root_entries_data += make_dir_entry(b'VISHNU OS  ', 0x08, 0, 0)

    dirs: dict[str, list[tuple[str, bytes]]] = {}
    root_files: list[tuple[str, bytes]] = []

    for path, content in files.items():
        parts = path.replace('\\', '/').split('/')
        if len(parts) == 1:
            root_files.append((parts[0], content))
        else:
            d = parts[0]
            fname = '/'.join(parts[1:])
            dirs.setdefault(d, []).append((fname, content))

    # Write root-level files
    for fname, content in root_files:
        clust = write_data(content)
        root_entries_data += make_dir_entry(to_8_3(fname), 0x20, clust, len(content))

    # Write directories
    for dirname, dir_files in dirs.items():
        # Allocate a cluster for this directory's entries
        dir_cluster = next_cluster
        next_cluster += 1
        set_fat12(dir_cluster, 0xFFF)

        dir_entry_data = bytearray()
        # . and .. entries
        dir_entry_data += make_dir_entry(b'.          ', 0x10, dir_cluster, 0)
        dir_entry_data += make_dir_entry(b'..         ', 0x10, 0, 0)

        # Subdirectories within this directory
        subdirs: dict[str, list[tuple[str, bytes]]] = {}
        direct_files: list[tuple[str, bytes]] = []

        for fpath, content in dir_files:
            subparts = fpath.split('/')
            if len(subparts) == 1:
                direct_files.append((subparts[0], content))
            else:
                sd = subparts[0]
                subdirs.setdefault(sd, []).append(('/'.join(subparts[1:]), content))

        # Write direct files in this subdirectory
        for fname, content in direct_files:
            clust = write_data(content)
            dir_entry_data += make_dir_entry(to_8_3(fname), 0x20, clust, len(content))

        # Write sub-subdirectories
        for sdname, sd_files in subdirs.items():
            sd_cluster = next_cluster
            next_cluster += 1
            set_fat12(sd_cluster, 0xFFF)

            sd_entry_data = bytearray()
            sd_entry_data += make_dir_entry(b'.          ', 0x10, sd_cluster, 0)
            sd_entry_data += make_dir_entry(b'..         ', 0x10, dir_cluster, 0)

            for sf_name, sf_content in sd_files:
                sc = write_data(sf_content)
                sd_entry_data += make_dir_entry(to_8_3(sf_name), 0x20, sc, len(sf_content))

            # Write subdirectory entries into its cluster
            sd_off = cluster_offset(sd_cluster)
            img[sd_off:sd_off + len(sd_entry_data)] = sd_entry_data

            dir_entry_data += make_dir_entry(to_8_3(sdname), 0x10, sd_cluster, 0)

        # Write directory entries into its cluster
        d_off = cluster_offset(dir_cluster)
        img[d_off:d_off + len(dir_entry_data)] = dir_entry_data

        # Add directory to root
        root_entries_data += make_dir_entry(to_8_3(dirname), 0x10, dir_cluster, 0)

    # Write root directory entries
    img[root_dir_start:root_dir_start + len(root_entries_data)] = root_entries_data

    return bytes(img)


# ---------------------------------------------------------------------------
# ISO 9660 + El Torito builder
# ---------------------------------------------------------------------------

def pad_to(data: bytearray, size: int) -> bytearray:
    if len(data) < size:
        data.extend(b'\x00' * (size - len(data)))
    return data


def iso_str_a(s: str, length: int) -> bytes:
    """ISO 9660 A-characters (uppercase, digits, underscore), space-padded."""
    return s.upper().ljust(length)[:length].encode('ascii')


def iso_str_d(s: str, length: int) -> bytes:
    """ISO 9660 D-characters, space-padded."""
    return s.upper().ljust(length)[:length].encode('ascii')


def iso_date_time() -> bytes:
    """17-byte ISO 9660 date/time for 'now'."""
    now = datetime.datetime.now()
    s = now.strftime('%Y%m%d%H%M%S') + '00'
    return s.encode('ascii') + b'\x00'


def both_endian_32(val: int) -> bytes:
    """LSB then MSB (8 bytes)."""
    return struct.pack('<I', val) + struct.pack('>I', val)


def both_endian_16(val: int) -> bytes:
    """LSB then MSB (4 bytes)."""
    return struct.pack('<H', val) + struct.pack('>H', val)


def make_directory_record(name: bytes, lba: int, size: int, is_dir: bool) -> bytes:
    """Build a single ISO 9660 directory record."""
    name_len = len(name)
    rec_len = 33 + name_len
    if rec_len % 2:
        rec_len += 1

    rec = bytearray(rec_len)
    rec[0] = rec_len
    rec[1] = 0  # extended attribute length
    rec[2:10] = both_endian_32(lba)
    rec[10:18] = both_endian_32(size)
    # Recording date (7 bytes) — simplified
    now = datetime.datetime.now()
    rec[18] = now.year - 1900
    rec[19] = now.month
    rec[20] = now.day
    rec[21] = now.hour
    rec[22] = now.minute
    rec[23] = now.second
    rec[24] = 0  # GMT offset
    rec[25] = 0x02 if is_dir else 0x00  # file flags
    rec[26] = 0  # interleave unit size
    rec[27] = 0  # interleave gap size
    rec[28:32] = both_endian_16(1)  # volume sequence number
    rec[32] = name_len
    rec[33:33 + name_len] = name
    return bytes(rec)


def build_iso(fat_image: bytes, extra_files: dict[str, bytes], output_path: str):
    """Build a bootable ISO 9660 image with an El Torito UEFI boot catalog."""

    iso = bytearray()

    # --- System Area (sectors 0-15) — 32 KiB of zeros -------------------------
    iso.extend(b'\x00' * (16 * ISO_SECTOR))

    # We will lay out the ISO as:
    #   Sector 16: Primary Volume Descriptor
    #   Sector 17: Boot Record (El Torito)
    #   Sector 18: Volume Descriptor Set Terminator
    #   Sector 19: El Torito Boot Catalog
    #   Sector 20: Root directory record
    #   Sector 21+: EFI boot image (the FAT)
    #   After FAT: extra files

    root_dir_lba = 20
    efi_image_lba = 21
    efi_image_sectors = (len(fat_image) + ISO_SECTOR - 1) // ISO_SECTOR
    boot_catalog_lba = 19

    # Place extra files after the FAT image
    file_lbas = {}
    next_lba = efi_image_lba + efi_image_sectors
    for fname, content in extra_files.items():
        file_lbas[fname] = (next_lba, len(content))
        sectors_needed = (len(content) + ISO_SECTOR - 1) // ISO_SECTOR
        next_lba += max(sectors_needed, 1)

    total_sectors = next_lba

    # --- Sector 16: Primary Volume Descriptor ---------------------------------
    pvd = bytearray(ISO_SECTOR)
    pvd[0] = 1  # type: Primary
    pvd[1:6] = b'CD001'
    pvd[6] = 1  # version
    pvd[8:40] = iso_str_a('VISHNU_OS', 32)       # system identifier
    pvd[40:72] = iso_str_d('VISHNU_MICRO_OS', 32) # volume identifier
    pvd[80:88] = both_endian_32(total_sectors)     # volume space size
    pvd[120:124] = both_endian_16(1)              # volume set size
    pvd[124:128] = both_endian_16(1)              # volume sequence number
    pvd[128:132] = both_endian_16(ISO_SECTOR)     # logical block size

    # Path table (minimal — just root)
    # Path table: 1 byte name len + 1 byte ext attr + 4 byte LBA + 2 byte parent
    path_table_l = struct.pack('<BBIH', 1, 0, root_dir_lba, 1) + b'\x00\x00'
    path_table_m = struct.pack('>BBIH', 1, 0, root_dir_lba, 1) + b'\x00\x00'
    # We'll put path tables right after everything else but for simplicity
    # just embed size as 10 and store them inline in the PVD
    pvd[132:140] = both_endian_32(len(path_table_l))

    # For simplicity, skip real path table sectors — point to sector 0 (unused)
    # This is enough for UEFI boot; full ISO filesystem browsing may not work
    # on all OS explorers but the boot path is valid.
    struct.pack_into('<I', pvd, 140, 0)  # L path table location
    struct.pack_into('<I', pvd, 144, 0)  # optional L path table
    struct.pack_into('>I', pvd, 148, 0)  # M path table location
    struct.pack_into('>I', pvd, 152, 0)  # optional M path table

    # Root directory record (34 bytes) at offset 156
    root_record = make_directory_record(b'\x00', root_dir_lba, ISO_SECTOR, True)
    pvd[156:156 + len(root_record)] = root_record

    pvd[190:318] = iso_str_d('VISHNU OS', 128)    # volume set identifier
    pvd[318:446] = iso_str_a('VISHNU', 128)        # publisher
    pvd[446:574] = iso_str_a('', 128)              # data preparer
    pvd[574:702] = iso_str_a('VISHNU OS ISO BUILDER', 128) # application

    pvd[813:830] = iso_date_time()  # volume creation
    pvd[830:847] = iso_date_time()  # volume modification
    pvd[847:864] = b'0000000000000000\x00'  # expiration (none)
    pvd[864:881] = iso_date_time()  # effective date
    pvd[881] = 1  # file structure version

    iso.extend(pvd)

    # --- Sector 17: El Torito Boot Record Volume Descriptor --------------------
    brvd = bytearray(ISO_SECTOR)
    brvd[0] = 0  # type: Boot Record
    brvd[1:6] = b'CD001'
    brvd[6] = 1
    brvd[7:39] = b'EL TORITO SPECIFICATION'.ljust(32, b'\x00')
    struct.pack_into('<I', brvd, 71, boot_catalog_lba)  # boot catalog LBA
    iso.extend(brvd)

    # --- Sector 18: Volume Descriptor Set Terminator ---------------------------
    vdst = bytearray(ISO_SECTOR)
    vdst[0] = 255  # type: terminator
    vdst[1:6] = b'CD001'
    vdst[6] = 1
    iso.extend(vdst)

    # --- Sector 19: El Torito Boot Catalog ------------------------------------
    catalog = bytearray(ISO_SECTOR)

    # Validation entry (32 bytes)
    validation = bytearray(32)
    validation[0] = 1   # header ID
    validation[1] = 0xEF  # platform: EFI
    validation[2:4] = b'\x00\x00'  # reserved
    validation[4:28] = b'Vishnu OS EFI Boot'.ljust(24, b'\x00')
    # Checksum: sum of all 16-bit words in this entry must be 0
    validation[28:30] = b'\x00\x00'  # checksum placeholder
    validation[30] = 0x55
    validation[31] = 0xAA
    # Calculate checksum
    total = 0
    for i in range(0, 32, 2):
        total += struct.unpack_from('<H', validation, i)[0]
    checksum = (0x10000 - (total & 0xFFFF)) & 0xFFFF
    struct.pack_into('<H', validation, 28, checksum)
    catalog[0:32] = validation

    # Initial/Default Entry — EFI boot image (32 bytes)
    initial = bytearray(32)
    initial[0] = 0x88  # bootable
    initial[1] = 0xEF  # EFI media type
    struct.pack_into('<H', initial, 2, 0)  # load segment
    initial[4] = 0     # system type
    initial[5] = 0     # unused
    # Sector count (in 512-byte virtual sectors)
    efi_virt_sectors = (len(fat_image) + 511) // 512
    struct.pack_into('<H', initial, 6, efi_virt_sectors if efi_virt_sectors < 65535 else 0)
    struct.pack_into('<I', initial, 8, efi_image_lba)
    catalog[32:64] = initial

    iso.extend(catalog)

    # --- Sector 20: Root Directory --------------------------------------------
    root_dir = bytearray(ISO_SECTOR)
    offset = 0

    # '.' (self)
    dot = make_directory_record(b'\x00', root_dir_lba, ISO_SECTOR, True)
    root_dir[offset:offset + len(dot)] = dot
    offset += len(dot)

    # '..' (parent = self for root)
    dotdot = make_directory_record(b'\x01', root_dir_lba, ISO_SECTOR, True)
    root_dir[offset:offset + len(dotdot)] = dotdot
    offset += len(dotdot)

    # EFI.IMG entry (the FAT image — not normally visible, but useful)
    efi_rec = make_directory_record(b'EFI.IMG;1', efi_image_lba, len(fat_image), False)
    root_dir[offset:offset + len(efi_rec)] = efi_rec
    offset += len(efi_rec)

    # Boot catalog
    cat_rec = make_directory_record(b'BOOT.CAT;1', boot_catalog_lba, ISO_SECTOR, False)
    root_dir[offset:offset + len(cat_rec)] = cat_rec
    offset += len(cat_rec)

    # Extra files
    for fname, (lba, size) in file_lbas.items():
        iso_name = fname.upper().replace('.', '_DOT_') + ';1'
        if len(iso_name) > 30:
            iso_name = iso_name[:30] + ';1'
        frec = make_directory_record(iso_name.encode('ascii'), lba, size, False)
        if offset + len(frec) < ISO_SECTOR:
            root_dir[offset:offset + len(frec)] = frec
            offset += len(frec)

    iso.extend(root_dir)

    # --- Sector 21+: EFI Boot Image (FAT) ------------------------------------
    fat_padded = bytearray(fat_image)
    pad_to(fat_padded, efi_image_sectors * ISO_SECTOR)
    iso.extend(fat_padded)

    # --- Extra files -----------------------------------------------------------
    for fname, content in extra_files.items():
        lba, size = file_lbas[fname]
        file_data = bytearray(content)
        sectors_needed = max((len(content) + ISO_SECTOR - 1) // ISO_SECTOR, 1)
        pad_to(file_data, sectors_needed * ISO_SECTOR)
        iso.extend(file_data)

    # Pad to final size
    pad_to(iso, total_sectors * ISO_SECTOR)

    # Write to disk
    with open(output_path, 'wb') as f:
        f.write(iso)

    return len(iso)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description='Build a bootable Vishnu OS ISO image')
    parser.add_argument('-o', '--output', default=None,
                        help='Output ISO path (default: vishnu-os.iso in project root)')
    args = parser.parse_args()

    # Find project root (one level up from tools/)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)

    if args.output:
        iso_path = args.output
    else:
        iso_path = os.path.join(project_root, 'vishnu-os.iso')

    usb_dir = os.path.join(project_root, 'usb')

    # 1. Read the UEFI boot files
    boot_efi_path = os.path.join(usb_dir, 'EFI', 'BOOT', 'BOOTX64.EFI')
    vishnu_cfg_path = os.path.join(usb_dir, 'EFI', 'BOOT', 'vishnu.cfg')

    if not os.path.exists(boot_efi_path):
        print(f"[!] BOOTX64.EFI not found at {boot_efi_path}")
        print("    Run 'python tools/build_uefi_binary.py' first.")
        sys.exit(1)

    with open(boot_efi_path, 'rb') as f:
        boot_efi = f.read()
    vishnu_cfg = b''
    if os.path.exists(vishnu_cfg_path):
        with open(vishnu_cfg_path, 'rb') as f:
            vishnu_cfg = f.read()

    print("[*] Building Vishnu OS Bootable ISO Image...")
    print(f"    BOOTX64.EFI : {len(boot_efi):,} bytes")
    if vishnu_cfg:
        print(f"    vishnu.cfg   : {len(vishnu_cfg):,} bytes")

    # 2. Build the FAT EFI System Partition image
    fat_files = {'EFI/BOOT/BOOTX64.EFI': boot_efi}
    if vishnu_cfg:
        fat_files['EFI/BOOT/VISHNU.CFG'] = vishnu_cfg

    print("[*] Creating FAT12 EFI System Partition (1.44 MB)...")
    fat_img = build_fat_image(fat_files)

    # 3. Extra files to include on the ISO root
    sha_path = os.path.join(usb_dir, 'SHA256.txt')
    extra = {}
    if os.path.exists(sha_path):
        with open(sha_path, 'rb') as f:
            extra['SHA256.TXT'] = f.read()

    # README as plain text on the ISO
    readme_path = os.path.join(project_root, 'README.md')
    if os.path.exists(readme_path):
        with open(readme_path, 'rb') as f:
            extra['README.TXT'] = f.read()

    # 4. Build the ISO
    print("[*] Assembling ISO 9660 image with El Torito UEFI boot record...")
    iso_size = build_iso(fat_img, extra, iso_path)

    # 5. Compute checksum
    with open(iso_path, 'rb') as f:
        sha = hashlib.sha256(f.read()).hexdigest()

    print()
    print(f"[✓] Bootable ISO generated successfully!")
    print(f"    Path   : {iso_path}")
    print(f"    Size   : {iso_size:,} bytes ({iso_size / 1024 / 1024:.2f} MB)")
    print(f"    SHA-256: {sha}")
    print()
    print("    Boot in QEMU:")
    print(f'      qemu-system-x86_64 -bios OVMF.fd -cdrom "{iso_path}"')
    print()
    print("    Or burn to USB/DVD and boot on a UEFI PC.")


if __name__ == '__main__':
    main()
