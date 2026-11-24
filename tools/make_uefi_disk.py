import struct
import os
import subprocess

def make_fat16_uefi_disk():
    # Disk geometry: 16 MiB total
    SECTOR_SIZE = 512
    TOTAL_SECTORS = 32768 # 16 MiB
    PART_START_LBA = 2048 # 1 MiB offset
    PART_SECTORS = TOTAL_SECTORS - PART_START_LBA # 30720 sectors (15 MiB)

    disk = bytearray(TOTAL_SECTORS * SECTOR_SIZE)

    # 1. MBR Partition Table
    mbr = bytearray(SECTOR_SIZE)
    # Partition 1: Type 0xEF (EFI System Partition), Bootable 0x80
    part_entry = struct.pack(
        '<B3sB3sII',
        0x80,                      # Bootable
        b'\x00\x02\x00',           # Start CHS
        0xEF,                      # Partition Type (EFI System Partition)
        b'\xff\xff\xff',           # End CHS
        PART_START_LBA,            # LBA start
        PART_SECTORS               # LBA length
    )
    mbr[0x1BE:0x1BE + 16] = part_entry
    mbr[510:512] = b'\x55\xAA'
    disk[0:SECTOR_SIZE] = mbr

    # 2. FAT16 Partition inside PART_START_LBA
    # Parameters
    sectors_per_cluster = 4 # 2048 bytes per cluster
    cluster_size = sectors_per_cluster * SECTOR_SIZE
    reserved_sectors = 4
    num_fats = 2
    root_entries = 512
    root_dir_sectors = (root_entries * 32) // SECTOR_SIZE # 32 sectors
    media_byte = 0xF8

    # Calculate sectors per FAT
    # Data sectors = PART_SECTORS - reserved_sectors - root_dir_sectors - (num_fats * spf)
    # Total clusters ~ 30720 / 4 ~ 7680 clusters
    # 7680 clusters * 2 bytes = 15360 bytes ~ 30 sectors per FAT
    sectors_per_fat = 32

    part_offset = PART_START_LBA * SECTOR_SIZE
    fat_part = bytearray(PART_SECTORS * SECTOR_SIZE)

    # Boot Sector (BPB)
    fat_part[0:3] = b'\xEB\x3C\x90'
    fat_part[3:11] = b'MSDOS5.0'
    struct.pack_into('<H', fat_part, 11, SECTOR_SIZE)
    fat_part[13] = sectors_per_cluster
    struct.pack_into('<H', fat_part, 14, reserved_sectors)
    fat_part[16] = num_fats
    struct.pack_into('<H', fat_part, 17, root_entries)
    struct.pack_into('<H', fat_part, 19, 0) # 0 for large volume
    fat_part[21] = media_byte
    struct.pack_into('<H', fat_part, 22, sectors_per_fat)
    struct.pack_into('<H', fat_part, 24, 63) # sectors per track
    struct.pack_into('<H', fat_part, 26, 255) # heads
    struct.pack_into('<I', fat_part, 28, PART_START_LBA) # hidden sectors
    struct.pack_into('<I', fat_part, 32, PART_SECTORS) # total sectors 32-bit
    fat_part[36] = 0x80 # drive number
    fat_part[37] = 0 # reserved
    fat_part[38] = 0x29 # extended boot signature
    struct.pack_into('<I', fat_part, 39, 0x12345678) # volume ID
    fat_part[43:54] = b'VISHNU_OS  '
    fat_part[54:62] = b'FAT16   '
    fat_part[510:512] = b'\x55\xAA'

    # FAT Tables
    fat1_offset = reserved_sectors * SECTOR_SIZE
    fat2_offset = (reserved_sectors + sectors_per_fat) * SECTOR_SIZE
    root_dir_offset = (reserved_sectors + num_fats * sectors_per_fat) * SECTOR_SIZE
    data_offset = root_dir_offset + root_dir_sectors * SECTOR_SIZE

    def set_fat_entry(c, val):
        struct.pack_into('<H', fat_part, fat1_offset + c * 2, val)
        struct.pack_into('<H', fat_part, fat2_offset + c * 2, val)

    # Initial FAT entries
    set_fat_entry(0, 0xFF00 | media_byte)
    set_fat_entry(1, 0xFFFF)

    cur_cluster = 2

    # Load files
    efi_binary_path = r"C:\Users\MSI\.gemini\antigravity\scratch\vishnu-os\usb\EFI\BOOT\BOOTX64.EFI"
    with open(efi_binary_path, "rb") as f:
        bootx64_data = f.read()

    startup_nsh_data = b"\\EFI\\BOOT\\BOOTX64.EFI\r\n"
    vishnu_cfg_data = b"title=Vishnu Micro-OS\r\nkernel=vishnu-kernel\r\n"

    def write_file_clusters(data):
        nonlocal cur_cluster
        start = cur_cluster
        remaining = len(data)
        ptr = 0
        while remaining > 0:
            c = cur_cluster
            cur_cluster += 1
            chunk = min(remaining, cluster_size)
            c_offset = data_offset + (c - 2) * cluster_size
            fat_part[c_offset:c_offset + chunk] = data[ptr:ptr + chunk]
            ptr += chunk
            remaining -= chunk
            if remaining > 0:
                set_fat_entry(c, cur_cluster)
            else:
                set_fat_entry(c, 0xFFFF)
        return start

    def make_entry(name, ext, attr, cluster, size):
        entry = bytearray(32)
        entry[0:8] = name.ljust(8).encode('ascii')
        entry[8:11] = ext.ljust(3).encode('ascii')
        entry[11] = attr
        struct.pack_into('<H', entry, 26, cluster)
        struct.pack_into('<I', entry, 28, size)
        return entry

    # 1. Write startup.nsh in root
    nsh_cluster = write_file_clusters(startup_nsh_data)

    # 2. Allocate clusters for EFI directory and BOOT directory
    efi_dir_cluster = cur_cluster
    cur_cluster += 1
    set_fat_entry(efi_dir_cluster, 0xFFFF)

    boot_dir_cluster = cur_cluster
    cur_cluster += 1
    set_fat_entry(boot_dir_cluster, 0xFFFF)

    # 3. Write files into BOOT directory
    bootx64_cluster = write_file_clusters(bootx64_data)
    cfg_cluster = write_file_clusters(vishnu_cfg_data)

    # Build BOOT directory table
    boot_dir_data = bytearray(cluster_size)
    boot_dir_data[0:32] = make_entry('.', '   ', 0x10, boot_dir_cluster, 0)
    boot_dir_data[32:64] = make_entry('..', '  ', 0x10, efi_dir_cluster, 0)
    boot_dir_data[64:96] = make_entry('BOOTX64 ', 'EFI', 0x20, bootx64_cluster, len(bootx64_data))
    boot_dir_data[96:128] = make_entry('VISHNU  ', 'CFG', 0x20, cfg_cluster, len(vishnu_cfg_data))

    boot_dir_off = data_offset + (boot_dir_cluster - 2) * cluster_size
    fat_part[boot_dir_off:boot_dir_off + cluster_size] = boot_dir_data

    # Build EFI directory table
    efi_dir_data = bytearray(cluster_size)
    efi_dir_data[0:32] = make_entry('.', '   ', 0x10, efi_dir_cluster, 0)
    efi_dir_data[32:64] = make_entry('..', '  ', 0x10, 0, 0)
    efi_dir_data[64:96] = make_entry('BOOT    ', '   ', 0x10, boot_dir_cluster, 0)

    efi_dir_off = data_offset + (efi_dir_cluster - 2) * cluster_size
    fat_part[efi_dir_off:efi_dir_off + cluster_size] = efi_dir_data

    # Build Root directory table
    fat_part[root_dir_offset:root_dir_offset + 32] = make_entry('STARTUP ', 'NSH', 0x20, nsh_cluster, len(startup_nsh_data))
    fat_part[root_dir_offset + 32:root_dir_offset + 64] = make_entry('EFI     ', '   ', 0x10, efi_dir_cluster, 0)

    # Insert partition into disk
    disk[part_offset:part_offset + len(fat_part)] = fat_part

    out_raw = r"C:\Users\MSI\.gemini\antigravity\scratch\vishnu-os\vishnu_boot.raw"
    with open(out_raw, "wb") as f:
        f.write(disk)
    print(f"Created {out_raw} successfully ({len(disk)} bytes)")

if __name__ == '__main__':
    make_fat16_uefi_disk()
