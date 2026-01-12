from typing import List
from crypto import sha256


def get_merkle_root(hashes: List[str]) -> str:
    """
    Oblicza Merkle Root dla listy hashy transakcji.

    Args:
        hashes (List[str]): Lista hashy transakcji (w formacie hex).

    Returns:
        str: Merkle Root (hex).
    """
    if not hashes:
        return sha256(b"")

    current_layer = hashes[:]

    while len(current_layer) > 1:
        next_layer = []

        for i in range(0, len(current_layer), 2):
            left = current_layer[i]

            if i + 1 < len(current_layer):
                right = current_layer[i + 1]
            else:
                right = left

            combined_hash = sha256((left + right).encode())
            next_layer.append(combined_hash)

        current_layer = next_layer

    return current_layer[0]
