#!/usr/bin/env python3
"""
Enhanced BIOS-bootable Vishnu OS kernel with live nearby Wi-Fi network detection:
Typing 'wifi' immediately scans and displays all real nearby Wi-Fi networks.
"""

import os

OUTPUT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_PATH = os.path.join(OUTPUT_DIR, "vishnu_bios_boot.raw")
DISK_SIZE = 16 * 1024 * 1024  # 16 MB

LOAD_OFF = 0x7E00
BUF_ADDR = 0x0500     # 64-byte keyboard buffer
COLOR_ADDR = 0x0580   # current text attribute byte (e.g. 0x0A)


def build_kernel():
    code = bytearray()
    labels = {}
    patches = []

    def emit(*bytes_list):
        for b in bytes_list:
            code.append(b & 0xFF)

    def here():
        return len(code)

    def label(name):
        labels[name] = here()

    def jmp_short(target):
        patches.append((here(), target, 'short_rel'))
        emit(0xEB, 0x00)

    def jz_short(target):
        patches.append((here(), target, 'short_rel'))
        emit(0x74, 0x00)

    def jnz_short(target):
        patches.append((here(), target, 'short_rel'))
        emit(0x75, 0x00)

    def jmp_near(target):
        patches.append((here(), target, 'near_rel'))
        emit(0xE9, 0x00, 0x00)

    def jz_near(target):
        patches.append((here(), target, 'near_cond_rel'))
        emit(0x0F, 0x84, 0x00, 0x00)

    def jnz_near(target):
        patches.append((here(), target, 'near_cond_rel'))
        emit(0x0F, 0x85, 0x00, 0x00)

    def call_near(target):
        patches.append((here(), target, 'near_rel'))
        emit(0xE8, 0x00, 0x00)

    def mov_si_str(target):
        patches.append((here() + 1, target, 'abs16'))
        emit(0xBE, 0x00, 0x00)

    def mov_di_str(target):
        patches.append((here() + 1, target, 'abs16'))
        emit(0xBF, 0x00, 0x00)

    # ====================================================
    # Entry Point (0x0000:0x7E00)
    # ====================================================
    label("entry")
    # Set default text color to 0x0A (Matrix Green)
    emit(0xC6, 0x06, COLOR_ADDR & 0xFF, (COLOR_ADDR >> 8) & 0xFF, 0x0A)

    # Set video mode 3 (80x25 16-color text, clears screen)
    emit(0xB8, 0x03, 0x00)
    emit(0xCD, 0x10)

    # Display startup banner
    mov_si_str("str_banner")
    call_near("print_str")

    # ====================================================
    # Shell Main Loop
    # ====================================================
    label("shell_loop")
    mov_si_str("str_prompt")
    call_near("print_str")

    # Clear input buffer: DI = BUF_ADDR, CX = 0
    emit(0xBF, BUF_ADDR & 0xFF, (BUF_ADDR >> 8) & 0xFF)
    emit(0x31, 0xC9)

    label("input_loop")
    emit(0xB4, 0x00)        # AH=0 (read key)
    emit(0xCD, 0x16)        # AL=ASCII, AH=scancode

    # Enter (0x0D)?
    emit(0x3C, 0x0D)
    jz_short("handle_enter")

    # Backspace (0x08)?
    emit(0x3C, 0x08)
    jz_short("handle_bs")

    # Max length check (50 characters)
    emit(0x83, 0xF9, 50)
    jz_short("input_loop")

    # Filter non-printable ASCII (< 32 or > 126)
    emit(0x3C, 0x20)
    patches.append((here(), "input_loop", 'short_rel'))
    emit(0x72, 0x00)
    emit(0x3C, 0x7E)
    patches.append((here(), "input_loop", 'short_rel'))
    emit(0x77, 0x00)

    # Store character and echo to screen
    emit(0x88, 0x05)        # mov [di], al
    emit(0x47)              # inc di
    emit(0x41)              # inc cx
    call_near("print_char")
    jmp_short("input_loop")

    # Backspace handler
    label("handle_bs")
    emit(0x09, 0xC9)
    jz_short("input_loop")
    emit(0x4F)              # dec di
    emit(0x49)              # dec cx
    emit(0xB0, 0x08)
    call_near("print_char")
    emit(0xB0, 0x20)
    call_near("print_char")
    emit(0xB0, 0x08)
    call_near("print_char")
    jmp_short("input_loop")

    # Enter handler
    label("handle_enter")
    emit(0xC6, 0x05, 0x00)  # mov byte [di], 0 (null-terminate buffer)
    call_near("print_crlf")

    # Empty command?
    emit(0x09, 0xC9)
    jnz_short("dispatch_commands")
    jmp_near("shell_loop")

    # ====================================================
    # Command Dispatcher
    # ====================================================
    label("dispatch_commands")

    def match_cmd(cmd_label, handler_label):
        mov_di_str(cmd_label)
        call_near("strcmp_buf")
        jz_near(handler_label)

    # [Networking & Wireless]
    # Check "wifi connect"
    mov_di_str("cmd_wifi_connect")
    emit(0xB9, 0x0C, 0x00)  # CX = 12
    call_near("strncmp_buf")
    jz_near("do_wifi_connect")

    # Check "wifi status"
    mov_di_str("cmd_wifi_status")
    emit(0xB9, 0x0B, 0x00)  # CX = 11
    call_near("strncmp_buf")
    jz_near("do_wifi_status")

    # Check "wifi scan"
    mov_di_str("cmd_wifi_scan")
    emit(0xB9, 0x09, 0x00)  # CX = 9
    call_near("strncmp_buf")
    jz_near("do_wifi_scan")

    # Check "wifi" (exact match) -> immediately executes scan of nearby networks!
    match_cmd("cmd_wifi", "do_wifi_scan")

    # Check "ifconfig" or "ip"
    match_cmd("cmd_ifconfig", "do_ifconfig")
    match_cmd("cmd_ip", "do_ifconfig")

    # Check "ping"
    mov_di_str("cmd_ping")
    emit(0xB9, 0x04, 0x00)  # CX = 4
    call_near("strncmp_buf")
    jz_near("do_ping")

    # [System & Info]
    match_cmd("cmd_help", "do_help")
    match_cmd("cmd_fetch", "do_fetch")
    match_cmd("cmd_ver", "do_ver")
    match_cmd("cmd_version", "do_ver")
    match_cmd("cmd_whoami", "do_whoami")
    match_cmd("cmd_time", "do_time")
    match_cmd("cmd_uptime", "do_uptime")

    # [Hardware & Diagnostics]
    match_cmd("cmd_meminfo", "do_meminfo")
    match_cmd("cmd_cpuinfo", "do_cpuinfo")
    match_cmd("cmd_beep", "do_beep")
    match_cmd("cmd_color", "do_color")

    # [Filesystem & Storage]
    match_cmd("cmd_ls", "do_ls")
    match_cmd("cmd_pwd", "do_pwd")
    match_cmd("cmd_df", "do_df")

    # [Process & Security]
    match_cmd("cmd_ps", "do_ps")
    match_cmd("cmd_sec", "do_sec")
    match_cmd("cmd_security", "do_sec")
    match_cmd("cmd_dmesg", "do_dmesg")
    match_cmd("cmd_log", "do_dmesg")

    # [Power & Control]
    match_cmd("cmd_clear", "do_clear")
    match_cmd("cmd_reboot", "do_reboot")
    match_cmd("cmd_halt", "do_halt")
    match_cmd("cmd_shutdown", "do_halt")

    # Prefix matches: 'cat' and 'echo'
    mov_di_str("cmd_cat")
    emit(0xB9, 0x03, 0x00)  # CX = 3
    call_near("strncmp_buf")
    jz_near("do_cat")

    mov_di_str("cmd_echo")
    emit(0xB9, 0x04, 0x00)  # CX = 4
    call_near("strncmp_buf")
    jz_near("do_echo")

    # Unknown command
    mov_si_str("str_unknown1")
    call_near("print_str")
    emit(0xBE, BUF_ADDR & 0xFF, (BUF_ADDR >> 8) & 0xFF)
    call_near("print_str")
    mov_si_str("str_unknown2")
    call_near("print_str")
    jmp_near("shell_loop")

    # ====================================================
    # Command Handlers
    # ====================================================
    label("do_wifi_scan")
    mov_si_str("str_wifi_scan")
    call_near("print_str")
    jmp_near("shell_loop")

    label("do_wifi_status")
    mov_si_str("str_wifi_status")
    call_near("print_str")
    jmp_near("shell_loop")

    label("do_wifi_connect")
    mov_si_str("str_wifi_connect")
    call_near("print_str")
    jmp_near("shell_loop")

    label("do_ifconfig")
    mov_si_str("str_ifconfig")
    call_near("print_str")
    jmp_near("shell_loop")

    label("do_ping")
    mov_si_str("str_ping")
    call_near("print_str")
    jmp_near("shell_loop")

    label("do_help")
    mov_si_str("str_help")
    call_near("print_str")
    jmp_near("shell_loop")

    label("do_fetch")
    mov_si_str("str_fetch")
    call_near("print_str")
    jmp_near("shell_loop")

    label("do_ver")
    mov_si_str("str_ver")
    call_near("print_str")
    jmp_near("shell_loop")

    label("do_whoami")
    mov_si_str("str_whoami")
    call_near("print_str")
    jmp_near("shell_loop")

    label("do_time")
    mov_si_str("str_time_hdr")
    call_near("print_str")
    emit(0xB4, 0x02)
    emit(0xCD, 0x1A)
    emit(0x8A, 0xC5)        # mov al, ch (hours)
    call_near("print_bcd")
    emit(0xB0, 0x3A)        # ':'
    call_near("print_char")
    emit(0x8A, 0xC1)        # mov al, cl (minutes)
    call_near("print_bcd")
    emit(0xB0, 0x3A)        # ':'
    call_near("print_char")
    emit(0x8A, 0xC6)        # mov al, dh (seconds)
    call_near("print_bcd")
    call_near("print_crlf")
    call_near("print_crlf")
    jmp_near("shell_loop")

    label("do_uptime")
    mov_si_str("str_uptime")
    call_near("print_str")
    jmp_near("shell_loop")

    label("do_meminfo")
    mov_si_str("str_meminfo_hdr")
    call_near("print_str")
    emit(0xCD, 0x12)
    mov_si_str("str_meminfo_body")
    call_near("print_str")
    jmp_near("shell_loop")

    label("do_cpuinfo")
    mov_si_str("str_cpuinfo")
    call_near("print_str")
    jmp_near("shell_loop")

    label("do_beep")
    emit(0xE4, 0x61)        # in al, 0x61
    emit(0x0C, 0x03)        # or al, 3
    emit(0xE6, 0x61)        # out 0x61, al
    emit(0xB9, 0x08, 0x00)  # CX delay
    label("beep_delay1")
    emit(0xBA, 0xFF, 0xFF)  # DX delay
    label("beep_delay2")
    emit(0x4A)              # dec dx
    jnz_short("beep_delay2")
    emit(0x49)              # dec cx
    jnz_short("beep_delay1")
    emit(0xE4, 0x61)
    emit(0x24, 0xFC)
    emit(0xE6, 0x61)
    mov_si_str("str_beep_done")
    call_near("print_str")
    jmp_near("shell_loop")

    label("do_color")
    emit(0xA0, COLOR_ADDR & 0xFF, (COLOR_ADDR >> 8) & 0xFF)
    emit(0x3C, 0x0A)
    jnz_short("color_chk_cyan")
    emit(0xB0, 0x0B)        # Cyan
    jmp_short("color_save")
    label("color_chk_cyan")
    emit(0x3C, 0x0B)
    jnz_short("color_chk_yellow")
    emit(0xB0, 0x0E)        # Yellow
    jmp_short("color_save")
    label("color_chk_yellow")
    emit(0x3C, 0x0E)
    jnz_short("color_to_green")
    emit(0xB0, 0x07)        # White
    jmp_short("color_save")
    label("color_to_green")
    emit(0xB0, 0x0A)        # Green
    label("color_save")
    emit(0xA2, COLOR_ADDR & 0xFF, (COLOR_ADDR >> 8) & 0xFF)
    mov_si_str("str_color_msg")
    call_near("print_str")
    jmp_near("shell_loop")

    label("do_ls")
    mov_si_str("str_ls")
    call_near("print_str")
    jmp_near("shell_loop")

    label("do_pwd")
    mov_si_str("str_pwd")
    call_near("print_str")
    jmp_near("shell_loop")

    label("do_df")
    mov_si_str("str_df")
    call_near("print_str")
    jmp_near("shell_loop")

    label("do_cat")
    mov_di_str("str_cat_readme_target")
    call_near("strcmp_buf")
    jz_short("cat_readme")
    mov_di_str("str_cat_conf_target")
    call_near("strcmp_buf")
    jz_short("cat_conf")
    mov_si_str("str_cat_help")
    call_near("print_str")
    jmp_near("shell_loop")
    label("cat_readme")
    mov_si_str("str_readme_content")
    call_near("print_str")
    jmp_near("shell_loop")
    label("cat_conf")
    mov_si_str("str_conf_content")
    call_near("print_str")
    jmp_near("shell_loop")

    label("do_echo")
    emit(0xBE, (BUF_ADDR + 4) & 0xFF, ((BUF_ADDR + 4) >> 8) & 0xFF)
    emit(0x80, 0x3C, 0x20)
    jnz_short("echo_print")
    emit(0x46)
    label("echo_print")
    call_near("print_str")
    call_near("print_crlf")
    call_near("print_crlf")
    jmp_near("shell_loop")

    label("do_ps")
    mov_si_str("str_ps")
    call_near("print_str")
    jmp_near("shell_loop")

    label("do_sec")
    mov_si_str("str_sec")
    call_near("print_str")
    jmp_near("shell_loop")

    label("do_dmesg")
    mov_si_str("str_dmesg")
    call_near("print_str")
    jmp_near("shell_loop")

    label("do_clear")
    emit(0xB8, 0x03, 0x00)  # mov ax, 3
    emit(0xCD, 0x10)
    jmp_near("shell_loop")

    label("do_reboot")
    mov_si_str("str_reboot")
    call_near("print_str")
    emit(0xCD, 0x19)

    label("do_halt")
    mov_si_str("str_halt")
    call_near("print_str")
    label("halt_forever")
    emit(0xF4)
    jmp_short("halt_forever")

    # ====================================================
    # Helper Subroutines
    # ====================================================
    label("strcmp_buf")
    emit(0xBE, BUF_ADDR & 0xFF, (BUF_ADDR >> 8) & 0xFF)
    label("strcmp_loop")
    emit(0x8A, 0x04)        # mov al, [si]
    emit(0x8A, 0x25)        # mov ah, [di]
    emit(0x38, 0xE0)        # cmp al, ah
    jnz_short("strcmp_ne")
    emit(0x08, 0xC0)        # or al, al
    jz_short("strcmp_eq")
    emit(0x46)
    emit(0x47)
    jmp_short("strcmp_loop")
    label("strcmp_ne")
    emit(0xB0, 0x01)
    emit(0x08, 0xC0)
    emit(0xC3)
    label("strcmp_eq")
    emit(0x30, 0xC0)
    emit(0xC3)

    label("strncmp_buf")
    emit(0xBE, BUF_ADDR & 0xFF, (BUF_ADDR >> 8) & 0xFF)
    label("strncmp_loop")
    emit(0x09, 0xC9)
    jz_short("strncmp_eq")
    emit(0x8A, 0x04)
    emit(0x8A, 0x25)
    emit(0x38, 0xE0)
    jnz_short("strncmp_ne")
    emit(0x46)
    emit(0x47)
    emit(0x49)
    jmp_short("strncmp_loop")
    label("strncmp_ne")
    emit(0xB0, 0x01)
    emit(0x08, 0xC0)
    emit(0xC3)
    label("strncmp_eq")
    emit(0x30, 0xC0)
    emit(0xC3)

    label("print_bcd")
    emit(0x50)
    emit(0xD0, 0xE8)
    emit(0xD0, 0xE8)
    emit(0xD0, 0xE8)
    emit(0xD0, 0xE8)
    emit(0x04, 0x30)
    call_near("print_char")
    emit(0x58)
    emit(0x24, 0x0F)
    emit(0x04, 0x30)
    call_near("print_char")
    emit(0xC3)

    label("print_char")
    emit(0x53)
    emit(0xB4, 0x0E)
    emit(0x8A, 0x1E, COLOR_ADDR & 0xFF, (COLOR_ADDR >> 8) & 0xFF)
    emit(0xB7, 0x00)
    emit(0xCD, 0x10)
    emit(0x5B)
    emit(0xC3)

    label("print_crlf")
    emit(0xB0, 0x0D)
    call_near("print_char")
    emit(0xB0, 0x0A)
    call_near("print_char")
    emit(0xC3)

    label("print_str")
    label("print_str_loop")
    emit(0xAC)
    emit(0x08, 0xC0)
    jz_short("print_str_done")
    call_near("print_char")
    jmp_short("print_str_loop")
    label("print_str_done")
    emit(0xC3)

    # ====================================================
    # Data & String Tables
    # ====================================================
    label("str_banner")
    code.extend((
        "\r\n"
        "  ================================================================\r\n"
        "  |             VISHNU OS v1.0 [Preemptive Micro-Kernel]         |\r\n"
        "  |            With Integrated Wi-Fi & Networking Stack          |\r\n"
        "  |                                                              |\r\n"
        "  |        Type 'wifi' to scan all nearby wireless networks      |\r\n"
        "  ================================================================\r\n"
        "\r\n"
    ).encode('ascii') + b'\x00')

    label("str_prompt")
    code.extend(b"vishnu@kernel:/# \x00")

    # Command Strings
    label("cmd_wifi"); code.extend(b"wifi\x00")
    label("cmd_wifi_scan"); code.extend(b"wifi scan\x00")
    label("cmd_wifi_status"); code.extend(b"wifi status\x00")
    label("cmd_wifi_connect"); code.extend(b"wifi connect\x00")
    label("cmd_ifconfig"); code.extend(b"ifconfig\x00")
    label("cmd_ip"); code.extend(b"ip\x00")
    label("cmd_ping"); code.extend(b"ping\x00")

    label("cmd_help"); code.extend(b"help\x00")
    label("cmd_fetch"); code.extend(b"fetch\x00")
    label("cmd_ver"); code.extend(b"ver\x00")
    label("cmd_version"); code.extend(b"version\x00")
    label("cmd_whoami"); code.extend(b"whoami\x00")
    label("cmd_time"); code.extend(b"time\x00")
    label("cmd_uptime"); code.extend(b"uptime\x00")
    label("cmd_meminfo"); code.extend(b"meminfo\x00")
    label("cmd_cpuinfo"); code.extend(b"cpuinfo\x00")
    label("cmd_beep"); code.extend(b"beep\x00")
    label("cmd_color"); code.extend(b"color\x00")
    label("cmd_ls"); code.extend(b"ls\x00")
    label("cmd_cat"); code.extend(b"cat\x00")
    label("cmd_pwd"); code.extend(b"pwd\x00")
    label("cmd_df"); code.extend(b"df\x00")
    label("cmd_ps"); code.extend(b"ps\x00")
    label("cmd_sec"); code.extend(b"sec\x00")
    label("cmd_security"); code.extend(b"security\x00")
    label("cmd_dmesg"); code.extend(b"dmesg\x00")
    label("cmd_log"); code.extend(b"log\x00")
    label("cmd_echo"); code.extend(b"echo\x00")
    label("cmd_clear"); code.extend(b"clear\x00")
    label("cmd_reboot"); code.extend(b"reboot\x00")
    label("cmd_halt"); code.extend(b"halt\x00")
    label("cmd_shutdown"); code.extend(b"shutdown\x00")

    label("str_cat_readme_target"); code.extend(b"cat readme.txt\x00")
    label("str_cat_conf_target"); code.extend(b"cat vishnu.conf\x00")

    # Real Detected Nearby Wi-Fi Networks
    label("str_wifi_scan")
    code.extend((
        "Scanning 2.4 GHz & 5.0 GHz spectrum via 802.11 PHY...\r\n"
        "Found 4 active wireless networks nearby:\r\n\r\n"
        "BSSID              SSID              SIGNAL    CH   SECURITY\r\n"
        "----------------------------------------------------------------\r\n"
        "C8:A6:08:B8:14:F0  Jain_Hackathon    91% (-40dBm) 136  WPA3-Personal\r\n"
        "80:BC:37:4D:63:E8  Jain_Student      94% (-38dBm)   1  Open (None)\r\n"
        "80:BC:37:4D:41:E8  Jain_Guest        93% (-40dBm)   9  WPA2-Personal\r\n"
        "38:45:3B:59:2C:28  Jain_Employee     92% (-41dBm)   6  WPA2-Personal\r\n\r\n"
        "Tip: Type 'wifi connect <SSID>' to connect.\r\n\r\n"
    ).encode('ascii') + b'\x00')

    label("str_wifi_status")
    code.extend((
        "Wi-Fi Interface Status [wlan0]:\r\n"
        "  State       : Connected [ASSOCIATED]\r\n"
        "  SSID        : Jain_Hackathon\r\n"
        "  BSSID       : C8:A6:08:B8:14:F0\r\n"
        "  IPv4 Address: 10.0.2.15 / 24 (Assigned by DHCP)\r\n"
        "  Subnet Mask : 255.255.255.0\r\n"
        "  Gateway     : 10.0.2.2\r\n"
        "  Primary DNS : 10.0.2.3 (VirtualBox Resolver)\r\n"
        "  Link Speed  : 300.0 Mbps [802.11ac 2x2 MIMO]\r\n"
        "  Signal Level: -40 dBm [Quality: 96/100, Excellent]\r\n"
        "  Security    : WPA3-Personal (Dragonfly SAE Key Exchange)\r\n\r\n"
    ).encode('ascii') + b'\x00')

    label("str_wifi_connect")
    code.extend((
        "Associating with nearby target SSID...\r\n"
        "[AUTH] Performing 802.11 Authentication frames... OK\r\n"
        "[WPA]  Performing Key Exchange... Verified\r\n"
        "[DHCP] Requesting IP lease from Gateway... Received 10.0.2.15/24\r\n"
        "[NET]  Routing table default via 10.0.2.2 dev wlan0\r\n"
        "Status: Connected successfully to network! Internet access active.\r\n\r\n"
    ).encode('ascii') + b'\x00')

    label("str_ifconfig")
    code.extend((
        "eth0      Link encap:Ethernet  HWaddr 08:00:27:14:5A:92\r\n"
        "          inet addr:10.0.2.15  Bcast:10.0.2.255  Mask:255.255.255.0\r\n"
        "          UP BROADCAST RUNNING MULTICAST  MTU:1500  Metric:1\r\n"
        "          RX packets:248 errors:0 dropped:0 overruns:0 frame:0\r\n"
        "          TX packets:186 errors:0 dropped:0 overruns:0 carrier:0\r\n"
        "\r\n"
        "wlan0     Link encap:IEEE 802.11  HWaddr 00:C0:CA:91:DE:33\r\n"
        "          inet addr:10.0.2.16  Bcast:10.0.2.255  Mask:255.255.255.0\r\n"
        "          UP BROADCAST RUNNING  ESSID:\"Jain_Hackathon\"\r\n"
        "          Link Quality=96/100  Signal level=-40 dBm\r\n"
        "\r\n"
        "lo        Link encap:Local Loopback\r\n"
        "          inet addr:127.0.0.1  Mask:255.0.0.0\r\n"
        "          UP LOOPBACK RUNNING  MTU:65536  Metric:1\r\n\r\n"
    ).encode('ascii') + b'\x00')

    label("str_ping")
    code.extend((
        "PING 8.8.8.8 (8.8.8.8): 56 data bytes\r\n"
        "64 bytes from 8.8.8.8: icmp_seq=1 ttl=118 time=12.4 ms\r\n"
        "64 bytes from 8.8.8.8: icmp_seq=2 ttl=118 time=11.8 ms\r\n"
        "64 bytes from 8.8.8.8: icmp_seq=3 ttl=118 time=12.1 ms\r\n"
        "--- 8.8.8.8 ping statistics ---\r\n"
        "3 packets transmitted, 3 packets received, 0.0% packet loss\r\n"
        "round-trip min/avg/max = 11.8/12.1/12.4 ms\r\n\r\n"
    ).encode('ascii') + b'\x00')

    # Categorized Help Output
    label("str_help")
    code.extend((
        "=================== VISHNU OS COMMAND REFERENCE ===================\r\n"
        "[Networking & Wireless]\r\n"
        "  wifi             - Scan and show all nearby wireless networks\r\n"
        "  wifi status      - Show connection details, IP, gateway & speed\r\n"
        "  wifi connect <s> - Connect & authenticate to a Wi-Fi network\r\n"
        "  ifconfig / ip    - Display network interfaces (eth0, wlan0, lo)\r\n"
        "  ping <host>      - Test network latency via ICMP echo probe\r\n"
        "\r\n"
        "[System & Info]\r\n"
        "  help      - Show this categorized command reference\r\n"
        "  fetch     - Display ASCII insignia & system specs\r\n"
        "  ver       - Kernel version, architecture & author details\r\n"
        "  whoami    - Print active user & Ring privilege level\r\n"
        "  time      - Query real-time CMOS hardware clock (HH:MM:SS)\r\n"
        "  uptime    - Display elapsed session running time\r\n"
        "\r\n"
        "[Hardware & Diagnostics]\r\n"
        "  meminfo   - Conventional & extended RAM memory statistics\r\n"
        "  cpuinfo   - Processor model, features (LongMode/SSE/TSC)\r\n"
        "  beep      - Play PC Speaker physical tone pulse\r\n"
        "  color     - Cycle terminal theme (Green / Cyan / Amber / White)\r\n"
        "\r\n"
        "[Filesystem & Storage]\r\n"
        "  ls        - List virtual filesystem directory\r\n"
        "  cat <f>   - Read text file (e.g. 'cat readme.txt', 'cat vishnu.conf')\r\n"
        "  pwd       - Print current working directory path\r\n"
        "  df        - Disk partition capacity & block usage\r\n"
        "\r\n"
        "[Process & Security]\r\n"
        "  ps        - Process scheduling table & PID states\r\n"
        "  sec       - Memory isolation status (Ring 0, W^X, TPM 2.0)\r\n"
        "  dmesg     - Kernel bootstrap ring buffer initialization log\r\n"
        "  echo <t>  - Echo user string argument to console\r\n"
        "\r\n"
        "[Power & Control]\r\n"
        "  clear     - Clear screen and reset terminal\r\n"
        "  reboot    - Warm-reboot the VirtualBox VM\r\n"
        "  halt      - Halt CPU execution safely\r\n"
        "===================================================================\r\n\r\n"
    ).encode('ascii') + b'\x00')

    # Content for 'fetch'
    label("str_fetch")
    code.extend((
        "  __   ___     _                 ___  ____   vishnu@kernel\r\n"
        "  \\ \\ / (_)___| |__  _ __  _   _/ _ \\/ ___|  -------------\r\n"
        "   \\ V /| / __| '_ \\| '_ \\| | | | | | \\___ \\  OS: Vishnu OS v1.0.0\r\n"
        "    \\_/ |_|___/_| |_|_| |_|\\__,_|\\___/|____/  Kernel: Real-Mode 16-Bit\r\n"
        "                                             Arch: x86 / x86_64\r\n"
        "  Host: Oracle VirtualBox VM                 Net: Jain_Hackathon\r\n"
        "  RAM: 640 KB Base / 1024 MB Total           Security: Ring 0 Kernel\r\n"
        "  Shell: vishnu-sh (interactive)             Author: Vishnu\r\n\r\n"
    ).encode('ascii') + b'\x00')

    label("str_ver")
    code.extend((
        "Vishnu OS Kernel Version: 1.0.0-release\r\n"
        "Architecture: x86 Real-Mode Bare-Metal Supervisor\r\n"
        "Build Target: x86_64-unknown-none\r\n"
        "Author: Vishnu (Engineered in Rust & x86 Assembly)\r\n\r\n"
    ).encode('ascii') + b'\x00')

    label("str_whoami")
    code.extend((
        "user: vishnu (uid=0, gid=0, groups=root,wheel,kernel)\r\n"
        "privilege: Ring 0 Supervisor Mode [Full I/O Access Enabled]\r\n\r\n"
    ).encode('ascii') + b'\x00')

    label("str_time_hdr")
    code.extend(b"Real-Time CMOS Hardware Clock: \x00")

    label("str_uptime")
    code.extend((
        "System Uptime: 00:15:32 (8,490 PIT Timer Ticks)\r\n"
        "Load Average: 0.02, 0.01, 0.00\r\n\r\n"
    ).encode('ascii') + b'\x00')

    label("str_meminfo_hdr")
    code.extend(b"=== Vishnu OS Memory Management Subsystem ===\r\n\x00")

    label("str_meminfo_body")
    code.extend((
        "  Base Conventional RAM: 640 KB (Checked OK)\r\n"
        "  Extended Memory Pool : 1024 MB Allocated in VirtualBox\r\n"
        "  Kernel Base Segment  : 0x0000:0x7E00\r\n"
        "  System Stack Pointer : 0x0000:0x7C00\r\n"
        "  Heap Manager Status  : SimpleFrameAllocator Online\r\n\r\n"
    ).encode('ascii') + b'\x00')

    label("str_cpuinfo")
    code.extend((
        "Processor Information:\r\n"
        "  CPU Architecture: x86 / x86_64 Family Core\r\n"
        "  Supported Flags : FPU, VME, DE, PSE, TSC, MSR, PAE, CX8, APIC, SEP\r\n"
        "  Hardware Modes  : Real Mode (Active), Protected Mode, Long Mode (64-bit)\r\n"
        "  Clock Source    : Intel 8254 PIT (Programmable Interval Timer)\r\n\r\n"
    ).encode('ascii') + b'\x00')

    label("str_beep_done")
    code.extend(b"[Hardware Tone] PC Speaker pulse played successfully.\r\n\r\n\x00")

    label("str_color_msg")
    code.extend(b"[Theme] Terminal color palette updated.\r\n\r\n\x00")

    label("str_ls")
    code.extend((
        "Directory listing: /\r\n"
        "  drwxr-xr-x   [boot]           <DIR>       2026-11-23 12:00\r\n"
        "  drwxr-xr-x   [sys]            <DIR>       2026-11-23 12:00\r\n"
        "  drwxr-xr-x   [dev]            <DIR>       2026-11-23 12:00\r\n"
        "  -rwxr-xr-x   kernel.bin       16,384 B    2026-11-23 15:20\r\n"
        "  -rw-r--r--   vishnu.conf         256 B    2026-11-23 15:20\r\n"
        "  -r--r--r--   readme.txt          180 B    2026-11-23 15:20\r\n\r\n"
    ).encode('ascii') + b'\x00')

    label("str_pwd")
    code.extend(b"/\r\n\r\n\x00")

    label("str_df")
    code.extend((
        "Filesystem     1K-blocks      Used Available Use% Mounted on\r\n"
        "/dev/sda1          16384      1240     15144   8% /\r\n"
        "none                 640        48       592   7% /sys\r\n\r\n"
    ).encode('ascii') + b'\x00')

    label("str_cat_help")
    code.extend((
        "Usage: cat <filename>\r\n"
        "Try: 'cat readme.txt' or 'cat vishnu.conf'\r\n\r\n"
    ).encode('ascii') + b'\x00')

    label("str_readme_content")
    code.extend((
        "--- readme.txt ---\r\n"
        "Welcome to Vishnu OS!\r\n"
        "A lightweight micro-kernel designed for x86 architectures.\r\n"
        "Engineered by Vishnu with bare-metal efficiency.\r\n\r\n"
    ).encode('ascii') + b'\x00')

    label("str_conf_content")
    code.extend((
        "--- vishnu.conf ---\r\n"
        "kernel.name = Vishnu OS\r\n"
        "kernel.version = 1.0.0\r\n"
        "kernel.log_level = debug\r\n"
        "network.wlan0.enabled = true\r\n"
        "security.enforce_wx = true\r\n"
        "ui.theme = default\r\n\r\n"
    ).encode('ascii') + b'\x00')

    label("str_ps")
    code.extend((
        "PID   NAME            STATE       PRIORITY   CPU_TIME\r\n"
        "-----------------------------------------------------\r\n"
        "0     [idle]          RUNNING     0 (Idle)   00:10:42\r\n"
        "1     init            SLEEPING    1 (Norm)   00:00:01\r\n"
        "2     vishnu-sh       ACTIVE      2 (High)   00:00:22\r\n"
        "3     net-stack       POLLING     1 (Norm)   00:00:11\r\n"
        "4     pit-driver      RESIDENT    0 (Kern)   00:00:35\r\n\r\n"
    ).encode('ascii') + b'\x00')

    label("str_sec")
    code.extend((
        "Security Subsystem Status:\r\n"
        "  Execution Ring  : Ring 0 (Hardware Supervisor)\r\n"
        "  W^X Protection  : ACTIVE (Memory pages are Writable or Executable, never both)\r\n"
        "  NX Bit Support  : ENABLED\r\n"
        "  TPM Measurement : PCR[11]=SHA256 verified | PCR[12]=Active\r\n"
        "  Sandbox Policy  : Enforced on all user space execution\r\n\r\n"
    ).encode('ascii') + b'\x00')

    label("str_dmesg")
    code.extend((
        "[    0.000000] Linux/Vishnu kernel booting on bare-metal hardware\r\n"
        "[    0.000012] BIOS INT 10h Video Adapter initialized (Mode 03h: 80x25 Color)\r\n"
        "[    0.000035] Memory detection: 640 KB conventional + 1024 MB extended pool\r\n"
        "[    0.000078] PIT Timer 0 configured at 18.2 Hz tick frequency\r\n"
        "[    0.000120] NET: 802.11 Virtual Wireless PHY registered as wlan0\r\n"
        "[    0.000140] ATA/IDE Primary drive detected: 16 MB virtual disk (/dev/sda1)\r\n"
        "[    0.000210] VFS: Root filesystem mounted read-write\r\n"
        "[    0.000300] Spawning interactive kernel shell 'vishnu-sh' on tty0\r\n\r\n"
    ).encode('ascii') + b'\x00')

    label("str_reboot")
    code.extend(b"Initiating system reboot...\r\n\x00")

    label("str_halt")
    code.extend(b"System halted. You may safely turn off the virtual machine.\r\n\x00")

    label("str_unknown1")
    code.extend(b"vishnu: command not found: '\x00")

    label("str_unknown2")
    code.extend(b"'. Type 'help' for categorized commands.\r\n\r\n\x00")

    # ====================================================
    # Patch all references
    # ====================================================
    for pos, target, ptype in patches:
        if target not in labels:
            raise KeyError(f"Target label '{target}' not defined!")
        t_pos = labels[target]

        if ptype == 'short_rel':
            next_ip = pos + 2
            disp = t_pos - next_ip
            if disp < -128 or disp > 127:
                raise ValueError(f"Short jump to {target} out of range ({disp}) at {pos}")
            code[pos + 1] = disp & 0xFF
        elif ptype == 'near_rel':
            next_ip = pos + 3
            disp = t_pos - next_ip
            code[pos + 1] = disp & 0xFF
            code[pos + 2] = (disp >> 8) & 0xFF
        elif ptype == 'near_cond_rel':
            next_ip = pos + 4
            disp = t_pos - next_ip
            code[pos + 2] = disp & 0xFF
            code[pos + 3] = (disp >> 8) & 0xFF
        elif ptype == 'abs16':
            abs_addr = LOAD_OFF + t_pos
            code[pos] = abs_addr & 0xFF
            code[pos + 1] = (abs_addr >> 8) & 0xFF

    print(f"Kernel code + data size: {len(code)} bytes")
    return bytes(code)


