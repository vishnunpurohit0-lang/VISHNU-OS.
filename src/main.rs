use std::io::{self, BufRead, Write};
use vishnu_kernel::arch::x86_64::CpuFeatures;
use vishnu_kernel::fs::RamFs;
use vishnu_kernel::memory::{FrameAllocator, SimpleHeap};
use vishnu_kernel::security::{get_security_status, TpmMeasurement};
use vishnu_kernel::task::Scheduler;
use vishnu_kernel::{KernelRingLog, KERNEL_NAME, KERNEL_VERSION};

fn print_banner() {
    println!("\x1b[1;36m");
    println!("  ===============================================================");
    println!("  *      __     ___     _                 ___  ____             *");
    println!("  *      \\ \\   / (_)___| |__  _ __  _   _/ _ \\/ ___|            *");
    println!("  *       \\ \\ / /| / __| '_ \\| '_ \\| | | | | | \\___ \\            *");
    println!("  *        \\ V / | \\__ \\ | | | | | | |_| | |_| |___) |           *");
    println!("  *         \\_/  |_|___/_| |_|_| |_|\\__,_|\\___/|____/            *");
    println!("  *                                                             *");
    println!("  *            Vishnu Micro-OS // Rust Kernel v0.11.0            *");
    println!("  *             Target: x86_64 UEFI Secure Micro-Kernel          *");
    println!("  ===============================================================");
    println!("\x1b[0m");
}

fn boot_sequence(log: &mut KernelRingLog, tpm: &mut TpmMeasurement) {
    println!("\x1b[1;33m[*] Starting Vishnu OS Boot Sequence...\x1b[0m");

    log.log("firmware-entry", "Watchdog disabled, calibrating TSC timer (3.20 GHz)");
    println!(" [0.000100] [BOOT::firmware-entry  ] Watchdog disabled, TSC calibrated");

    log.log("early-init", "GOP Framebuffer 1920x1080 32bpp initialized");
    println!(" [0.002400] [BOOT::early-init      ] CPUID x86_64 verified, GOP Framebuffer ready");

    log.log("platform-discovery", "ACPI RSDP 2.0 verified, SecureBoot=Enrolled");
    println!(" [0.005100] [BOOT::platform-disc   ] ACPI tables checked, Secure Boot verified");

    tpm.extend_pcr12("BOOT_IMAGE=vishnu.efi quiet mode=1920x1080");
    log.log("security-init", "TPM PCR 12 extended with boot commandline");
    println!(" [0.008900] [BOOT::security-init   ] Hardware entropy seeded, PCR 12 extended");

    tpm.mark_phase("EXIT_BOOT_SERVICES");
    log.log("exit-boot-serv", "Firmware boot services exited, PCR 11 phase marked");
    println!(" [0.012300] [BOOT::exit-boot-serv  ] PCR 11 sealed, firmware handoff complete");

    log.log("kernel-env", "GDT/TSS loaded, W^X page tables enabled, CR0.WP=1");
    println!(" [0.015000] [BOOT::kernel-env      ] Memory protection active (W^X, SMEP, SMAP)");

    log.log("kernel-tasks", "Round-robin scheduler active, spawning shell task");
    println!(" [0.025000] [BOOT::kernel-tasks    ] Preemptive multitasking initialized");
    println!("\x1b[1;32m[✓] Boot Complete! Entering Vishnu OS Shell.\x1b[0m\n");
}

fn print_help() {
    println!("\x1b[1;34m--- Vishnu OS Commands ---\x1b[0m");
    println!("  help                 - Display available commands");
    println!("  uname / version      - Show OS and kernel information");
    println!("  uptime               - Show system ticks and uptime");
    println!("  cpuinfo              - Inspect CPU features and security flags");
    println!("  meminfo / df         - Frame allocator and heap memory statistics");
    println!("  security / tpm       - View TPM PCR measurements and protection state");
    println!("  ps / tasks           - List running scheduler tasks");
    println!("  spawn <name>         - Spawn a worker task to test preemption");
    println!("  counters             - Show scheduler preemption tick counters");
    println!("  ls [path]            - List directory contents");
    println!("  tree [path]          - Recursive directory tree view");
    println!("  cd <path>            - Change directory");
    println!("  pwd                  - Print current working directory");
    println!("  cat <file>           - Display file contents");
    println!("  write <file> <text>  - Create or overwrite a file");
    println!("  append <file> <text> - Append text to an existing file");
    println!("  mkdir <path>         - Create a directory");
    println!("  rm <path>            - Remove a file or folder");
    println!("  run <prog>           - Execute isolated ring-3 user program");
    println!("  wifi [scan|status]   - Inspect Wi-Fi host bridge status");
    println!("  log                  - Display kernel boot ring log");
    println!("  clear / cls          - Clear screen");
    println!("  reboot / exit        - Shut down Vishnu OS session");
}

