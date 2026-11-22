//! Physical and virtual memory management for Vishnu OS.

pub const PAGE_SIZE: usize = 4096;
pub const TOTAL_MEMORY_FRAMES: usize = 16384; // 64 MB physical memory

pub struct FrameAllocator {
    bitmap: [u64; TOTAL_MEMORY_FRAMES / 64],
    allocated_count: usize,
}

impl FrameAllocator {
    pub fn new() -> Self {
        Self {
            bitmap: [0; TOTAL_MEMORY_FRAMES / 64],
            allocated_count: 0,
        }
    }

    pub fn alloc_frame(&mut self) -> Option<usize> {
        for (i, word) in self.bitmap.iter_mut().enumerate() {
            if *word != u64::MAX {
                let bit = (!*word).trailing_zeros() as usize;
                *word |= 1 << bit;
                self.allocated_count += 1;
                return Some(i * 64 + bit);
            }
        }
        None
    }

    pub fn free_frame(&mut self, frame_idx: usize) -> bool {
        if frame_idx >= TOTAL_MEMORY_FRAMES {
            return false;
        }
        let word_idx = frame_idx / 64;
        let bit = frame_idx % 64;
        if (self.bitmap[word_idx] & (1 << bit)) != 0 {
            self.bitmap[word_idx] &= !(1 << bit);
            self.allocated_count -= 1;
            true
        } else {
            false
        }
    }

    pub fn allocated_frames(&self) -> usize {
        self.allocated_count
    }

    pub fn free_frames(&self) -> usize {
        TOTAL_MEMORY_FRAMES - self.allocated_count
    }
}

pub struct HeapStats {
    pub total_bytes: usize,
    pub used_bytes: usize,
    pub free_bytes: usize,
    pub allocation_count: usize,
}

pub struct SimpleHeap {
    total_size: usize,
    used: usize,
    alloc_count: usize,
}

impl SimpleHeap {
    pub fn new(size: usize) -> Self {
        Self {
            total_size: size,
            used: 0,
            alloc_count: 0,
        }
    }

    pub fn allocate(&mut self, size: usize) -> Option<usize> {
        let aligned_size = (size + 15) & !15;
        if self.used + aligned_size <= self.total_size {
            let offset = self.used;
            self.used += aligned_size;
            self.alloc_count += 1;
            Some(offset)
        } else {
            None
        }
    }

    pub fn stats(&self) -> HeapStats {
        HeapStats {
            total_bytes: self.total_size,
            used_bytes: self.used,
            free_bytes: self.total_size.saturating_sub(self.used),
            allocation_count: self.alloc_count,
        }
    }
}
