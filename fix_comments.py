import threading

class Helper:
    _lock = threading.RLock()

    def _invalidate_cache(self) -> None:
        with self._lock:
            self.__dict__.pop("total_operations", None)
            self.__dict__.pop("unique_files", None)
            self.__dict__.pop("operations_with_semantic_support", None)
