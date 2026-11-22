//! Preemptive multitasking and process control block for Vishnu OS.

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TaskState {
    Ready,
    Running,
    Sleeping,
    Terminated,
}

#[derive(Debug, Clone)]
pub struct Task {
    pub id: u32,
    pub name: String,
    pub priority: u8,
    pub state: TaskState,
    pub cpu_ticks: u64,
    pub memory_used_kb: usize,
}

pub struct Scheduler {
    tasks: Vec<Task>,
    current_index: usize,
    total_ticks: u64,
}

impl Scheduler {
    pub fn new() -> Self {
        let mut sched = Self {
            tasks: Vec::new(),
            current_index: 0,
            total_ticks: 0,
        };

        sched.tasks.push(Task {
            id: 0,
            name: "kernel_idle".to_string(),
            priority: 0,
            state: TaskState::Running,
            cpu_ticks: 0,
            memory_used_kb: 128,
        });

        sched.tasks.push(Task {
            id: 1,
            name: "shell".to_string(),
            priority: 10,
            state: TaskState::Ready,
            cpu_ticks: 0,
            memory_used_kb: 512,
        });

        sched
    }

    pub fn spawn(&mut self, name: &str, priority: u8, mem_kb: usize) -> u32 {
        let id = self.tasks.len() as u32;
        self.tasks.push(Task {
            id,
            name: name.to_string(),
            priority,
            state: TaskState::Ready,
            cpu_ticks: 0,
            memory_used_kb: mem_kb,
        });
        id
    }

    pub fn tick(&mut self) {
        self.total_ticks += 1;
        if self.tasks.is_empty() {
            return;
        }

        // Advance current task
        if self.tasks[self.current_index].state == TaskState::Running {
            self.tasks[self.current_index].cpu_ticks += 1;
            self.tasks[self.current_index].state = TaskState::Ready;
        }

        // Round-robin selection of next ready task
        for i in 1..=self.tasks.len() {
            let next_idx = (self.current_index + i) % self.tasks.len();
            if self.tasks[next_idx].state == TaskState::Ready {
                self.current_index = next_idx;
                self.tasks[self.current_index].state = TaskState::Running;
                return;
            }
        }
    }

    pub fn list_tasks(&self) -> &[Task] {
        &self.tasks
    }

    pub fn total_ticks(&self) -> u64 {
        self.total_ticks
    }
}
