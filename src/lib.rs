//! Vishnu OS - Educational Micro-Kernel in Rust
//! Designed for x86_64 UEFI and modular experimentation.

pub mod arch;
pub mod fs;
pub mod memory;
pub mod security;
pub mod task;

pub const KERNEL_NAME: &str = "Vishnu OS";
pub const KERNEL_VERSION: &str = "0.11.0";
pub const KERNEL_ARCH: &str = "x86_64";

pub struct KernelRingLog {
    entries: Vec<String>,
}

impl KernelRingLog {
    pub fn new() -> Self {
        Self {
            entries: Vec::new(),
        }
    }

    pub fn log(&mut self, stage: &str, msg: &str) {
        let entry = format!("[BOOT::{:<16}] {}", stage, msg);
        self.entries.push(entry);
    }

    pub fn entries(&self) -> &[String] {
        &self.entries
    }
}
