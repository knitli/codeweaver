// SPDX-FileCopyrightText: 2025 Knitli Inc.
// SPDX-License-Identifier: MIT OR Apache-2.0

//! Sample Rust module for testing chunker functionality.
//! Contains traits, impls, macros, and struct definitions.

use std::collections::HashMap;
use std::fmt;

/// Trait for cacheable items
pub trait Cacheable {
    fn cache_key(&self) -> String;
    fn is_valid(&self) -> bool;
}

/// Data item with identifier and value
#[derive(Debug, Clone)]
pub struct DataItem {
    pub id: String,
    pub value: i32,
    pub metadata: HashMap<String, String>,
}

impl Cacheable for DataItem {
    fn cache_key(&self) -> String {
        format!("item:{}", self.id)
    }

    fn is_valid(&self) -> bool {
        !self.id.is_empty() && self.value >= 0
    }
}

impl fmt::Display for DataItem {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "DataItem(id={}, value={})", self.id, self.value)
    }
}

/// Generic cache with type parameter
pub struct Cache<T> {
    storage: HashMap<String, T>,
    max_size: usize,
}

impl<T: Cacheable> Cache<T> {
    pub fn new(max_size: usize) -> Self {
        Cache {
            storage: HashMap::new(),
            max_size,
        }
    }

    pub fn insert(&mut self, item: T) -> Option<T> {
        if self.storage.len() >= self.max_size {
            return None;
        }
        self.storage.insert(item.cache_key(), item)
    }

    pub fn get(&self, key: &str) -> Option<&T> {
        self.storage.get(key)
    }

    pub fn remove(&mut self, key: &str) -> Option<T> {
        self.storage.remove(key)
    }
}

/// Macro for creating data items
#[macro_export]
macro_rules! data_item {
    ($id:expr, $value:expr) => {
        DataItem {
            id: $id.to_string(),
            value: $value,
            metadata: HashMap::new(),
        }
    };
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_cache_operations() {
        let mut cache = Cache::new(10);
        let item = data_item!("test", 42);
        assert!(cache.insert(item).is_none());
    }
}
─────┴──────────────────────────────────────────────────────────────────────────
