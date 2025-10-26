// SPDX-FileCopyrightText: 2025 Knitli Inc.
// SPDX-License-Identifier: MIT OR Apache-2.0

/**
 * Sample JavaScript module for testing chunker functionality.
 * Contains nested functions, closures, and class definitions.
 */

class TaskQueue {
  constructor(maxConcurrency = 5) {
    this.maxConcurrency = maxConcurrency;
    this.queue = [];
    this.running = 0;
  }

  async enqueue(task) {
    return new Promise((resolve, reject) => {
      this.queue.push({ task, resolve, reject });
      this.processNext();
    });
  }

  async processNext() {
    if (this.running >= this.maxConcurrency || this.queue.length === 0) {
      return;
    }

    this.running++;
    const { task, resolve, reject } = this.queue.shift();

    try {
      const result = await task();
      resolve(result);
    } catch (error) {
      reject(error);
    } finally {
      this.running--;
      this.processNext();
    }
  }
}

function createDataProcessor(config) {
  const cache = new Map();
  const stats = { hits: 0, misses: 0 };

  function processItem(item) {
    const cached = cache.get(item.id);
    if (cached) {
      stats.hits++;
      return cached;
    }

    stats.misses++;
    const result = {
      id: item.id,
      value: transformValue(item.value),
      timestamp: Date.now()
    };

    cache.set(item.id, result);
    return result;
  }

  function transformValue(value) {
    return config.multiplier ? value * config.multiplier : value;
  }

  function getStats() {
    return { ...stats };
  }

  return {
    process: processItem,
    stats: getStats,
    cache
  };
}

const withRetry = (fn, maxAttempts = 3) => {
  return async (...args) => {
    let lastError;
    
    for (let attempt = 1; attempt <= maxAttempts; attempt++) {
      try {
        return await fn(...args);
      } catch (error) {
        lastError = error;
        if (attempt < maxAttempts) {
          await new Promise(resolve => setTimeout(resolve, 1000 * attempt));
        }
      }
    }
    
    throw lastError;
  };
};

module.exports = { TaskQueue, createDataProcessor, withRetry };
─────┴──────────────────────────────────────────────────────────────────────────
