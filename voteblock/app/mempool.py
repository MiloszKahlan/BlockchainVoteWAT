from typing import List
from models import VoteTx

class Mempool:
    """Zarządza buforem niezatwierdzonych transakcji."""
    
    def __init__(self):
        self._txs: List[VoteTx] = []

    def add(self, tx: VoteTx) -> bool:
        """Dodaje transakcję do Mempoola, weryfikując duplikaty nonce wewnątrz bufora."""
        for existing in self._txs:
            if existing.voter_pubkey == tx.voter_pubkey and existing.nonce == tx.nonce:
                return False 
        
        self._txs.append(tx)
        return True

    def remove_many(self, txs: List[VoteTx]) -> None:
        """Usuwa zatwierdzone transakcje z Mempoola."""
        self._txs = [t for t in self._txs if t not in txs]

    def get(self, limit: int = 1000) -> List[VoteTx]:
        """Pobiera transakcje oczekujące na dodanie do bloku."""
        return self._txs[:limit]
    
    def clear(self) -> None:
        """Opróżnia Mempool (używane głównie w testach i podczas awaryjnego czyszczenia)."""
        self._txs.clear()