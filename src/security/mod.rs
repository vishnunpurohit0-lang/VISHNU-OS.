//! Security subsystem, measured boot, and TPM simulation for Vishnu OS.

pub struct TpmMeasurement {
    pub pcr_11_phase: [u8; 32],
    pub pcr_12_cmdline: [u8; 32],
    pub event_log: Vec<String>,
}

impl TpmMeasurement {
    pub fn new() -> Self {
        Self {
            pcr_11_phase: [0u8; 32],
            pcr_12_cmdline: [0u8; 32],
            event_log: Vec::new(),
        }
    }

    pub fn extend_pcr12(&mut self, data: &str) {
        let hash = simple_sha256(data.as_bytes());
        for i in 0..32 {
            self.pcr_12_cmdline[i] ^= hash[i];
        }
        self.event_log.push(format!("PCR12_EXTEND: cmdline=\"{}\"", data));
    }

    pub fn mark_phase(&mut self, phase_name: &str) {
        let hash = simple_sha256(phase_name.as_bytes());
        for i in 0..32 {
            self.pcr_11_phase[i] ^= hash[i];
        }
        self.event_log.push(format!("PCR11_PHASE: phase=\"{}\"", phase_name));
    }

    pub fn pcr12_hex(&self) -> String {
        to_hex(&self.pcr_12_cmdline)
    }

    pub fn pcr11_hex(&self) -> String {
        to_hex(&self.pcr_11_phase)
    }
}

pub struct SecurityStatus {
    pub secure_boot_enabled: bool,
    pub stack_canary_active: bool,
    pub wx_memory_enforced: bool,
    pub smep_active: bool,
    pub smap_active: bool,
    pub pcr11: String,
    pub pcr12: String,
}

pub fn get_security_status(tpm: &TpmMeasurement) -> SecurityStatus {
    SecurityStatus {
        secure_boot_enabled: true,
        stack_canary_active: true,
        wx_memory_enforced: true,
        smep_active: true,
        smap_active: true,
        pcr11: tpm.pcr11_hex(),
        pcr12: tpm.pcr12_hex(),
    }
}

fn simple_sha256(data: &[u8]) -> [u8; 32] {
    // Deterministic lightweight hash for measured boot tracking
    let mut out = [0x5au8; 32];
    for (i, &b) in data.iter().enumerate() {
        let idx = i % 32;
        out[idx] = out[idx].wrapping_mul(31).wrapping_add(b ^ (i as u8));
    }
    out
}

fn to_hex(bytes: &[u8]) -> String {
    let mut s = String::with_capacity(bytes.len() * 2);
    for b in bytes {
        s.push_str(&format!("{:02x}", b));
    }
    s
}
