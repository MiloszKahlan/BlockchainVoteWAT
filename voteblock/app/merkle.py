from typing import List
from crypto import sha256

def get_merkle_root(hashes: List[str]) -> str:
    """Wylicza korzeń drzewa Merkle'a (Merkle Root) dla podanej listy skrótów."""
    if not hashes:
        return sha256(b"")

    current_layer = hashes[:]
    while len(current_layer) > 1:
        next_layer = []
        for i in range(0, len(current_layer), 2):
            left = current_layer[i]
            right = current_layer[i + 1] if i + 1 < len(current_layer) else left
            next_layer.append(sha256((left + right).encode()))
        current_layer = next_layer
    return current_layer[0]

def get_merkle_proof(hashes: List[str], index: int) -> List[str]:
    """Generuje dowód przynależności (Merkle Proof) dla elementu o wskazanym indeksie."""
    proof = []
    current_layer = hashes[:]
    
    while len(current_layer) > 1:
        if len(current_layer) % 2 != 0:
            current_layer.append(current_layer[-1])
            
        next_layer = []
        for i in range(0, len(current_layer), 2):
            if i <= index <= i + 1:
                neighbor_idx = i + 1 if index == i else i
                proof.append(current_layer[neighbor_idx])
            
            combined = sha256((current_layer[i] + current_layer[i+1]).encode())
            next_layer.append(combined)
        
        current_layer = next_layer
        index //= 2
    return proof

def verify_merkle_proof(leaf_hash: str, proof: List[str], root: str, index: int) -> bool:
    """Weryfikuje matematyczną poprawność dowodu Merkle'a względem skrótu korzenia."""
    current_hash = leaf_hash
    for neighbor in proof:
        if index % 2 == 0:
            current_hash = sha256((current_hash + neighbor).encode())
        else:
            current_hash = sha256((neighbor + current_hash).encode())
        index //= 2
    return current_hash == root