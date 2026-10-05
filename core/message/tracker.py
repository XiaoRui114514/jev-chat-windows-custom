"""Ordered overlap preserves repeated identical bubbles without coordinate IDs."""
from collections import Counter, deque

class MessageTracker:
    def __init__(self, limit=500):
        self.previous = []
        self.seen = deque(maxlen=limit)

    def new(self, messages):
        ids = [m.id for m in messages]
        old = self.previous
        overlap = 0
        # Scrolling/new messages preserve a contiguous tail-to-prefix overlap.
        for size in range(min(len(old), len(ids)), 0, -1):
            if old[-size:] == ids[:size]:
                overlap = size
                break
        if ids == old:
            new = []
        elif overlap:
            new = messages[overlap:]
        else:
            prior = Counter(self.seen)
            now = Counter()
            new = []
            for m in messages:
                now[m.id] += 1
                if now[m.id] > prior[m.id]:
                    new.append(m)
        self.previous = ids
        self.seen.extend(m.id for m in new)
        return new

