use vishnu_kernel::fs::RamFs;
use vishnu_kernel::memory::{FrameAllocator, SimpleHeap};
use vishnu_kernel::security::{get_security_status, TpmMeasurement};
use vishnu_kernel::task::Scheduler;

#[test]
fn test_frame_allocator() {
    let mut alloc = FrameAllocator::new();
    assert_eq!(alloc.allocated_frames(), 0);

    let f1 = alloc.alloc_frame().expect("Alloc first frame");
    let f2 = alloc.alloc_frame().expect("Alloc second frame");
    assert_ne!(f1, f2);
    assert_eq!(alloc.allocated_frames(), 2);

    assert!(alloc.free_frame(f1));
    assert_eq!(alloc.allocated_frames(), 1);
}

#[test]
fn test_simple_heap() {
    let mut heap = SimpleHeap::new(1024 * 1024);
    let off1 = heap.allocate(128).expect("Alloc 128 bytes");
    let off2 = heap.allocate(256).expect("Alloc 256 bytes");
    assert!(off2 > off1);

    let stats = heap.stats();
    assert_eq!(stats.allocation_count, 2);
    assert!(stats.used_bytes >= 384);
}

#[test]
fn test_ramfs_operations() {
    let mut fs = RamFs::new();
    assert!(fs.is_dir("/bin"));
    assert!(fs.is_dir("/home/vishnu"));

    // Write & read test
    assert!(fs.write_file("/home/vishnu/notes.txt", "Test notes for Vishnu OS"));
    let content = fs.read_file("/home/vishnu/notes.txt");
    assert_eq!(content.as_deref(), Some("Test notes for Vishnu OS"));

    // Mkdir & remove
    assert!(fs.mkdir("/home/vishnu/projects"));
    assert!(fs.is_dir("/home/vishnu/projects"));
    assert!(fs.remove("/home/vishnu/projects"));
    assert!(!fs.is_dir("/home/vishnu/projects"));
}

#[test]
fn test_scheduler_preemption() {
    let mut sched = Scheduler::new();
    let worker_pid = sched.spawn("worker_a", 5, 256);
    assert_eq!(worker_pid, 2);

    for _ in 0..10 {
        sched.tick();
    }
    assert_eq!(sched.total_ticks(), 10);
}

#[test]
fn test_tpm_measured_boot() {
    let mut tpm = TpmMeasurement::new();
    tpm.extend_pcr12("BOOT_IMAGE=vishnu.efi quiet");
    tpm.mark_phase("STAGE_INIT");

    let sec = get_security_status(&tpm);
    assert!(sec.secure_boot_enabled);
    assert!(sec.stack_canary_active);
    assert_eq!(sec.pcr11.len(), 64);
    assert_eq!(sec.pcr12.len(), 64);
}
