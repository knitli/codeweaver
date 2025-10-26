// SPDX-FileCopyrightText: 2025 Knitli Inc.
// SPDX-License-Identifier: MIT OR Apache-2.0

// Package fixtures provides sample Go code for testing chunker functionality.
package fixtures

import (
    "fmt"
    "sync"
    "time"
)

// Processor defines the interface for data processing operations.
type Processor interface {
    Process(item DataItem) (DataItem, error)
    ProcessBatch(items []DataItem) ([]DataItem, error)
}

// DataItem represents a single data element with metadata.
type DataItem struct {
    ID        string
    Value     int
    Timestamp time.Time
    Metadata  map[string]string
}

// Cache provides thread-safe caching with TTL support.
type Cache struct {
    mu      sync.RWMutex
    storage map[string]cacheEntry
    ttl     time.Duration
}

type cacheEntry struct {
    value     interface{}
    expiresAt time.Time
}

// NewCache creates a new cache with specified TTL.
func NewCache(ttl time.Duration) *Cache {
    return &Cache{
        storage: make(map[string]cacheEntry),
        ttl:     ttl,
    }
}

// Get retrieves a value from cache if not expired.
func (c *Cache) Get(key string) (interface{}, bool) {
    c.mu.RLock()
    defer c.mu.RUnlock()

    entry, exists := c.storage[key]
    if !exists {
        return nil, false
    }

    if time.Now().After(entry.expiresAt) {
        return nil, false
    }

    return entry.value, true
}

// Set stores a value in cache with TTL.
func (c *Cache) Set(key string, value interface{}) {
    c.mu.Lock()
    defer c.mu.Unlock()

    c.storage[key] = cacheEntry{
        value:     value,
        expiresAt: time.Now().Add(c.ttl),
    }
}

// DefaultProcessor implements the Processor interface.
type DefaultProcessor struct {
    cache      *Cache
    multiplier int
}

// NewDefaultProcessor creates a processor with caching.
func NewDefaultProcessor(multiplier int) *DefaultProcessor {
    return &DefaultProcessor{
        cache:      NewCache(5 * time.Minute),
        multiplier: multiplier,
    }
}

// Process transforms a single data item.
func (p *DefaultProcessor) Process(item DataItem) (DataItem, error) {
    if item.ID == "" {
        return DataItem{}, fmt.Errorf("missing item ID")
    }

    item.Value *= p.multiplier
    item.Timestamp = time.Now()

    return item, nil
}

// ProcessBatch processes multiple items concurrently.
func (p *DefaultProcessor) ProcessBatch(items []DataItem) ([]DataItem, error) {
    results := make([]DataItem, len(items))
    var wg sync.WaitGroup

    for i, item := range items {
        wg.Add(1)
        go func(idx int, it DataItem) {
            defer wg.Done()
            result, _ := p.Process(it)
            results[idx] = result
        }(i, item)
    }

    wg.Wait()
    return results, nil
}
─────┴──────────────────────────────────────────────────────────────────────────
