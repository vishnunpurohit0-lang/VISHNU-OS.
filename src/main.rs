use std::io::{self, BufRead, Write};
use std::thread;
use std::time::Duration;

use vishnu_kernel::arch::x86_64::CpuFeatures;
use vishnu_kernel::fs::RamFs;
use vishnu_kernel::memory::{FrameAllocator, SimpleHeap};
use vishnu_kernel::security::{get_security_status, TpmMeasurement};
use vishnu_kernel::task::{Scheduler, TaskState};
use vishnu_kernel::{KernelRingLog, KERNEL_NAME, KERNEL_VERSION};

#[derive(Clone, Copy)]
enum Theme {
    NeonCyan,
    MatrixGreen,
    AmberRetro,
    DeepPurple,
}

impl Theme {
    fn primary(&self) -> &'static str {
        match self {
            Theme::NeonCyan => "\x1b[1;36m",
            Theme::MatrixGreen => "\x1b[1;32m",
            Theme::AmberRetro => "\x1b[1;33m",
            Theme::DeepPurple => "\x1b[1;35m",
        }
    }

    fn secondary(&self) -> &'static str {
        match self {
            Theme::NeonCyan => "\x1b[1;34m",
            Theme::MatrixGreen => "\x1b[0;32m",
            Theme::AmberRetro => "\x1b[0;33m",
            Theme::DeepPurple => "\x1b[0;35m",
        }
    }

    fn prompt_user(&self) -> &'static str {
        match self {
            Theme::NeonCyan => "\x1b[1;32m",
            Theme::MatrixGreen => "\x1b[1;32m",
            Theme::AmberRetro => "\x1b[1;33m",
            Theme::DeepPurple => "\x1b[1;35m",
        }
    }
}

