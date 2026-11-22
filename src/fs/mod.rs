//! RamFS in-memory filesystem implementation for Vishnu OS.

use std::collections::BTreeMap;

#[derive(Debug, Clone)]
pub enum FsNode {
    File {
        content: String,
        created_at: u64,
        modified_at: u64,
    },
    Directory {
        children: BTreeMap<String, FsNode>,
    },
}

pub struct RamFs {
    root: FsNode,
    current_path: String,
}

impl RamFs {
    pub fn new() -> Self {
        let mut fs = Self {
            root: FsNode::Directory {
                children: BTreeMap::new(),
            },
            current_path: "/".to_string(),
        };

        // Standard hierarchy
        fs.mkdir("/bin");
        fs.mkdir("/etc");
        fs.mkdir("/home");
        fs.mkdir("/home/vishnu");
        fs.mkdir("/docs");

        fs.write_file(
            "/etc/os-release",
            "NAME=\"Vishnu OS\"\nVERSION=\"0.11.0\"\nID=vishnu\nKERNEL=micro-rust\nARCH=x86_64\n",
        );

        fs.write_file(
            "/home/vishnu/welcome.txt",
            "Welcome to Vishnu OS!\nA secure, modern x86_64 Micro-OS written in safe Rust.\nType 'help' to see available commands.\n",
        );

        fs.write_file(
            "/bin/hello",
            "[ELF-Micro Executable] Built-in user binary: prints greeting.\n",
        );

        fs
    }

    pub fn current_path(&self) -> &str {
        &self.current_path
    }

    pub fn set_current_path(&mut self, path: &str) -> bool {
        let target = self.resolve_path(path);
        if self.is_dir(&target) {
            self.current_path = target;
            true
        } else {
            false
        }
    }

    pub fn resolve_path(&self, path: &str) -> String {
        if path.starts_with('/') {
            normalize_path(path)
        } else if self.current_path == "/" {
            normalize_path(&format!("/{}", path))
        } else {
            normalize_path(&format!("{}/{}", self.current_path, path))
        }
    }

    pub fn is_dir(&self, abs_path: &str) -> bool {
        let parts: Vec<&str> = abs_path.split('/').filter(|p| !p.is_empty()).collect();
        let mut curr = &self.root;

        for part in parts {
            match curr {
                FsNode::Directory { children } => {
                    if let Some(child) = children.get(part) {
                        curr = child;
                    } else {
                        return false;
                    }
                }
                FsNode::File { .. } => return false,
            }
        }
        matches!(curr, FsNode::Directory { .. })
    }

    pub fn list_dir(&self, abs_path: &str) -> Option<Vec<(String, bool, usize)>> {
        let parts: Vec<&str> = abs_path.split('/').filter(|p| !p.is_empty()).collect();
        let mut curr = &self.root;

        for part in parts {
            match curr {
                FsNode::Directory { children } => {
                    curr = children.get(part)?;
                }
                FsNode::File { .. } => return None,
            }
        }

        match curr {
            FsNode::Directory { children } => {
                let mut list = Vec::new();
                for (name, node) in children {
                    match node {
                        FsNode::Directory { .. } => list.push((name.clone(), true, 0)),
                        FsNode::File { content, .. } => list.push((name.clone(), false, content.len())),
                    }
                }
                Some(list)
            }
            _ => None,
        }
    }

    pub fn mkdir(&mut self, abs_path: &str) -> bool {
        let parts: Vec<&str> = abs_path.split('/').filter(|p| !p.is_empty()).collect();
        if parts.is_empty() {
            return true;
        }

        let mut curr = &mut self.root;
        for part in parts {
            match curr {
                FsNode::Directory { children } => {
                    curr = children.entry(part.to_string()).or_insert_with(|| {
                        FsNode::Directory {
                            children: BTreeMap::new(),
                        }
                    });
                }
                FsNode::File { .. } => return false,
            }
        }
        true
    }

    pub fn write_file(&mut self, abs_path: &str, content: &str) -> bool {
        let parts: Vec<&str> = abs_path.split('/').filter(|p| !p.is_empty()).collect();
        if parts.is_empty() {
            return false;
        }

        let dir_parts = &parts[..parts.len() - 1];
        let file_name = parts[parts.len() - 1];

        let mut curr = &mut self.root;
        for part in dir_parts {
            match curr {
                FsNode::Directory { children } => {
                    curr = children.entry(part.to_string()).or_insert_with(|| {
                        FsNode::Directory {
                            children: BTreeMap::new(),
                        }
                    });
                }
                FsNode::File { .. } => return false,
            }
        }

        match curr {
            FsNode::Directory { children } => {
                children.insert(
                    file_name.to_string(),
                    FsNode::File {
                        content: content.to_string(),
                        created_at: 1,
                        modified_at: 1,
                    },
                );
                true
            }
            FsNode::File { .. } => false,
        }
    }

    pub fn read_file(&self, abs_path: &str) -> Option<String> {
        let parts: Vec<&str> = abs_path.split('/').filter(|p| !p.is_empty()).collect();
        if parts.is_empty() {
            return None;
        }

        let mut curr = &self.root;
        for part in parts {
            match curr {
                FsNode::Directory { children } => {
                    curr = children.get(part)?;
                }
                FsNode::File { .. } => return None,
            }
        }

        match curr {
            FsNode::File { content, .. } => Some(content.clone()),
            FsNode::Directory { .. } => None,
        }
    }

    pub fn remove(&mut self, abs_path: &str) -> bool {
        let parts: Vec<&str> = abs_path.split('/').filter(|p| !p.is_empty()).collect();
        if parts.is_empty() {
            return false;
        }

        let dir_parts = &parts[..parts.len() - 1];
        let target_name = parts[parts.len() - 1];

        let mut curr = &mut self.root;
        for &part in dir_parts {
            match curr {
                FsNode::Directory { children } => {
                    if let Some(next) = children.get_mut(part) {
                        curr = next;
                    } else {
                        return false;
                    }
                }
                FsNode::File { .. } => return false,
            }
        }

        match curr {
            FsNode::Directory { children } => children.remove(target_name).is_some(),
            FsNode::File { .. } => false,
        }
    }
}

fn normalize_path(path: &str) -> String {
    let mut stack = Vec::new();
    for seg in path.split('/') {
        if seg.is_empty() || seg == "." {
            continue;
        } else if seg == ".." {
            stack.pop();
        } else {
            stack.push(seg);
        }
    }
    if stack.is_empty() {
        "/".to_string()
    } else {
        format!("/{}", stack.join("/"))
    }
}
