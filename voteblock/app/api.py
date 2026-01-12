import os
import json
from fastapi import FastAPI, APIRouter, HTTPException
from dataclasses import asdict
from typing import List, Dict
from models import VoteTxIn, VoteTxOut, ResultsOut, ChainInfo, VoteTx, Block, BlockIn
from state import ChainState
from mempool import Mempool
from blockchain import Blockchain
from consensus import PoALite
from crypto import generate_keypair

# --- Konfiguracja Tożsamości Węzła (Node Identity) ---
KEY_FILE = "node_key.json"


def load_or_generate_node_key():
    """
    Ładuje klucze węzła z pliku lub generuje nowe.
    W pracy dyplomowej opiszesz to jako 'mechanizm zarządzania tożsamością węzła'.
    """
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
# 1. State: Ładuje historię z dysku (persistence)
state = ChainState()

# 2. Consensus: Logika PoA (kto może tworzyć bloki)
consensus = PoALite(state)

# 3. Mempool & Blockchain
mempool = Mempool()
chain = Blockchain(state, mempool)

app = FastAPI(title="VoteBlock API Node")
router = APIRouter(prefix="/api")

print(f"\n=== NODE STARTED ===")
print(f"My Public Key (Validator ID): {NODE_PUB_KEY}")
print(f"Add this key to validators list via POST /api/validators to enable mining.\n")

# --- Schemy requestów (Pydantic) ---
from pydantic import BaseModel


class CreateElectionReq(BaseModel):
    election_id: str
    candidates: List[str]


class AddVotersReq(BaseModel):
    voters_pubkeys: List[str]


class SetValidatorsReq(BaseModel):
    validators: List[str]


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
    # W wersji produkcyjnej to też powinno być transakcją,
    # tutaj upraszczamy - admin ma bezpośredni dostęp do stanu.
    if req.election_id in state._elections:
        raise HTTPException(status_code=400, detail="election already exists")
    state.create_election(req.election_id, req.candidates)
    return {"ok": True}


@router.post("/elections/{election_id}/registry")
def add_voters(election_id: str, req: AddVotersReq):
    if election_id not in state._elections:
        raise HTTPException(status_code=404, detail="unknown election")
    state.add_voters(election_id, req.voters_pubkeys)
    return {"ok": True}


@router.post("/validators")
def set_validators(req: SetValidatorsReq):
    """
    Ustawia listę kluczy publicznych, które mogą tworzyć bloki.
    Aby ten węzeł mógł kopać, jego NODE_PUB_KEY musi się tu znaleźć.
    """
    state.set_validators(req.validators)
    return {"ok": True}


# --- Transakcje (Głosowanie) ---


@router.post("/tx", response_model=VoteTxOut)
def submit_vote(tx: VoteTxIn) -> VoteTxOut:
    itx = VoteTx(**tx.model_dump())

    # Walidacja biznesowa (czy wybory istnieją, podpis, czy nie głosował)
    ok, reason = chain.validate_tx(itx)
    if not ok:
        return VoteTxOut(tx_hash="", accepted=False, reason=reason)

    mempool.add(itx)
    return VoteTxOut(tx_hash="pending", accepted=True)


# --- Konsensus i Blok ---


@router.post("/propose")
def propose_block():
    """
    Tworzy kandydat na blok, PODPISUJE go i zwraca PEŁNY obiekt.
    Dzięki temu można skopiować wynik JSON wprost do /finalize.
    """
    # 1. Sprawdź uprawnienia
    if not consensus.is_validator(NODE_PUB_KEY):
        raise HTTPException(
            status_code=403, detail="Node is not an authorized validator"
        )

    # 2. Zbuduj blok
    block = chain.build_block(proposer_pubkey=NODE_PUB_KEY)

    # 3. Podpisz blok
    consensus.sign_block(block, NODE_PRIV_KEY, NODE_PUB_KEY)

    # 4. Zwróć PEŁNĄ strukturę zgodną z BlockIn (schema finalize)
    return {
        "header": {
            "index": block.index,
            "prev_hash": block.prev_hash,
            "timestamp": block.timestamp,
            "merkle_root": block.merkle_root,
            "proposer_pubkey": block.proposer_pubkey,
        },
        # Konwertujemy dataclass VoteTx na zwykły słownik (dict)
        "txs": [asdict(tx) for tx in block.txs],
        "validator_signatures": block.validator_signatures,
        "block_hash": block.block_hash,
    }


@router.post("/finalize")
def finalize_block(block_in: BlockIn):
    """
    Przyjmuje zbudowany blok, WERYFIKUJE uprawnienia twórcy i dołącza do łańcucha.
    """
    # 1. Konwersja z Pydantic (JSON) na wewnętrzny obiekt Block
    # Musimy zrekonstruować obiekty VoteTx w środku
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

    # 2. Weryfikacja Konsensusu (PoA)
    # Czy ten, kto przysłał blok, jest na liście walidatorów w state.py?
    is_valid_proposer, msg = consensus.verify_proposer(block)
    if not is_valid_proposer:
        raise HTTPException(status_code=400, detail=f"Consensus Error: {msg}")

    # 3. Finalizacja (Sprawdzenie transakcji i zapis do chain.json)
    ok, reason = chain.finalize_block(block)
    if not ok:
        raise HTTPException(status_code=400, detail=f"Block Error: {reason}")

    return {
        "ok": True,
        "height": state.get_chain_height(),
        "last_hash": state.last_hash,
    }


# --- Info / Wyniki ---


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
        raise HTTPException(status_code=404, detail="unknown election")

    counts = state.count_votes(election_id)
    return ResultsOut(
        election_id=election_id,
        counts=counts,
        total_valid=sum(counts.values()),
        total_rejected=0,
    )


app.include_router(router)
