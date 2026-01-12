import json, time
from typing import Tuple
from models import VoteTx, Block
from state import ChainState
from mempool import Mempool
from crypto import sha256, verify
from merkle import get_merkle_root


def _tx_payload(tx: VoteTx) -> bytes:
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

    def validate_tx(self, tx: VoteTx) -> Tuple[bool, str]:
        if tx.election_id not in self.state._elections:
            return False, "unknown election"
        if tx.candidate_id not in self.state.candidates(tx.election_id):
            return False, "unknown candidate"
        if not self.state.is_voter_registered(tx.election_id, tx.voter_pubkey):
            return False, "not registered"
        if self.state.has_voted(tx.election_id, tx.voter_pubkey):
            return False, "already voted"
        if not verify(tx.voter_pubkey, _tx_payload(tx), tx.signature):
            return False, "bad signature"
        return True, "ok"

    # ...
    def build_block(self, proposer_pubkey: str, max_txs: int = 1000) -> Block:
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
        if block.prev_hash != self.state.last_hash:
            return False, "wrong prev hash"
        for tx in block.txs:
            ok, reason = self.validate_tx(tx)
            if not ok:
                return False, f"invalid tx: {reason}"
        for tx in block.txs:
            self.state.mark_voted(tx.election_id, tx.voter_pubkey)
        self.state.append_block(block)
        self.mempool.remove_many(block.txs)
        return True, "ok"
