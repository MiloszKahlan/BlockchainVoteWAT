from typing import List
from models import VoteTx


class Mempool:
    def __init__(self):
        self._txs: List[VoteTx] = []

    def add(self, tx: VoteTx) -> bool:
        self._txs.append(tx)
        return True

    def remove_many(self, txs: List[VoteTx]) -> None:
        self._txs = [t for t in self._txs if t not in txs]

    def get(self, limit: int = 1000) -> List[VoteTx]:
        return self._txs[:limit]

    def clear(self) -> None:
        self._txs.clear()
