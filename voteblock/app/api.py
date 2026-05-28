import os
import json
import time
from fastapi import FastAPI, APIRouter, HTTPException, status
from dataclasses import asdict
from typing import List, Dict
from pydantic import BaseModel

from models import VoteTxIn, VoteTxOut, ResultsOut, ChainInfo, VoteTx, Block, BlockIn
from state import ChainState
from mempool import Mempool
from blockchain import Blockchain, _hash_tx
from consensus import PoALite
from crypto import generate_keypair
from merkle import get_merkle_proof, verify_merkle_proof

# --- Konfiguracja Tożsamości Węzła ---
KEY_FILE = "node_key.json"

def load_or_generate_node_key():
    if os.path.exists(KEY_FILE):
        with open(KEY_FILE, "r") as f:
            data = json.load(f)
            return data["priv"], data["pub"]
    else:
        print("Generowanie nowych kluczy węzła...")
        priv, pub = generate_keypair()
        with open(KEY_FILE, "w") as f:
            json.dump({"priv": priv, "pub": pub}, f)
        return priv, pub

NODE_PRIV_KEY, NODE_PUB_KEY = load_or_generate_node_key()

# --- Inicjalizacja komponentów ---
state = ChainState()
consensus = PoALite(state)
mempool = Mempool()
chain = Blockchain(state, mempool)

app = FastAPI(title="VoteBlock API Node")
router = APIRouter(prefix="/api")

print(f"\n=== NODE STARTED ===")
print(f"My Public Key (Validator ID): {NODE_PUB_KEY}")
print(f"Add this key to validators list via POST /api/validators to enable mining.\n")

# --- Schemy requestów (Pydantic) ---
class CreateElectionReq(BaseModel):
    election_id: str
    candidates: List[str]

class AddVotersReq(BaseModel):
    voters_pubkeys: List[str]

class SetValidatorsReq(BaseModel):
    validators: List[str]

class VerifyProofReq(BaseModel):
    leaf_hash: str
    proof: List[str]
    root: str
    index: int

# --- Endpoints ---
@router.get("/health")
def health():
    return {
        "status": "ok",
        "node_pubkey": NODE_PUB_KEY,
        "height": state.get_chain_height(),
    }

# --- Admin / Konfiguracja ---
@router.post("/elections")
def create_election(req: CreateElectionReq):
    if req.election_id in state._elections:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Election already exists")
    state.create_election(req.election_id, req.candidates)
    return {"ok": True}

@router.post("/elections/{election_id}/registry")
def add_voters(election_id: str, req: AddVotersReq):
    if election_id not in state._elections:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown election")
    state.add_voters(election_id, req.voters_pubkeys)
    return {"ok": True}

@router.post("/validators")
def set_validators(req: SetValidatorsReq):
    state.set_validators(req.validators)
    return {"ok": True}

# --- Transakcje (Głosowanie) ---
@router.post("/tx", response_model=VoteTxOut)
def submit_vote(tx: VoteTxIn) -> VoteTxOut:
    """
    Endpoint przyjmujący transakcję od klienta.
    Odrzuca żądanie (HTTP 400), jeśli walidacja kryptograficzna lub reguły nonce zawiodą.
    """
    itx = VoteTx(**tx.model_dump())

    ok, reason = chain.validate_tx(itx)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Transaction rejected: {reason}"
        )

    mempool_ok = mempool.add(itx)
    if not mempool_ok:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Transaction rejected: Identical transaction with this nonce is already pending in mempool"
        )

    return VoteTxOut(tx_hash=_hash_tx(itx), accepted=True)

# --- Konsensus i Blok ---
@router.post("/propose")
def propose_block():
    if not consensus.is_validator(NODE_PUB_KEY):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Node is not an authorized validator")

    block = chain.build_block(proposer_pubkey=NODE_PUB_KEY)
    consensus.sign_block(block, NODE_PRIV_KEY, NODE_PUB_KEY)

    return {
        "header": {
            "index": block.index,
            "prev_hash": block.prev_hash,
            "timestamp": block.timestamp,
            "merkle_root": block.merkle_root,
            "proposer_pubkey": block.proposer_pubkey,
        },
        "txs": [asdict(tx) for tx in block.txs],
        "validator_signatures": block.validator_signatures,
        "block_hash": block.block_hash,
    }

@router.post("/finalize")
def finalize_block(block_in: BlockIn):
    txs_objs = [VoteTx(**tx.model_dump()) for tx in block_in.txs]
    block = Block(
        index=block_in.header.index,
        prev_hash=block_in.header.prev_hash,
        timestamp=block_in.header.timestamp,
        merkle_root=block_in.header.merkle_root,
        proposer_pubkey=block_in.header.proposer_pubkey,
        txs=txs_objs,
        validator_signatures=block_in.validator_signatures,
        block_hash=block_in.block_hash,
    )

    is_valid_proposer, msg = consensus.verify_proposer(block)
    if not is_valid_proposer:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Consensus Error: {msg}")

    ok, reason = chain.finalize_block(block)
    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Block Error: {reason}")

    return {
        "ok": True,
        "height": state.get_chain_height(),
        "last_hash": state.last_hash,
    }

# --- Info / Wyniki / Weryfikacja ---
@router.get("/chain", response_model=ChainInfo)
def chain_info():
    return ChainInfo(
        height=state.get_chain_height(),
        last_hash=state.last_hash,
        validators=state.get_validators(),
    )

@router.get("/results/{election_id}", response_model=ResultsOut)
def results(election_id: str):
    if election_id not in state._elections:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown election")
    counts = state.count_votes(election_id)
    return ResultsOut(
        election_id=election_id,
        counts=counts,
        total_valid=sum(counts.values()),
        total_rejected=0,
    )

@router.get("/verify-vote/{election_id}")
def get_vote_proof(election_id: str, voter_pubkey: str):
    target_tx, target_block, tx_index = None, None, -1

    for block in reversed(state.chain):
        for i, tx in enumerate(block.txs):
            if tx.election_id == election_id and tx.voter_pubkey == voter_pubkey:
                target_tx, target_block, tx_index = tx, block, i
                break
        if target_tx: break

    if not target_tx:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Głos nie został jeszcze sfinalizowany w łańcuchu.")

    block_tx_hashes = [_hash_tx(t) for t in target_block.txs]
    proof = get_merkle_proof(block_tx_hashes, tx_index)

    return {
        "status": "confirmed",
        "block_height": target_block.index,
        "transaction_hash": _hash_tx(target_tx),
        "merkle_root": target_block.merkle_root,
        "merkle_proof": proof,
        "index_in_block": tx_index,
    }

@router.post("/check-proof-validity")
def check_proof_validity(req: VerifyProofReq):
    """
    Endpoint pomocniczy wykorzystujący funkcję verify_merkle_proof.
    Pozwala sprawdzić, czy dostarczony dowód matematycznie pasuje do korzenia Merkle'a.
    """
    is_valid = verify_merkle_proof(req.leaf_hash, req.proof, req.root, req.index)
    return {"is_valid": is_valid}

app.include_router(router)