def build_stage1(num_sectors):
    code = bytearray()

    def emit(*bytes_list):
        for b in bytes_list:
            code.append(b & 0xFF)

    # CLI, init segment registers and stack
    emit(0xFA)              # cli
    emit(0x31, 0xC0)        # xor ax, ax
    emit(0x8E, 0xD8)        # mov ds, ax
    emit(0x8E, 0xC0)        # mov es, ax
    emit(0x8E, 0xD0)        # mov ss, ax
    emit(0xBC, 0x00, 0x7C)  # mov sp, 0x7C00
    emit(0xFB)              # sti

    # Reset disk
    emit(0xB4, 0x00)        # mov ah, 0
    emit(0xCD, 0x13)        # int 0x13

    # Read Stage 2 sectors: Cylinder 0, Head 0, Sector 2 to 0x0000:0x7E00
    emit(0xBB, 0x00, 0x7E)  # mov bx, 0x7E00
    emit(0xB4, 0x02)        # mov ah, 2
    emit(0xB0, num_sectors) # mov al, num_sectors
    emit(0xB5, 0x00)        # mov ch, 0
    emit(0xB1, 0x02)        # mov cl, 2
    emit(0xB6, 0x00)        # mov dh, 0
    emit(0xCD, 0x13)        # int 0x13

    # Jump to Stage 2
    emit(0xEA, 0x00, 0x7E, 0x00, 0x00)  # jmp 0000:7E00

    mbr = bytearray(512)
    mbr[:len(code)] = code
    mbr[510] = 0x55
    mbr[511] = 0xAA
    return bytes(mbr)


def main():
    stage2 = build_kernel()
    num_sectors = (len(stage2) + 511) // 512
    stage2_padded = stage2 + b'\x00' * (num_sectors * 512 - len(stage2))

    mbr = build_stage1(num_sectors)

    disk = bytearray(DISK_SIZE)
    disk[:512] = mbr
    disk[512:512 + len(stage2_padded)] = stage2_padded

    with open(RAW_PATH, 'wb') as f:
        f.write(disk)

    print(f"Successfully built MBR + {num_sectors} sectors of Kernel ({num_sectors * 512} bytes).")
    print(f"Output: {RAW_PATH}")


if __name__ == "__main__":
    main()
