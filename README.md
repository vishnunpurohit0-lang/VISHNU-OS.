# Vishnu OS - Micro-Kernel in Rust

Vishnu OS is a modular x86_64 UEFI Micro-Operating System written in Rust. It features preemptive multitasking, physical frame allocation, in-memory RamFS, TPM 2.0 measured boot simulation, hardware memory protections (W^X, SMEP, SMAP), and an interactive command shell.

---

## Key Features

- **Memory Management**: Physical bitmap frame allocator (4096-byte pages) and 32 MB heap manager.
- **Multitasking & Preemption**: Preemptive round-robin scheduler with task control blocks (TCBs) and preemption tick counters.
- **In-Memory RamFS**: Hierarchical filesystem supporting directory traversal (`cd`, `pwd`), listing (`ls`, `tree`), creation (`mkdir`, `write`, `append`), deletion (`rm`), and reading (`cat`).
- **Security & Measured Boot**: TPM 2.0 PCR simulation (PCR 11 boot phase marker, PCR 12 measured command line), hardware entropy seeding, and memory protection verification.
- **Interactive Shell**: Rich command-line interface with diagnostics (`cpuinfo`, `meminfo`, `security`, `ps`, `counters`, `wifi`, `run`, `log`).

---

## Directory Structure

```text
vishnu-os/
├── Cargo.toml               # Rust package manifest
├── README.md                # Project documentation
├── .gitignore
├── src/
│   ├── lib.rs               # Kernel library root & ring buffer logger
│   ├── main.rs              # Boot sequence & interactive shell
│   ├── arch/                # CPU register checks & x86_64 feature detection
│   ├── memory/              # Physical frame allocator & heap manager
│   ├── task/                # Task control blocks & preemptive scheduler
│   ├── fs/                  # RamFS in-memory filesystem
│   └── security/            # TPM 2.0 PCR measurement & security verification
├── tests/
│   └── unit_tests.rs        # Automated test suite
├── tools/
│   └── run-vishnu.ps1       # Interactive PowerShell launch script
└── usb/
    └── EFI/BOOT/vishnu.cfg  # UEFI boot configuration
```

---

## Building and Running

### 1. Run Automated Tests
```powershell
cargo test
```

### 2. Launch Vishnu OS Interactively
```powershell
cargo run
# or run the helper script:
.\tools\run-vishnu.ps1
```

### 3. Non-Interactive Boot Self-Check
```powershell
cargo run -- --test-boot
```

---

## Pushing to Your Own GitHub Repository

To upload this project to your own GitHub repo:

```powershell
cd C:\Users\MSI\.gemini\antigravity\scratch\vishnu-os
git init
git add .
git commit -m "Initial commit of Vishnu OS"
git branch -M main
git remote add origin https://github.com/<YOUR_USERNAME>/<YOUR_REPO_NAME>.git
git push -u origin main
```
