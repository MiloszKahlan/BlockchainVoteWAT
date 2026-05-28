import pytest
import time
import dataclasses
from fastapi.testclient import TestClient
from api import app, state, mempool, chain
from crypto import generate_keypair, sign
from blockchain import _tx_payload
from models import VoteTx

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_clean_state():
    """Resetuje stan pamięci węzła przed każdym uruchomieniem testu."""
    state.chain = []
    state._elections = {}
    state._voters_who_voted = set()
    state._last_nonces = {}
    mempool.clear()
    yield

def test_merkle_proof_verification():
    """Weryfikuje poprawność matematyczną drzewa Merkle'a i generowania dowodów."""
    from merkle import get_merkle_root, get_merkle_proof, verify_merkle_proof
    hashes = ["h1", "h2", "h3", "h4"]
    root = get_merkle_root(hashes)
    proof = get_merkle_proof(hashes, 0)
    assert verify_merkle_proof("h1", proof, root, 0) is True

def test_nonce_replay_protection():
    """Sprawdza, czy węzeł odrzuca ponownie przesłaną transakcję z tym samym nonce (Replay Attack)."""
    priv, pub = generate_keypair()
    state.create_election("t1", ["A"])
    state.add_voters("t1", [pub])
    
    tx = VoteTx("t1", pub, "A", 0, int(time.time()), "")
    tx.signature = sign(priv, _tx_payload(tx))
    
    assert client.post("/api/tx", json=dataclasses.asdict(tx)).json()["accepted"] is True
    
    response = client.post("/api/tx", json=dataclasses.asdict(tx))
    assert response.status_code == 400
    assert "pending in mempool" in response.json()["detail"]

def test_revoting_logic():
    """Weryfikuje algorytm nadpisywania głosów (Revoting) dla transakcji z wyższym nonce."""
    priv, pub = generate_keypair()
    eid = "revote"
    state.create_election(eid, ["A", "B"])
    
    tx1 = VoteTx(eid, pub, "A", 0, 100, "sig1")
    tx2 = VoteTx(eid, pub, "B", 1, 200, "sig2")
    
    from models import Block
    block = Block(0, "0"*64, 1000, "root", "prop", [tx1, tx2], [], "bhash")
    state.append_block(block)
    
    results = state.count_votes(eid)
    assert results["A"] == 0
    assert results["B"] == 1

def test_full_voting_lifecycle():
    """Test integracyjny E2E: od rejestracji, przez Mempool i finalizację, aż po weryfikację."""
    voter_priv, voter_pub = generate_keypair()
    from api import NODE_PUB_KEY
    state.set_validators([NODE_PUB_KEY])
    state.create_election("v", ["X"])
    state.add_voters("v", [voter_pub])
    
    tx = VoteTx("v", voter_pub, "X", 0, int(time.time()), "")
    tx.signature = sign(voter_priv, _tx_payload(tx))
    client.post("/api/tx", json=dataclasses.asdict(tx))
    
    res_prop = client.post("/api/propose")
    block_data = res_prop.json()
    finalize_payload = {
        "header": block_data["header"],
        "txs": block_data["txs"],
        "validator_signatures": block_data["validator_signatures"],
        "block_hash": block_data["block_hash"]
    }
    
    res_fin = client.post("/api/finalize", json=finalize_payload)
    assert res_fin.status_code == 200
    
    res_verify = client.get(f"/api/verify-vote/v", params={"voter_pubkey": voter_pub})
    assert res_verify.status_code == 200
    assert res_verify.json()["status"] == "confirmed"