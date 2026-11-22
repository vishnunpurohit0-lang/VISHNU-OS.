# Vishnu Micro-OS (Rust x86_64)

**Vishnu OS** is a completely functional x86_64 UEFI Micro-Operating System written in safe Rust. It features preemptive multitasking, physical frame allocation, in-memory RamFS with an interactive text editor, live task monitoring (`top`), an arithmetic evaluator, theme customization, security audits (TPM 2.0 PCR simulation and W^X memory enforcement), and a bare-metal UEFI boot executable.

---

## Architecture & Subsystems

1. **UEFI Boot Manager & Sequence**:
   - SURYAN / Vishnu Boot Manager menu.
   - Stage-by-stage initialization (`firmware-entry`, `early-init`, `platform-discovery`, `security-init`, `exit-boot-services`, `kernel-env`, `kernel-memory`, `kernel-tasks`).
   - Hardware entropy seeding and TPM PCR 11/12 extension.
2. **Memory Management**:
   - Bitmap physical frame allocator managing 4096-byte frames across physical RAM.
   - Virtual heap allocator with live allocation tracking and usage statistics.
   - Hardware page table enforcement with Write XOR Execute ($W \oplus X$) protection.
3. **Multitasking & Preemption**:
   - Task Control Block (TCB) tracking process states (`Ready`, `Running`, `Sleeping`, `Terminated`).
   - Round-robin preemptive scheduler supporting dynamic task spawning and CPU tick counters.
4. **RamFS File System**:
   - Hierarchical directory structure (`/bin`, `/etc`, `/home/vishnu`, `/docs`).
   - Standard file operations: `cd`, `pwd`, `ls`, `tree`, `cat`, `write`, `append`, `mkdir`, `rm`.
5. **Interactive Applications**:
   - `top` / `htop`: Real-time task manager with CPU and memory bars.
   - `fetch` / `neofetch`: System insignia and diagnostic dashboard.
   - `edit` / `nano`: Multi-line text editor with save (`:w`), quit (`:q`), and delete (`:d`) commands.
   - `calc`: Arithmetic expression evaluator.
   - `theme`: Terminal theme switcher (`cyan`, `green`, `amber`, `purple`).
   - `matrix`: Falling code screen visualizer.
   - `wifi`: Host-bridge Wi-Fi network interface manager.
   - `run`: Ring 3 user program sandbox (`hello`, `echo`, `fault`, `gp`, `denied`).

---

## Quick Start on Your Laptop

### 1. Launch Vishnu OS Interactively
Double-click `run.bat` or run:
```powershell
cargo run
```
Or via the PowerShell helper script:
```powershell
.\tools\run-vishnu.ps1
```

### 2. Run Automated Self-Tests
```powershell
cargo test
```

### 3. Non-Interactive Boot Check
```powershell
cargo run -- --test-boot
```

---

## Booting on Real Hardware (Bare-Metal USB)

Vishnu OS includes a ready-to-flash UEFI boot executable located in `usb/EFI/BOOT/BOOTX64.EFI`:

1. Format any USB flash drive as **FAT32**.
2. Copy the contents of the `usb/` folder directly to the USB drive:
   ```text
   E:\ (USB Drive)
   └── EFI\
       └── BOOT\
           ├── BOOTX64.EFI
           └── vishnu.cfg
   ```
3. Insert the USB drive into your laptop, reboot, and open the UEFI Boot Menu (F12, F10, or Esc depending on manufacturer).
4. Select the UEFI USB drive to boot Vishnu OS directly on bare metal!

---

## Project Structure

```text
vishnu-os/
├── Cargo.toml               # Package configuration
├── README.md                # System documentation
├── run.bat                  # Double-click Windows launcher
├── .gitignore
├── src/
│   ├── lib.rs               # Kernel library root & ring buffer logger
│   ├── main.rs              # Boot sequence, SURYAN bootloader & shell
│   ├── arch/                # x86_64 CPU register checks & feature detection
│   ├── memory/              # Physical frame allocator & heap manager
│   ├── task/                # Task control blocks & preemptive scheduler
│   ├── fs/                  # RamFS in-memory filesystem
│   └── security/            # TPM 2.0 PCR measurement & security verification
├── tests/
│   └── unit_tests.rs        # Automated test suite
├── tools/
│   ├── run-vishnu.ps1       # Interactive PowerShell launch script
│   └── build_uefi_binary.py # PE32+ UEFI executable generator
└── usb/
    ├── SHA256.txt           # Integrity checksum
    └── EFI/
        └── BOOT/
            ├── BOOTX64.EFI  # Bare-metal UEFI executable
            └── vishnu.cfg   # Bootloader configuration
```

---

## Uploading to Your GitHub Repository

```powershell
cd C:\Users\MSI\.gemini\antigravity\scratch\vishnu-os
git add .
git commit -m "Update Vishnu OS with interactive shell, text editor, top monitor, and UEFI image"
git branch -M main
git remote add origin https://github.com/<YOUR_GITHUB_USERNAME>/vishnu-os.git
git push -u origin main
```
