from dataclasses import dataclass
from typing import List, Dict, Optional
from pydantic import BaseModel


class VoteTxIn(BaseModel):
    election_id: str
    voter_pubkey: str
    candidate_id: str
    nonce: int
    timestamp: int
    signature: str


class VoteTxOut(BaseModel):
    tx_hash: str
    accepted: bool
    reason: Optional[str] = None


class BlockHeader(BaseModel):
    index: int
    prev_hash: str
    timestamp: int
    merkle_root: str
    proposer_pubkey: str


class BlockIn(BaseModel):
    header: BlockHeader
    txs: List[VoteTxIn]
    validator_signatures: List[dict]
    block_hash: str


class ChainInfo(BaseModel):
    height: int
    last_hash: str
    validators: List[str] = []


class ResultsOut(BaseModel):
    election_id: str
    counts: Dict[str, int]
    total_valid: int
    total_rejected: int


@dataclass
class VoteTx:
    election_id: str
    voter_pubkey: str
    candidate_id: str
    nonce: int
    timestamp: int
    signature: str


@dataclass
class Block:
    index: int
    prev_hash: str
    timestamp: int
    merkle_root: str
    proposer_pubkey: str
    txs: List[VoteTx]
    validator_signatures: List[dict]
    block_hash: str
