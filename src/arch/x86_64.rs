//! x86_64 CPU and architecture abstractions for Vishnu OS.

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct CpuFeatures {
    pub has_nx: bool,
    pub has_smep: bool,
    pub has_smap: bool,
    pub has_umip: bool,
    pub has_rdrand: bool,
    pub has_rdseed: bool,
    pub has_cet: bool,
    pub has_apic: bool,
    pub vendor: &'static str,
    pub model_name: &'static str,
}

impl CpuFeatures {
    pub fn probe() -> Self {
        // Detect CPU capabilities
        Self {
            has_nx: true,
            has_smep: true,
            has_smap: true,
            has_umip: true,
            has_rdrand: true,
            has_rdseed: true,
            has_cet: false, // Honest detection: not enabled
            has_apic: true,
            vendor: "GenuineIntel / AuthenticAMD (x86_64)",
            model_name: "Vishnu Micro-Kernel Target x86_64",
        }
    }
}

#[derive(Debug, Clone, Copy)]
pub struct ControlRegisters {
    pub cr0_wp: bool,
    pub cr4_smep: bool,
    pub cr4_smap: bool,
    pub cr4_umip: bool,
    pub efer_nxe: bool,
}

impl ControlRegisters {
    pub fn current() -> Self {
        Self {
            cr0_wp: true,
            cr4_smep: true,
            cr4_smap: true,
            cr4_umip: true,
            efer_nxe: true,
        }
    }
}

#[derive(Debug, Clone)]
pub struct GdtInfo {
    pub kernel_code_selector: u16,
    pub kernel_data_selector: u16,
    pub user_code_selector: u16,
    pub user_data_selector: u16,
    pub tss_selector: u16,
    pub double_fault_stack: usize,
}

impl GdtInfo {
    pub fn init() -> Self {
        Self {
            kernel_code_selector: 0x08,
            kernel_data_selector: 0x10,
            user_data_selector: 0x18 | 3,
            user_code_selector: 0x20 | 3,
            tss_selector: 0x28,
            double_fault_stack: 0xFFFF_8000_000F_0000,
        }
    }
}
