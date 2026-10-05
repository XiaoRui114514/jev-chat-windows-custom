"""Bounded in-memory TTL/LRU; keys never contain chat text or secrets."""
import time
from collections import OrderedDict
from threading import RLock
from copy import deepcopy

class TTLCache:
    def __init__(self, limit=128, ttl=600, clock=time.monotonic):
        self.limit, self.ttl, self.clock = limit, ttl, clock
        self.items = OrderedDict()
        self.lock = RLock()

    def get(self, key):
        with self.lock:
            item = self.items.get(key)
            if item is None:
                return None
            if self.clock()-item[0] > self.ttl:
                del self.items[key]
                return None
            self.items.move_to_end(key)
            return deepcopy(item[1])

    def put(self, key, value):
        with self.lock:
            self.items[key] = (self.clock(), deepcopy(value))
            self.items.move_to_end(key)
            while len(self.items) > self.limit:
                self.items.popitem(last=False)