fn print_logo(theme: Theme) {
    let p = theme.primary();
    println!("{}", p);
    println!(r#"  ==============================================================="#);
    println!(r#"  *      __     ___     _                 ___  ____             *"#);
    println!(r#"  *      \ \   / (_)___| |__  _ __  _   _/ _ \/ ___|            *"#);
    println!(r#"  *       \ \ / /| / __| '_ \| '_ \| | | | | | \___ \            *"#);
    println!(r#"  *        \ V / | \__ \ | | | | | | |_| | |_| |___) |           *"#);
    println!(r#"  *         \_/  |_|___/_| |_|_| |_|\__,_|\___/|____/            *"#);
    println!(r#"  *                                                             *"#);
    println!(r#"  *             V I S H N U   M I C R O - O S                   *"#);
    println!(r#"  *          x86_64 UEFI Preemptive Kernel v0.11.0               *"#);
    println!(r#"  *        Engineered by Vishnu | Safe Bare-Metal Rust          *"#);
    println!(r#"  ==============================================================="#);
    println!("\x1b[0m");
}

fn boot_manager_menu(theme: Theme) {
    println!("{}╔════════════════════════════════════════════════════════════════╗", theme.secondary());
    println!("║             SURYAN / VISHNU BOOT MANAGER v2.4                  ║");
    println!("╠════════════════════════════════════════════════════════════════╣");
    println!("║  [>] 1. Boot Vishnu OS (Standard Preemptive Multitasking Kernel)║");
    println!("║      2. Vishnu Recovery Console & Diagnostic Mode              ║");
    println!("║      3. UEFI Firmware Shell (Pre-Boot Direct Input)            ║");
    println!("║      4. Hardware Memory & TPM 2.0 PCR Integrity Audit          ║");
    println!("║      5. ACPI Power Management & Hardware Reset                 ║");
    println!("╚════════════════════════════════════════════════════════════════╝\x1b[0m");
    println!("Default boot option [1] selected. Initializing kernel in 1 second...\n");
    thread::sleep(Duration::from_millis(600));
}

fn boot_sequence(log: &mut KernelRingLog, tpm: &mut TpmMeasurement, theme: Theme) {
    println!("{}--- [SYSTEM BOOT INITIALIZATION] ---{}\x1b[0m", theme.primary(), "\x1b[0m");

    let stages = [
        ("firmware-entry", "Watchdog disabled, calibrating TSC timer (3.20 GHz)"),
        ("early-init", "GOP Framebuffer 1920x1080 32bpp mapped, GDT/IDT initialized"),
        ("platform-disc", "ACPI RSDP 2.0 verified, SMBIOS 3.3.0, SecureBoot=Enrolled"),
        ("security-init", "TPM PCR[12] extended with cmdline, RDRAND entropy seeded"),
        ("exit-boot-serv", "Firmware boot services exited, PCR[11] phase sealed"),
        ("kernel-env", "W^X page tables enforced, CR0.WP=1, SMEP=1, SMAP=1"),
        ("kernel-memory", "Physical frame allocator online (64 MB), 32 MB heap ready"),
        ("kernel-tasks", "Round-robin preemptive scheduler active, spawning ring-0 tasks"),
    ];

    for (i, (stage, desc)) in stages.iter().enumerate() {
        let pct = (i + 1) * 100 / stages.len();
        log.log(stage, desc);

        let progress_bars = (pct / 5) as usize;
        let bar: String = "█".repeat(progress_bars) + &"░".repeat(20 - progress_bars);

        println!(" [0.00{:04}] [{}] [{:<16}] {}",
            (i + 1) * 25,
            format!("\x1b[1;32m{}\x1b[0m", bar),
            stage,
            desc
        );
        thread::sleep(Duration::from_millis(60));
    }

    tpm.extend_pcr12("BOOT_IMAGE=vishnu.efi quiet mode=1920x1080");
    tpm.mark_phase("KERNEL_SHELL_READY");

    println!("\x1b[1;32m\n[✓] Vishnu OS Kernel initialized successfully!\x1b[0m\n");
}

fn show_fetch(theme: Theme, sched: &Scheduler, heap: &SimpleHeap, frames: &FrameAllocator) {
    let p = theme.primary();
    let s = theme.secondary();
    let h_stats = heap.stats();

    println!("{p}      __     ___     _                 ___  ____      {s}vishnu@kernel{p}");
    println!("{p}      \\ \\   / (_)___| |__  _ __  _   _/ _ \\/ ___|     {s}-------------{p}");
    println!("{p}       \\ \\ / /| / __| '_ \\| '_ \\| | | | | | \\___ \\     {s}OS: {p}Vishnu OS x86_64{p}");
    println!("{p}        \\ V / | \\__ \\ | | | | | | |_| | |_| |___) |    {s}Kernel: {p}Rust no_std micro-kernel v0.11.0{p}");
    println!("{p}         \\_/  |_|___/_| |_|_| |_|\\__,_|\\___/|____/     {s}Uptime: {p}{} ticks (~{:.1}s){p}",
        sched.total_ticks(), sched.total_ticks() as f64 * 0.05);
    println!("{p}                                                       {s}Shell: {p}vishnu-sh 1.2{p}");
    println!("{p}                                                       {s}Resolution: {p}1920x1080 GOP Framebuffer{p}");
    println!("{p}                                                       {s}Tasks: {p}{} active{p}",
        sched.list_tasks().len());
    println!("{p}                                                       {s}Memory: {p}{} KiB / {} KiB ({:.1}%){p}",
        h_stats.used_bytes / 1024, h_stats.total_bytes / 1024,
        (h_stats.used_bytes as f64 / h_stats.total_bytes as f64) * 100.0);
    println!("{p}                                                       {s}Frames: {p}{}/16384 used{p}",
        frames.allocated_frames());
    println!("{p}                                                       {s}Security: {p}TPM 2.0 (PCR 11/12) + W^X{p}");
    println!("\x1b[0m");
}

fn show_top(sched: &Scheduler, heap: &SimpleHeap, frames: &FrameAllocator) {
    println!("\x1b[1;36m=== Vishnu OS Real-Time Task Monitor (top) ===\x1b[0m");
    println!("Scheduler Ticks: {} | Context Switches: {}", sched.total_ticks(), sched.total_ticks() * 2);
    let h_stats = heap.stats();
    println!("Mem: {}K used, {}K free | Frames: {} allocated, {} free\n",
        h_stats.used_bytes / 1024, h_stats.free_bytes / 1024,
        frames.allocated_frames(), frames.free_frames());

    println!("\x1b[1;37m{:<6} {:<16} {:<10} {:<6} {:<10} {:<12}\x1b[0m",
        "PID", "COMMAND", "STATE", "PRIO", "MEM(KB)", "CPU_TICKS");
    println!("------------------------------------------------------------------");
    for t in sched.list_tasks() {
        let state_col = match t.state {
            TaskState::Running => "\x1b[1;32mRUNNING   \x1b[0m",
            TaskState::Ready => "\x1b[1;34mREADY     \x1b[0m",
            TaskState::Sleeping => "\x1b[0;33mSLEEPING  \x1b[0m",
            TaskState::Terminated => "\x1b[0;31mTERMINATED\x1b[0m",
        };
        println!("{:<6} {:<16} {} {:<6} {:<10} {:<12}",
            t.id, t.name, state_col, t.priority, t.memory_used_kb, t.cpu_ticks);
    }
}

fn run_matrix_effect() {
    println!("\x1b[1;32m[Entering Matrix stream - press any key simulation]\x1b[0m");
    let streams = [
        "0 1 1 0 1 0 0 1 0 1 1 1 0 1 0 1 0 0 1 1",
        "V I S H N U - O S - K E R N E L - R U S T",
        "1 0 0 1 0 1 1 0 1 0 0 1 0 1 1 0 1 1 0 1",
        "W ^ X   P A G I N G   A C T I V E   O K ",
        "0 0 1 1 0 1 0 1 0 1 1 0 1 0 0 1 0 1 1 0",
        "T P M   P C R 1 2   M E A S U R E D     ",
    ];
    for s in streams.iter().cycle().take(12) {
        println!("\x1b[0;32m    {}    {}\x1b[0m", s, s);
        thread::sleep(Duration::from_millis(50));
    }
    println!("\x1b[1;32m[Matrix stream paused]\x1b[0m\n");
}

fn run_calc(expr: &[&str]) {
    if expr.is_empty() {
        println!("Usage: calc <number> <+|-|*|/> <number>");
        return;
    }
    if expr.len() == 3 {
        let n1: Result<f64, _> = expr[0].parse();
        let op = expr[1];
        let n2: Result<f64, _> = expr[2].parse();

        if let (Ok(a), Ok(b)) = (n1, n2) {
            match op {
                "+" => println!("= {}", a + b),
                "-" => println!("= {}", a - b),
                "*" | "x" => println!("= {}", a * b),
                "/" => {
                    if b == 0.0 {
                        println!("Error: Division by zero");
                    } else {
                        println!("= {}", a / b);
                    }
                }
                _ => println!("Unknown operator '{}'. Use +, -, *, /", op),
            }
            return;
        }
    }
    println!("Usage: calc <number> <operator> <number> (e.g. calc 1024 * 64)");
}

fn run_text_editor(fs: &mut RamFs, file_path: &str, reader: &mut impl BufRead) {
    let target = fs.resolve_path(file_path);
    let mut buffer: Vec<String> = if let Some(content) = fs.read_file(&target) {
        content.lines().map(|s| s.to_string()).collect()
    } else {
        Vec::new()
    };

    println!("\x1b[1;33m--- Vishnu OS Text Editor (nano-lite) ---\x1b[0m");
    println!("Editing file: \x1b[1;36m{}\x1b[0m", target);
    println!("Commands: \x1b[1;32m:w\x1b[0m (save), \x1b[1;32m:q\x1b[0m (quit), \x1b[1;32m:wq\x1b[0m (save & quit), \x1b[1;32m:d <line#>\x1b[0m (delete line)\n");

    loop {
        // Display file content with line numbers
        if buffer.is_empty() {
            println!("  \x1b[0;90m[Empty file. Type lines to add content.]\x1b[0m");
        } else {
            for (idx, line) in buffer.iter().enumerate() {
                println!("{:>3} | {}", idx + 1, line);
            }
        }

        print!("\x1b[1;32medit>\x1b[0m ");
        io::stdout().flush().unwrap();

        let mut input = String::new();
        if reader.read_line(&mut input).unwrap_or(0) == 0 {
            break;
        }

        let line_trimmed = input.trim_end();
        if line_trimmed == ":q" {
            println!("Exited without saving.");
            break;
        } else if line_trimmed == ":w" {
            let content = buffer.join("\n") + "\n";
            fs.write_file(&target, &content);
            println!("Saved {} bytes to {}", content.len(), target);
        } else if line_trimmed == ":wq" {
            let content = buffer.join("\n") + "\n";
            fs.write_file(&target, &content);
            println!("Saved {} bytes to {}. Exited editor.", content.len(), target);
            break;
        } else if line_trimmed.starts_with(":d ") {
            let line_num: Result<usize, _> = line_trimmed[3..].trim().parse();
            if let Ok(num) = line_num {
                if num >= 1 && num <= buffer.len() {
                    buffer.remove(num - 1);
                    println!("Line {} deleted.", num);
                } else {
                    println!("Invalid line number.");
                }
            }
        } else {
            buffer.push(line_trimmed.to_string());
        }
    }
}

fn print_help() {
    println!("\x1b[1;36m===============================================================");
    println!("                 VISHNU OS COMMAND REFERENCE                   ");
    println!("===============================================================\x1b[0m");
    println!("\x1b[1;33m[System & Diagnostics]\x1b[0m");
    println!("  fetch / neofetch     - Show ASCII system insignia and status dashboard");
    println!("  top / htop           - Interactive real-time task manager");
    println!("  uname / version      - Display kernel architecture & version");
    println!("  uptime               - Show scheduler ticks and clock metrics");
    println!("  cpuinfo              - Inspect x86_64 security extensions (SMEP/SMAP/NX)");
    println!("  meminfo / df         - Frame allocator and virtual heap statistics");
    println!("  security / tpm       - View TPM 2.0 PCR[11]/PCR[12] & SecureBoot status");
    println!("  log                  - Print kernel ring buffer boot log");
    println!();
    println!("\x1b[1;33m[Process & Multitasking]\x1b[0m");
    println!("  ps / tasks           - List all active task control blocks");
    println!("  spawn <name>         - Spawn a worker task to test preemptive scheduling");
    println!("  counters             - Show per-task preemption ticks");
    println!("  run <prog>           - Run isolated Ring-3 program (hello, fault, gp, denied)");
    println!();
    println!("\x1b[1;33m[File Management (RamFS)]\x1b[0m");
    println!("  ls [path]            - List folder contents");
    println!("  tree [path]          - Recursive visual directory tree");
    println!("  cd <path>            - Change directory");
    println!("  pwd                  - Print current working directory");
    println!("  cat <file>           - Display text file");
    println!("  write <file> <text>  - Write line to file");
    println!("  append <file> <text> - Append text to file");
    println!("  edit <file>          - Launch interactive nano-lite text editor");
    println!("  mkdir <path>         - Create directory");
    println!("  rm <path>            - Delete file or folder");
    println!();
    println!("\x1b[1;33m[Utilities & Customization]\x1b[0m");
    println!("  calc <a +|-|*|/ b>   - Arithmetic expression evaluator");
    println!("  theme <cyan|green|amber|purple> - Change OS terminal UI theme");
    println!("  matrix               - Digital falling code visualizer");
    println!("  wifi [scan|status]   - Wi-Fi bridge adapter interface");
    println!("  clear / cls          - Clear screen");
    println!("  reboot / exit        - Gracefully shutdown Vishnu OS");
}

fn main() {
    let mut theme = Theme::NeonCyan;
    print_logo(theme);

    let mut log = KernelRingLog::new();
    let mut tpm = TpmMeasurement::new();
    let mut frames = FrameAllocator::new();
    let mut heap = SimpleHeap::new(32 * 1024 * 1024); // 32 MB heap
    let mut scheduler = Scheduler::new();
    let mut fs = RamFs::new();
    let cpu = CpuFeatures::probe();

    // Allocate initial kernel frames and heap blocks
    for _ in 0..128 {
        frames.alloc_frame();
    }
    heap.allocate(512 * 1024);

    boot_manager_menu(theme);
    boot_sequence(&mut log, &mut tpm, theme);

    // Automated non-interactive check
    let args: Vec<String> = std::env::args().collect();
    if args.contains(&"--test-boot".to_string()) {
        println!("Test boot successful. Vishnu OS ready.");
        return;
    }

    let stdin = io::stdin();
    let mut reader = stdin.lock();

    show_fetch(theme, &scheduler, &heap, &frames);
    println!("Type \x1b[1;33mhelp\x1b[0m for commands, \x1b[1;33mtop\x1b[0m for process monitor, or \x1b[1;33mexit\x1b[0m to quit.\n");

    loop {
        // Scheduler ticks on each loop cycle
        scheduler.tick();

        print!("{p}vishnu\x1b[0m@{p}kernel\x1b[0m:{s}{path}\x1b[0m# ",
            p = theme.prompt_user(),
            s = theme.secondary(),
            path = fs.current_path()
        );
        io::stdout().flush().unwrap();

        let mut line = String::new();
        if reader.read_line(&mut line).unwrap_or(0) == 0 {
            break;
        }

        let trimmed = line.trim();
        if trimmed.is_empty() {
            continue;
        }

        let parts: Vec<&str> = trimmed.split_whitespace().collect();
        let cmd = parts[0];

        match cmd {
            "help" => print_help(),
            "fetch" | "neofetch" => show_fetch(theme, &scheduler, &heap, &frames),
            "top" | "htop" => show_top(&scheduler, &heap, &frames),
            "matrix" => run_matrix_effect(),
            "calc" => run_calc(&parts[1..]),
            "edit" | "nano" => {
                if parts.len() < 2 {
                    println!("Usage: edit <filename>");
                } else {
                    run_text_editor(&mut fs, parts[1], &mut reader);
                }
            }
            "theme" => {
                if parts.len() > 1 {
                    match parts[1] {
                        "cyan" | "neon" => {
                            theme = Theme::NeonCyan;
                            println!("Theme switched to Neon Cyan.");
                        }
                        "green" | "matrix" => {
                            theme = Theme::MatrixGreen;
                            println!("Theme switched to Matrix Green.");
                        }
                        "amber" | "retro" => {
                            theme = Theme::AmberRetro;
                            println!("Theme switched to Amber Retro.");
                        }
                        "purple" => {
                            theme = Theme::DeepPurple;
                            println!("Theme switched to Deep Purple.");
                        }
                        _ => println!("Unknown theme. Choose: cyan, green, amber, purple"),
                    }
                } else {
                    println!("Usage: theme <cyan|green|amber|purple>");
                }
            }
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
                            println!("{}{}/ \x1b[0m", theme.secondary(), name);
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
                print_tree(&fs, &target, 0, theme);
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

fn print_tree(fs: &RamFs, path: &str, depth: usize, theme: Theme) {
    if let Some(entries) = fs.list_dir(path) {
        for (name, is_dir, _) in entries {
            let indent = "  ".repeat(depth);
            if is_dir {
                println!("{}|-- {}{}/\x1b[0m", indent, theme.secondary(), name);
                let subpath = if path == "/" {
                    format!("/{}", name)
                } else {
                    format!("{}/{}", path, name)
                };
                print_tree(fs, &subpath, depth + 1, theme);
            } else {
                println!("{}|-- {}", indent, name);
            }
        }
    }
}
