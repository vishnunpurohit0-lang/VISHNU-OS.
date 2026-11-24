import struct

def build_2stage_mbr():
    disk = bytearray(16 * 1024 * 1024)

    # === Stage 1: MBR at Sector 0 ===
    # Loads 8 sectors starting at LBA 1 into 0x7E00, then jumps there.
    stage1 = bytearray([
        0xFA,                         # 0x00: cli
        0x31, 0xC0,                   # 0x01: xor ax, ax
        0x8E, 0xD8,                   # 0x03: mov ds, ax
        0x8E, 0xC0,                   # 0x05: mov es, ax
        0x8E, 0xD0,                   # 0x07: mov ss, ax
        0xBC, 0x00, 0x7C,             # 0x09: mov sp, 0x7c00
        0xFB,                         # 0x0C: sti
        0x88, 0x16, 0x80, 0x7C,       # 0x0D: mov [0x7c80], dl  ; save drive
        0xB4, 0x02,                   # 0x11: mov ah, 0x02       ; read sectors
        0xB0, 0x08,                   # 0x13: mov al, 8          ; 8 sectors
        0xB5, 0x00,                   # 0x15: mov ch, 0          ; cylinder 0
        0xB1, 0x02,                   # 0x17: mov cl, 2          ; sector 2 (LBA 1)
        0xB6, 0x00,                   # 0x19: mov dh, 0          ; head 0
        0x8A, 0x16, 0x80, 0x7C,       # 0x1B: mov dl, [0x7c80]  ; drive
        0xBB, 0x00, 0x7E,             # 0x1F: mov bx, 0x7e00    ; dest buffer
        0xCD, 0x13,                   # 0x22: int 0x13           ; BIOS disk read
        0xEA, 0x00, 0x7E, 0x00, 0x00, # 0x24: jmp far 0000:7E00
    ])

    mbr = bytearray(512)
    mbr[0:len(stage1)] = stage1
    mbr[510] = 0x55
    mbr[511] = 0xAA
    disk[0:512] = mbr

    # === Stage 2: Loaded at 0x7E00 ===
    # Layout with CORRECT jump offsets:
    #
    # 0x00: B8 03 00        mov ax, 0x0003       ; 80x25 text mode
    # 0x03: CD 10           int 0x10             ; clear screen
    # 0x05: BE LL HH        mov si, text_addr    ; (patched at 0x06)
    #
    # print_char:  (offset 0x08)
    # 0x08: AC              lodsb
    # 0x09: 84 C0           test al, al
    # 0x0B: 74 09           jz key_loop          ; -> 0x0D+9 = 0x16  ✓
    # 0x0D: B4 0E           mov ah, 0x0E
    # 0x0F: BB 0B 00        mov bx, 0x000B       ; light cyan
    # 0x12: CD 10           int 0x10
    # 0x14: EB F2           jmp print_char       ; -> 0x16+(-14) = 0x08  ✓
    #
    # key_loop:  (offset 0x16)
    # 0x16: 31 E4           xor ah, ah
    # 0x18: CD 16           int 0x16             ; wait for key
    # 0x1A: 3C 0D           cmp al, 0x0D         ; Enter?
    # 0x1C: 75 0F           jne echo_key         ; -> 0x1E+15 = 0x2D  ✓
    #
    # enter_pressed:
    # 0x1E: B8 0D 0E        mov ax, 0x0E0D       ; teletype CR
    # 0x21: CD 10           int 0x10
    # 0x23: B8 0A 0E        mov ax, 0x0E0A       ; teletype LF
    # 0x26: CD 10           int 0x10
    # 0x28: BE LL HH        mov si, prompt_addr  ; (patched at 0x29)
    # 0x2B: EB DB           jmp print_char       ; -> 0x2D+(-37) = 0x08  ✓
    #
    # echo_key:  (offset 0x2D)
    # 0x2D: B4 0E           mov ah, 0x0E
    # 0x2F: CD 10           int 0x10
    # 0x31: EB E3           jmp key_loop         ; -> 0x33+(-29) = 0x16  ✓

    stage2_code = bytearray([
        0xB8, 0x03, 0x00,             # mov ax, 0x0003
        0xCD, 0x10,                   # int 0x10
        0xBE, 0x00, 0x00,             # mov si, text_addr (patch at 0x06)
        # print_char (0x08):
        0xAC,                         # lodsb
        0x84, 0xC0,                   # test al, al
        0x74, 0x09,                   # jz key_loop (0x0D+9=0x16)
        0xB4, 0x0E,                   # mov ah, 0x0e
        0xBB, 0x0B, 0x00,             # mov bx, 0x000b
        0xCD, 0x10,                   # int 0x10
        0xEB, 0xF2,                   # jmp print_char (0x16-14=0x08) ← FIXED
        # key_loop (0x16):
        0x31, 0xE4,                   # xor ah, ah
        0xCD, 0x16,                   # int 0x16
        0x3C, 0x0D,                   # cmp al, 0x0d
        0x75, 0x0F,                   # jne echo_key (0x1E+15=0x2D) ← FIXED
        # enter_pressed:
        0xB8, 0x0D, 0x0E,             # mov ax, 0x0e0d (CR)
        0xCD, 0x10,                   # int 0x10
        0xB8, 0x0A, 0x0E,             # mov ax, 0x0e0a (LF)
        0xCD, 0x10,                   # int 0x10
        0xBE, 0x00, 0x00,             # mov si, prompt_addr (patch at 0x29) ← FIXED
        0xEB, 0xDB,                   # jmp print_char (0x2D-37=0x08) ← FIXED
        # echo_key (0x2D):
        0xB4, 0x0E,                   # mov ah, 0x0e
        0xCD, 0x10,                   # int 0x10
        0xEB, 0xE3,                   # jmp key_loop (0x33-29=0x16) ← FIXED
    ])

    banner = (
        "\r\n"
        "  ===============================================================\r\n"
        "  *      __     ___     _                 ___  ____             *\r\n"
        "  *      \\ \\   / (_)___| |__  _ __  _   _/ _ \\/ ___|            *\r\n"
        "  *       \\ \\ / /| / __| '_ \\| '_ \\| | | | | | \\___ \\           *\r\n"
        "  *        \\ V / | \\__ \\ | | | | | | |_| | |_| |___) |          *\r\n"
        "  *         \\_/  |_|___/_| |_|_| |_|\\__,_|\\___/|____/           *\r\n"
        "  *                                                             *\r\n"
        "  *             V I S H N U   M I C R O - O S                   *\r\n"
        "  *          x86_64 Preemptive Micro-Kernel v0.11.0             *\r\n"
        "  *        Engineered by Vishnu | Safe Bare-Metal Kernel        *\r\n"
        "  ===============================================================\r\n\r\n"
        "  OS: Vishnu OS x86_64        Kernel: Rust no_std v0.11.0\r\n"
        "  Tasks: 2 active             Memory: 512 KiB / 32768 KiB\r\n"
        "  Security: TPM 2.0 + W^X     Mode: VirtualBox Bare-Metal\r\n\r\n"
        "Type help for commands or exit to shutdown.\r\n\r\n"
    )
    prompt = "vishnu@kernel:/# "

    text_bytes = banner.encode('ascii') + prompt.encode('ascii') + b'\x00'

    code_len = len(stage2_code)  # 0x33 = 51 bytes
    text_addr = 0x7E00 + code_len
    prompt_addr = text_addr + len(banner)

    # Patch the two mov si addresses
    struct.pack_into('<H', stage2_code, 0x06, text_addr)
    struct.pack_into('<H', stage2_code, 0x29, prompt_addr)

    stage2_payload = stage2_code + text_bytes
    disk[512:512 + len(stage2_payload)] = stage2_payload

    raw_path = r"C:\Users\MSI\.gemini\antigravity\scratch\vishnu-os\vishnu_direct_boot.raw"
    with open(raw_path, "wb") as f:
        f.write(disk)
    print(f"[+] Stage 2 code: {code_len} bytes")
    print(f"[+] Banner text: {len(banner)} bytes")
    print(f"[+] Text addr: 0x{text_addr:04X}, Prompt addr: 0x{prompt_addr:04X}")
    print(f"[OK] Created {raw_path} ({len(disk)} bytes)")

if __name__ == '__main__':
    build_2stage_mbr()