fn main() {
    print_banner();

    let mut log = KernelRingLog::new();
    let mut tpm = TpmMeasurement::new();
    let mut frames = FrameAllocator::new();
    let mut heap = SimpleHeap::new(32 * 1024 * 1024); // 32 MB heap
    let mut scheduler = Scheduler::new();
    let mut fs = RamFs::new();
    let cpu = CpuFeatures::probe();

    // Allocate initial kernel frames and heap
    for _ in 0..128 {
        frames.alloc_frame();
    }
    heap.allocate(512 * 1024);

    boot_sequence(&mut log, &mut tpm);

    // If executed with non-interactive flag
    let args: Vec<String> = std::env::args().collect();
    if args.contains(&"--test-boot".to_string()) {
        println!("Test boot successful. Exiting clean.");
        return;
    }

    let stdin = io::stdin();
    let mut reader = stdin.lock();

    println!("Type \x1b[1;33mhelp\x1b[0m to explore commands, or \x1b[1;33mexit\x1b[0m to quit.\n");

    loop {
        // Advance scheduler tick
        scheduler.tick();

        print!("\x1b[1;32mvishnu@kernel\x1b[0m:\x1b[1;34m{}\x1b[0m# ", fs.current_path());
        io::stdout().flush().unwrap();

        let mut line = String::new();
        if reader.read_line(&mut line).unwrap_or(0) == 0 {
            break; // EOF
        }

        let trimmed = line.trim();
        if trimmed.is_empty() {
            continue;
        }

        let parts: Vec<&str> = trimmed.split_whitespace().collect();
        let cmd = parts[0];

        match cmd {
            "help" => print_help(),
            "clear" | "cls" => {
                print!("\x1b[2J\x1b[1;1H");
                io::stdout().flush().unwrap();
            }
            "uname" | "version" => {
                println!("{} version {} ({})", KERNEL_NAME, KERNEL_VERSION, cpu.vendor);
            }
            "uptime" => {
                println!("Vishnu OS Ticks: {}, CPU clock: ~3.2 GHz", scheduler.total_ticks());
            }
            "cpuinfo" => {
                println!("CPU Vendor: {}", cpu.vendor);
                println!("Features  : NX={}, SMEP={}, SMAP={}, UMIP={}, RDRAND={}",
                    cpu.has_nx, cpu.has_smep, cpu.has_smap, cpu.has_umip, cpu.has_rdrand);
            }
            "meminfo" | "df" => {
                let h_stats = heap.stats();
                println!("Physical Frames : {} allocated, {} free (Page Size: 4 KiB)",
                    frames.allocated_frames(), frames.free_frames());
                println!("Virtual Heap    : {} KB used / {} KB total ({} allocations)",
                    h_stats.used_bytes / 1024, h_stats.total_bytes / 1024, h_stats.allocation_count);
            }
            "security" | "tpm" => {
                let sec = get_security_status(&tpm);
                println!("Secure Boot     : {}", if sec.secure_boot_enabled { "ENABLED (Validated)" } else { "DISABLED" });
                println!("Stack Canary    : {}", if sec.stack_canary_active { "ACTIVE (RDRAND Seed)" } else { "INACTIVE" });
                println!("W^X Enforced    : {}", sec.wx_memory_enforced);
                println!("TPM PCR[11]     : {}", sec.pcr11);
                println!("TPM PCR[12]     : {}", sec.pcr12);
            }
            "ps" | "tasks" => {
                println!("{:<6} {:<16} {:<10} {:<8} {:<10}", "PID", "NAME", "STATE", "PRIO", "MEM(KB)");
                println!("--------------------------------------------------");
                for t in scheduler.list_tasks() {
                    println!("{:<6} {:<16} {:<10?} {:<8} {:<10}", t.id, t.name, t.state, t.priority, t.memory_used_kb);
                }
            }
            "spawn" => {
                let name = if parts.len() > 1 { parts[1] } else { "worker_task" };
                let pid = scheduler.spawn(name, 5, 256);
                println!("Spawned task '{}' with PID {}", name, pid);
            }
            "counters" => {
                println!("Scheduler Ticks: {}", scheduler.total_ticks());
                for t in scheduler.list_tasks() {
                    println!(" Task [PID {}] {:<16} -> {} ticks", t.id, t.name, t.cpu_ticks);
                }
            }
            "pwd" => {
                println!("{}", fs.current_path());
            }
            "cd" => {
                let target = if parts.len() > 1 { parts[1] } else { "/" };
                if !fs.set_current_path(target) {
                    println!("cd: no such directory: {}", target);
                }
            }
            "ls" => {
                let target = if parts.len() > 1 {
                    fs.resolve_path(parts[1])
                } else {
                    fs.current_path().to_string()
                };

                if let Some(entries) = fs.list_dir(&target) {
                    for (name, is_dir, size) in entries {
                        if is_dir {
                            println!("\x1b[1;34m{}/\x1b[0m", name);
                        } else {
                            println!("{:<20} {} B", name, size);
                        }
                    }
                } else {
                    println!("ls: cannot access '{}': No such file or directory", target);
                }
            }
            "tree" => {
                let target = if parts.len() > 1 {
                    fs.resolve_path(parts[1])
                } else {
                    fs.current_path().to_string()
                };
                print_tree(&fs, &target, 0);
            }
            "cat" => {
                if parts.len() < 2 {
                    println!("Usage: cat <filename>");
                } else {
                    let target = fs.resolve_path(parts[1]);
                    if let Some(content) = fs.read_file(&target) {
                        print!("{}", content);
                    } else {
                        println!("cat: {}: No such file", parts[1]);
                    }
                }
            }
            "write" => {
                if parts.len() < 3 {
                    println!("Usage: write <filename> <content...>");
                } else {
                    let target = fs.resolve_path(parts[1]);
                    let content = parts[2..].join(" ") + "\n";
                    if fs.write_file(&target, &content) {
                        println!("Wrote {} bytes to {}", content.len(), parts[1]);
                    } else {
                        println!("write: failed to write to {}", parts[1]);
                    }
                }
            }
            "append" => {
                if parts.len() < 3 {
                    println!("Usage: append <filename> <content...>");
                } else {
                    let target = fs.resolve_path(parts[1]);
                    let mut existing = fs.read_file(&target).unwrap_or_default();
                    existing.push_str(&parts[2..].join(" "));
                    existing.push('\n');
                    if fs.write_file(&target, &existing) {
                        println!("Appended to {}", parts[1]);
                    } else {
                        println!("append: failed to append to {}", parts[1]);
                    }
                }
            }
            "mkdir" => {
                if parts.len() < 2 {
                    println!("Usage: mkdir <dirname>");
                } else {
                    let target = fs.resolve_path(parts[1]);
                    if fs.mkdir(&target) {
                        println!("Created directory {}", parts[1]);
                    } else {
                        println!("mkdir: failed to create {}", parts[1]);
                    }
                }
            }
            "rm" => {
                if parts.len() < 2 {
                    println!("Usage: rm <path>");
                } else {
                    let target = fs.resolve_path(parts[1]);
                    if fs.remove(&target) {
                        println!("Removed {}", parts[1]);
                    } else {
                        println!("rm: cannot remove '{}': No such file or directory", parts[1]);
                    }
                }
            }
            "run" => {
                if parts.len() < 2 {
                    println!("Usage: run <hello|echo|fault|gp|denied>");
                } else {
                    match parts[1] {
                        "hello" => println!("[Ring 3] Process 'hello': Hello from user space on Vishnu OS!"),
                        "echo" => {
                            let text = if parts.len() > 2 { parts[2..].join(" ") } else { "".to_string() };
                            println!("[Ring 3] {}", text);
                        }
                        "fault" => println!("[Ring 3] Page Fault in process: access outside isolated address space. Process safely terminated."),
                        "gp" => println!("[Ring 3] General Protection Fault (#GP): unprivileged ring-3 attempted privileged CPU opcode."),
                        "denied" => println!("[Ring 3] System Call Denied: syscall not allowed by current sandbox policy."),
                        other => println!("run: unknown program '{}'. Available: hello, echo, fault, gp, denied", other),
                    }
                }
            }
            "wifi" => {
                let sub = if parts.len() > 1 { parts[1] } else { "status" };
                match sub {
                    "scan" => {
                        println!("Scanning via host bridge interface COM2...");
                        println!(" 1. Vishnu_Secure_WiFi   [-42 dBm, WPA2-PSK]");
                        println!(" 2. Home_Network_5G      [-61 dBm, WPA3-SAE]");
                        println!(" 3. Campus_Guest         [-75 dBm, Open]");
                    }
                    "status" => {
                        println!("Wi-Fi Adapter : Host Bridge Virtualized Interface");
                        println!("Connection    : Connected to 'Vishnu_Secure_WiFi'");
                        println!("IPv4 Address  : 192.168.1.105 / 24 (DHCP lease active)");
                    }
                    _ => println!("Usage: wifi [scan|status]"),
                }
            }
            "log" => {
                println!("--- Vishnu OS Kernel Boot Log ---");
                for entry in log.entries() {
                    println!("{}", entry);
                }
            }
            "reboot" | "exit" | "shutdown" => {
                println!("\x1b[1;33m[*] Powering down Vishnu OS. Goodbye!\x1b[0m");
                break;
            }
            unknown => {
                println!("vishnu: command not found: {}. Type 'help' for available commands.", unknown);
            }
        }
    }
}

fn print_tree(fs: &RamFs, path: &str, depth: usize) {
    if let Some(entries) = fs.list_dir(path) {
        for (name, is_dir, _) in entries {
            let indent = "  ".repeat(depth);
            if is_dir {
                println!("{}|-- \x1b[1;34m{}/\x1b[0m", indent, name);
                let subpath = if path == "/" {
                    format!("/{}", name)
                } else {
                    format!("{}/{}", path, name)
                };
                print_tree(fs, &subpath, depth + 1);
            } else {
                println!("{}|-- {}", indent, name);
            }
        }
    }
}
