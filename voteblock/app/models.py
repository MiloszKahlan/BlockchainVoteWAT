from dataclasses import dataclass
from typing import List, Dict, Optional
from pydantic import BaseModel


# --- Modele DTO (Data Transfer Objects) dla API (Pydantic) ---

class VoteTxIn(BaseModel):
    """Schemat wejściowy dla nowej transakcji głosu z sieci."""
    election_id: str
    voter_pubkey: str
    candidate_id: str
    nonce: int
    timestamp: int
    signature: str


class VoteTxOut(BaseModel):
    """Schemat odpowiedzi po przetworzeniu transakcji."""
    tx_hash: str
    accepted: bool
    reason: Optional[str] = None


class BlockHeader(BaseModel):
    """Schemat nagłówka bloku w żądaniach sieciowych."""
    index: int
    prev_hash: str
    timestamp: int
    merkle_root: str
    proposer_pubkey: str


class BlockIn(BaseModel):
    """Schemat wejściowy propozycji całego bloku (złącze /finalize)."""
    header: BlockHeader
    txs: List[VoteTxIn]
    validator_signatures: List[dict]
    block_hash: str


class ChainInfo(BaseModel):
    """Schemat statusu łańcucha zwracany przez API."""
    height: int
    last_hash: str
    validators: List[str] = []


class ResultsOut(BaseModel):
    """Schemat wyników wyborów."""
    election_id: str
    counts: Dict[str, int]
    total_valid: int
    total_rejected: int


# --- Wewnętrzne modele domenowe (Dataclasses) ---

@dataclass
class VoteTx:
    """Wewnętrzna reprezentacja transakcji głosowania w logice węzła."""
    election_id: str
    voter_pubkey: str
    candidate_id: str
    nonce: int
    timestamp: int
    signature: str


@dataclass
class Block:
    """Wewnętrzna reprezentacja bloku w łańcuchu."""
    index: int
    prev_hash: str
    timestamp: int
    merkle_root: str
    proposer_pubkey: str
    txs: List[VoteTx]
    validator_signatures: List[dict]
    block_hash: str