import heapq
from dataclasses import dataclass, field
from typing import Optional

@dataclass(order=True)
class QueueItem:
    priority: float
    entry_id: str = field(compare=False)
    customer_id: str = field(compare=False)
    weight: float = field(compare=False, default=1.0)

class WeightedFairQueue:
    """O(log n) enqueue/dequeue using heap. Fair queuing with weights."""

    def __init__(self):
        self._heap: list = []
        self._counter: int = 0
        self._virtual_finish_times: dict[str, float] = {}

    def enqueue(self, entry_id: str, customer_id: str, weight: float = 1.0, base_priority: int = 0) -> float:
        self._counter += 1
        last_vft = self._virtual_finish_times.get(customer_id, 0.0)
        import time
        now = time.monotonic()
        vft = max(last_vft, now) + (1.0 / max(weight, 0.001)) + base_priority
        self._virtual_finish_times[customer_id] = vft
        item = (vft, self._counter, entry_id, customer_id, weight)
        heapq.heappush(self._heap, item)
        return vft

    def dequeue(self) -> Optional[tuple]:
        if not self._heap:
            return None
        vft, counter, entry_id, customer_id, weight = heapq.heappop(self._heap)
        return entry_id, customer_id, weight, vft

    def peek(self) -> Optional[str]:
        if not self._heap:
            return None
        return self._heap[0][2]

    def size(self) -> int:
        return len(self._heap)

    def remove(self, entry_id: str) -> bool:
        for i, item in enumerate(self._heap):
            if item[2] == entry_id:
                self._heap[i] = self._heap[-1]
                self._heap.pop()
                if i < len(self._heap):
                    heapq._siftup(self._heap, i)
                    heapq._siftdown(self._heap, 0, i)
                return True
        return False
