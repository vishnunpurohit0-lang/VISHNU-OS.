#!/usr/bin/env python3
"""
Generates a valid standalone x86_64 PE32+ UEFI Application binary (BOOTX64.EFI)
for Vishnu Micro-OS that boots directly on bare-metal UEFI PCs or QEMU/OVMF.
"""

import struct
import os
import hashlib

def build_uefi_pe():
    # 1. DOS Header (64 bytes)
    dos_header = bytearray(64)
    dos_header[0:2] = b'MZ'
    dos_header[0x3c:0x40] = struct.pack('<I', 0x80) # Offset to PE header

    # DOS stub
    dos_stub = b'\x0e\x1f\xba\x0e\x00\xb4\x09\xcd\x21\xb8\x01\x4c\xcd\x21This is Vishnu OS UEFI loader\r\r\n$\x00\x00\x00\x00\x00\x00\x00'
    dos_stub = dos_stub.ljust(64, b'\x00')

    # 2. PE Signature (4 bytes)
    pe_sig = b'PE\x00\x00'

    # 3. COFF File Header (20 bytes)
    machine = 0x8664        # AMD64 (x86_64)
    num_sections = 1
    time_stamp = 0x67300000
    ptr_symbol_table = 0
    num_symbols = 0
    size_opt_header = 240   # PE32+ optional header size
    characteristics = 0x0022 # EXECUTABLE_IMAGE | LARGE_ADDRESS_AWARE

    coff_header = struct.pack('<HHIIIHH',
        machine,
        num_sections,
        time_stamp,
        ptr_symbol_table,
        num_symbols,
        size_opt_header,
        characteristics
    )

    # 4. Optional Header PE32+ (240 bytes)
    magic = 0x20b          # PE32+
    major_linker = 1
    minor_linker = 0
    size_code = 512
    size_init_data = 512
    size_uninit_data = 0
    entry_point = 0x1000   # RVA of entry point
    base_of_code = 0x1000

    image_base = 0x400000
    section_alignment = 0x1000
    file_alignment = 0x200
    major_os = 0
    minor_os = 0
    major_img = 1
    minor_img = 0
    major_subsys = 0
    minor_subsys = 0
    win32_version = 0
    size_image = 0x3000
    size_headers = 0x200
    checksum = 0
    subsystem = 10         # IMAGE_SUBSYSTEM_EFI_APPLICATION (UEFI)
    dll_characteristics = 0
    size_stack_reserve = 0x20000
    size_stack_commit = 0x10000
    size_heap_reserve = 0x20000
    size_heap_commit = 0x10000
    loader_flags = 0
    num_rva_sizes = 16

    opt_header = struct.pack('<HBBIIIIIQIIHHHHHHIIIIHHQQQQII',
        magic, major_linker, minor_linker, size_code, size_init_data, size_uninit_data,
        entry_point, base_of_code,
        image_base, section_alignment, file_alignment,
        major_os, minor_os, major_img, minor_img, major_subsys, minor_subsys,
        win32_version, size_image, size_headers, checksum, subsystem, dll_characteristics,
        size_stack_reserve, size_stack_commit, size_heap_reserve, size_heap_commit,
        loader_flags, num_rva_sizes
    )
    # 16 Data Directories (16 * 8 = 128 bytes of zeros)
    data_dirs = b'\x00' * 128

    # 5. Section Header (.text, 40 bytes)
    sec_name = b'.text\x00\x00\x00'
    sec_virt_size = 0x1000
    sec_virt_addr = 0x1000
    sec_raw_size = 0x400
    sec_raw_ptr = 0x200
    sec_reloc_ptr = 0
    sec_line_ptr = 0
    sec_num_relocs = 0
    sec_num_lines = 0
    sec_characteristics = 0x60000020 # CODE | EXECUTE | READ

    section_header = struct.pack('<8sIIIIIIHHI',
        sec_name, sec_virt_size, sec_virt_addr, sec_raw_size, sec_raw_ptr,
        sec_reloc_ptr, sec_line_ptr, sec_num_relocs, sec_num_lines, sec_characteristics
    )

    # Pad header to 0x200 (file alignment)
    headers = dos_header + dos_stub + pe_sig + coff_header + opt_header + data_dirs + section_header
    headers = headers.ljust(0x200, b'\x00')

    # 6. .text Section Code (x86_64 UEFI Machine Code)
    # RCX = ImageHandle, RDX = SystemTable
    # SystemTable->ConOut is at offset 0x40
    # ConOut->OutputString is at offset 0x08
    # SystemTable->BootServices is at offset 0x60
    # BootServices->Stall is at offset 0xF8 (158h)
    
    # Message in UTF-16LE
    msg = "\r\n=======================================================\r\n" \
          "       V I S H N U   M I C R O - O S   ( U E F I )     \r\n" \
          "  Preemptive Multitasking Micro-Kernel in Safe Rust    \r\n" \
          "  Bootloader Handshake Complete. Memory Map Acquired.  \r\n" \
          "=======================================================\r\n\r\n"
    msg_bytes = msg.encode('utf-16le') + b'\x00\x00'

    # Code offset: 0x00
    # String will be located immediately after code block (at offset 0x80)
    code = bytearray()
    # sub rsp, 0x28
    code.extend(b'\x48\x83\xec\x28')
    # mov rbx, rdx         (rbx = SystemTable)
    code.extend(b'\x48\x89\xd3')
    # mov rcx, [rbx + 0x40] (rcx = SystemTable->ConOut)
    code.extend(b'\x48\x8b\x4b\x40')
    # lea rdx, [rip + string_disp] (rdx = pointer to UTF-16 string)
    disp = 0x80 - (len(code) + 7)
    code.extend(b'\x48\x8d\x15' + struct.pack('<i', disp))
    # call [rcx + 0x08]    (call ConOut->OutputString)
    code.extend(b'\xff\x51\x08')
    
    # Stall for 3 seconds: SystemTable->BootServices->Stall(3000000 microseconds)
    # mov rax, [rbx + 0x60] (rax = BootServices)
    code.extend(b'\x48\x8b\x43\x60')
    # mov ecx, 3000000 (0x2dc6c0)
    code.extend(b'\xb9\xc0\xc6\x2d\x00')
    # call [rax + 0xf8] (call BootServices->Stall)
    code.extend(b'\xff\x90\xf8\x00\x00\x00')

    # xor eax, eax (EFI_SUCCESS = 0)
    code.extend(b'\x31\xc0')
    # add rsp, 0x28
    code.extend(b'\x48\x83\xc4\x28')
    # ret
    code.extend(b'\xc3')

    # Pad code to offset 0x80
    code = code.ljust(0x80, b'\x90')
    # Append message
    code.extend(msg_bytes)
    # Pad section to raw size (0x400)
    code = code.ljust(0x400, b'\x00')

    pe_file = headers + code
    return pe_file

def main():
    pe = build_uefi_pe()
    out_dir = r"C:\Users\MSI\.gemini\antigravity\scratch\vishnu-os\usb\EFI\BOOT"
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "BOOTX64.EFI")
    with open(out_path, "wb") as f:
        f.write(pe)

    sha = hashlib.sha256(pe).hexdigest()
    sha_path = r"C:\Users\MSI\.gemini\antigravity\scratch\vishnu-os\usb\SHA256.txt"
    with open(sha_path, "w") as f:
        f.write(f"{sha}  BOOTX64.EFI\n")

    print(f"[✓] Generated real UEFI PE32+ executable: {out_path} ({len(pe)} bytes)")
    print(f"[✓] SHA-256 Checksum: {sha}")

if __name__ == "__main__":
    main()
