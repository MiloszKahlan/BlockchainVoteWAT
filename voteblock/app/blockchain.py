import json
import time
from typing import Tuple
from models import VoteTx, Block
from state import ChainState
from mempool import Mempool
from crypto import sha256, verify
from merkle import get_merkle_root


def _tx_payload(tx: VoteTx) -> bytes:
    """Zwraca dane transakcji w formie bajtów do haszowania i podpisywania."""
    d = {
        "election_id": tx.election_id,
        "voter_pubkey": tx.voter_pubkey,
        "candidate_id": tx.candidate_id,
        "nonce": tx.nonce,
        "timestamp": tx.timestamp,
    }
    return json.dumps(d, sort_keys=True).encode()


def _hash_tx(tx: VoteTx) -> str:
    return sha256(_tx_payload(tx))


class Blockchain:
    def __init__(self, state: ChainState, mempool: Mempool):
        self.state = state
        self.mempool = mempool
        self.current_election_id = None 

    def validate_tx(self, tx: VoteTx) -> Tuple[bool, str]:
        """
        Waliduje transakcję pod kątem kryptograficznym i logicznym.
        Uwzględnia mechanizm nadpisywania głosu (Revoting) poprzez weryfikację rosnącego nonce.
        """
        if tx.election_id not in self.state._elections:
            return False, "unknown election"
            
        if self.current_election_id and tx.election_id != self.current_election_id:
            return False, f"node restricted to election: {self.current_election_id}"

        if tx.candidate_id not in self.state.candidates(tx.election_id):
            return False, "unknown candidate"

        if not self.state.is_voter_registered(tx.election_id, tx.voter_pubkey):
            return False, "not registered"

        last_nonce = self.state.get_last_nonce(tx.voter_pubkey)
        
        if tx.nonce <= last_nonce:
            return False, f"invalid nonce: expected > {last_nonce}, got {tx.nonce}"

        if not verify(tx.voter_pubkey, _tx_payload(tx), tx.signature):
            return False, "bad signature"

        return True, "ok"

    def build_block(self, proposer_pubkey: str, max_txs: int = 1000) -> Block:
        """Pobiera poprawne transakcje z bufora (Mempool) i tworzy obiekt nowego bloku."""
        txs = self.mempool.get(max_txs)
        tx_hashes = [_hash_tx(tx) for tx in txs]
        merkle = get_merkle_root(tx_hashes)
        prev = self.state.last_hash
        header = {
            "index": self.state.get_chain_height(),
            "prev_hash": prev,
            "timestamp": int(time.time()),
            "merkle_root": merkle,
            "proposer_pubkey": proposer_pubkey,
        }
        header_hash = sha256(json.dumps(header, sort_keys=True).encode())
        return Block(
            index=header["index"],
            prev_hash=prev,
            timestamp=header["timestamp"],
            merkle_root=merkle,
            proposer_pubkey=proposer_pubkey,
            txs=txs,
            validator_signatures=[],
            block_hash=header_hash,
        )

    def finalize_block(self, block: Block) -> Tuple[bool, str]:
        """Weryfikuje strukturę bloku i zatwierdza go w lokalnym łańcuchu (stanie węzła)."""
        if block.prev_hash != self.state.last_hash:
            return False, "wrong prev hash"
        
        # Zabezpieczenie przed duplikacją nonce dla tego samego wyborcy wewnątrz jednego bloku
        seen_in_block = set()

        for tx in block.txs:
            ok, reason = self.validate_tx(tx)
            if not ok:
                return False, f"Invalid TX in block: {reason}"
            
            collision_key = (tx.voter_pubkey, tx.nonce)
            if collision_key in seen_in_block:
                return False, f"Duplicate nonce {tx.nonce} for voter in the same block"
            seen_in_block.add(collision_key)
        
        self.state.append_block(block)
        self.mempool.remove_many(block.txs)
        return True, "ok"