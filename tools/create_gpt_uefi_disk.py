import struct
import zlib
import uuid
import os

def create_gpt_uefi_disk():
    SECTOR_SIZE = 512
    TOTAL_SECTORS = 65536 # 32 MiB
    PART_START_LBA = 2048 # 1 MiB offset
    PART_SECTORS = TOTAL_SECTORS - PART_START_LBA - 34 # ~31 MiB
    PART_END_LBA = PART_START_LBA + PART_SECTORS - 1

    disk = bytearray(TOTAL_SECTORS * SECTOR_SIZE)

    # 1. Protective MBR (LBA 0)
    mbr = bytearray(SECTOR_SIZE)
    # Entry 1 at 0x1BE
    mbr[0x1BE] = 0x00 # Non-bootable
    mbr[0x1BF:0x1C2] = b'\x00\x02\x00' # Start CHS
    mbr[0x1C2] = 0xEE # GPT Protective Type
    mbr[0x1C3:0x1C6] = b'\xff\xff\xff' # End CHS
    struct.pack_into('<I', mbr, 0x1C6, 1) # Start LBA
    struct.pack_into('<I', mbr, 0x1CA, TOTAL_SECTORS - 1) # Sector count
    mbr[510:512] = b'\x55\xAA'
    disk[0:SECTOR_SIZE] = mbr

    # 2. GPT Partition Entries (LBA 2-33, 128 entries of 128 bytes = 16384 bytes)
    part_entries = bytearray(128 * 128)
    
    # Entry 0: EFI System Partition
    # Type GUID: C12A7328-F81F-11D2-BA4B-00A0C93EC93B
    esp_type_guid = uuid.UUID('C12A7328-F81F-11D2-BA4B-00A0C93EC93B').bytes_le
    part_unique_guid = uuid.uuid4().bytes_le
    part_name = "EFI System Partition".encode('utf-16le').ljust(72, b'\x00')

    entry0 = bytearray(128)
    entry0[0:16] = esp_type_guid
    entry0[16:32] = part_unique_guid
    struct.pack_into('<Q', entry0, 32, PART_START_LBA)
    struct.pack_into('<Q', entry0, 40, PART_END_LBA)
    struct.pack_into('<Q', entry0, 48, 0) # Attributes
    entry0[56:128] = part_name
    part_entries[0:128] = entry0

    part_entries_crc = zlib.crc32(part_entries) & 0xFFFFFFFF

    # 3. Primary GPT Header (LBA 1)
    disk_guid = uuid.uuid4().bytes_le
    hdr = bytearray(92)
    hdr[0:8] = b'EFI PART'
    struct.pack_into('<I', hdr, 8, 0x00010000) # Revision 1.0
    struct.pack_into('<I', hdr, 12, 92) # Header size
    struct.pack_into('<I', hdr, 16, 0) # CRC placeholder
    struct.pack_into('<I', hdr, 20, 0) # Reserved
    struct.pack_into('<Q', hdr, 24, 1) # MyLBA
    struct.pack_into('<Q', hdr, 32, TOTAL_SECTORS - 1) # AlternateLBA
    struct.pack_into('<Q', hdr, 40, 34) # FirstUsableLBA
    struct.pack_into('<Q', hdr, 48, TOTAL_SECTORS - 34) # LastUsableLBA
    hdr[56:72] = disk_guid
    struct.pack_into('<Q', hdr, 72, 2) # PartitionEntryLBA
    struct.pack_into('<I', hdr, 80, 128) # NumberOfPartitionEntries
    struct.pack_into('<I', hdr, 84, 128) # SizeOfPartitionEntry
    struct.pack_into('<I', hdr, 88, part_entries_crc)

    hdr_crc = zlib.crc32(hdr) & 0xFFFFFFFF
    struct.pack_into('<I', hdr, 16, hdr_crc)

    disk[SECTOR_SIZE:2 * SECTOR_SIZE] = hdr.ljust(SECTOR_SIZE, b'\x00')
    disk[2 * SECTOR_SIZE:34 * SECTOR_SIZE] = part_entries

    # Backup GPT at end of disk
    # Backup entries at TOTAL_SECTORS - 33
    disk[(TOTAL_SECTORS - 33) * SECTOR_SIZE:(TOTAL_SECTORS - 1) * SECTOR_SIZE] = part_entries
    # Backup header at TOTAL_SECTORS - 1
    bhdr = bytearray(hdr)
    struct.pack_into('<Q', bhdr, 24, TOTAL_SECTORS - 1) # MyLBA
    struct.pack_into('<Q', bhdr, 32, 1) # AlternateLBA
    struct.pack_into('<Q', bhdr, 72, TOTAL_SECTORS - 33) # PartitionEntryLBA
    struct.pack_into('<I', bhdr, 16, 0)
    bhdr_crc = zlib.crc32(bhdr) & 0xFFFFFFFF
    struct.pack_into('<I', bhdr, 16, bhdr_crc)
    disk[(TOTAL_SECTORS - 1) * SECTOR_SIZE:TOTAL_SECTORS * SECTOR_SIZE] = bhdr.ljust(SECTOR_SIZE, b'\x00')

    # 4. Format FAT16 inside Partition (LBA 2048 to PART_END_LBA)
    # Partition length: PART_SECTORS sectors (each 512 bytes)
    # Using FAT16 with 4 sectors per cluster (2048 bytes)
    # Total clusters ~ 63454 / 4 ~ 15860 clusters (perfect FAT16 range 4085 - 65524)
    sectors_per_cluster = 4
    cluster_size = sectors_per_cluster * SECTOR_SIZE
    reserved_sectors = 4
    num_fats = 2
    root_entries = 512
    root_dir_sectors = (root_entries * 32) // SECTOR_SIZE # 32 sectors
    sectors_per_fat = 64
    media_byte = 0xF8

    fat_part = bytearray(PART_SECTORS * SECTOR_SIZE)

    # Boot Sector (BPB)
    fat_part[0:3] = b'\xEB\x3C\x90'
    fat_part[3:11] = b'MSDOS5.0'
    struct.pack_into('<H', fat_part, 11, SECTOR_SIZE)
    fat_part[13] = sectors_per_cluster
    struct.pack_into('<H', fat_part, 14, reserved_sectors)
    fat_part[16] = num_fats
    struct.pack_into('<H', fat_part, 17, root_entries)
    struct.pack_into('<H', fat_part, 19, PART_SECTORS) # BPB_TotSec16
    fat_part[21] = media_byte
    struct.pack_into('<H', fat_part, 22, sectors_per_fat)
    struct.pack_into('<H', fat_part, 24, 63) # SecPerTrack
    struct.pack_into('<H', fat_part, 26, 16) # Heads
    struct.pack_into('<I', fat_part, 28, PART_START_LBA) # HiddSec
    struct.pack_into('<I', fat_part, 32, 0) # TotSec32 = 0 because TotSec16 is non-zero!
    fat_part[36] = 0x80 # DriveNum
    fat_part[37] = 0
    fat_part[38] = 0x29 # BootSig
    struct.pack_into('<I', fat_part, 39, 0x56495348) # VolID ('VISH')
    fat_part[43:54] = b'VISHNU_OS  '
    fat_part[54:62] = b'FAT16   '
    fat_part[510:512] = b'\x55\xAA'

    # Offsets inside partition
    fat1_offset = reserved_sectors * SECTOR_SIZE
    fat2_offset = (reserved_sectors + sectors_per_fat) * SECTOR_SIZE
    root_dir_offset = (reserved_sectors + num_fats * sectors_per_fat) * SECTOR_SIZE
    data_offset = root_dir_offset + root_dir_sectors * SECTOR_SIZE

    def set_fat(c, val):
        struct.pack_into('<H', fat_part, fat1_offset + c * 2, val)
        struct.pack_into('<H', fat_part, fat2_offset + c * 2, val)

    # Init FAT
    set_fat(0, 0xFF00 | media_byte)
    set_fat(1, 0xFFFF)

    cur_cluster = 2

    # Load file contents
    efi_bin = r"C:\Users\MSI\.gemini\antigravity\scratch\vishnu-os\usb\EFI\BOOT\BOOTX64.EFI"
    with open(efi_bin, "rb") as f:
        bootx64_bytes = f.read()

    startup_nsh_bytes = b"\\EFI\\BOOT\\BOOTX64.EFI\r\n"
    vishnu_cfg_bytes = b"title=Vishnu Micro-OS\r\nkernel=vishnu-kernel\r\n"

    def write_data(data):
        nonlocal cur_cluster
        start_c = cur_cluster
        remaining = len(data)
        p = 0
        while remaining > 0:
            c = cur_cluster
            cur_cluster += 1
            chunk = min(remaining, cluster_size)
            off = data_offset + (c - 2) * cluster_size
            fat_part[off:off + chunk] = data[p:p + chunk]
            p += chunk
            remaining -= chunk
            if remaining > 0:
                set_fat(c, cur_cluster)
            else:
                set_fat(c, 0xFFFF)
        return start_c

    def dir_entry(name_8, ext_3, attr, cluster, file_size):
        e = bytearray(32)
        e[0:8] = name_8.ljust(8).encode('ascii')[:8]
        e[8:11] = ext_3.ljust(3).encode('ascii')[:3]
        e[11] = attr
        # Date: 2026-11-23 -> (2026 - 1980) << 9 | 11 << 5 | 23 = 46 << 9 | 352 | 23 = 23552 + 352 + 23 = 23927 = 0x5D77
        struct.pack_into('<H', e, 16, 0x5D77)
        struct.pack_into('<H', e, 18, 0x5D77)
        struct.pack_into('<H', e, 24, 0x5D77)
        struct.pack_into('<H', e, 26, cluster)
        struct.pack_into('<I', e, 28, file_size)
        return e

    # 1. Root files
    nsh_cluster = write_data(startup_nsh_bytes)

    # 2. Directory clusters
    efi_dir_cluster = cur_cluster
    cur_cluster += 1
    set_fat(efi_dir_cluster, 0xFFFF)

    boot_dir_cluster = cur_cluster
    cur_cluster += 1
    set_fat(boot_dir_cluster, 0xFFFF)

    # 3. Files in BOOT directory
    bootx64_cluster = write_data(bootx64_bytes)
    cfg_cluster = write_data(vishnu_cfg_bytes)

    # Build BOOT directory
    boot_table = bytearray(cluster_size)
    boot_table[0:32] = dir_entry('.', '   ', 0x10, boot_dir_cluster, 0)
    boot_table[32:64] = dir_entry('..', '  ', 0x10, efi_dir_cluster, 0)
    boot_table[64:96] = dir_entry('BOOTX64', 'EFI', 0x20, bootx64_cluster, len(bootx64_bytes))
    boot_table[96:128] = dir_entry('VISHNU', 'CFG', 0x20, cfg_cluster, len(vishnu_cfg_bytes))
    off = data_offset + (boot_dir_cluster - 2) * cluster_size
    fat_part[off:off + cluster_size] = boot_table

    # Build EFI directory
    efi_table = bytearray(cluster_size)
    efi_table[0:32] = dir_entry('.', '   ', 0x10, efi_dir_cluster, 0)
    efi_table[32:64] = dir_entry('..', '  ', 0x10, 0, 0)
    efi_table[64:96] = dir_entry('BOOT', '   ', 0x10, boot_dir_cluster, 0)
    off = data_offset + (efi_dir_cluster - 2) * cluster_size
    fat_part[off:off + cluster_size] = efi_table

    # Build Root directory
    fat_part[root_dir_offset:root_dir_offset + 32] = dir_entry('STARTUP', 'NSH', 0x20, nsh_cluster, len(startup_nsh_bytes))
    fat_part[root_dir_offset + 32:root_dir_offset + 64] = dir_entry('EFI', '   ', 0x10, efi_dir_cluster, 0)

    # Place partition into disk
    disk[PART_START_LBA * SECTOR_SIZE:(PART_START_LBA + PART_SECTORS) * SECTOR_SIZE] = fat_part

    raw_path = r"C:\Users\MSI\.gemini\antigravity\scratch\vishnu-os\vishnu_gpt.raw"
    with open(raw_path, "wb") as f:
        f.write(disk)
    print(f"Created GPT disk {raw_path} ({len(disk)} bytes)")

if __name__ == '__main__':
    create_gpt_uefi_disk()
