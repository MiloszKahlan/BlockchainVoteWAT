import json
import os
from typing import List, Dict, Set, Optional
from dataclasses import asdict

from models import Block, VoteTx

DATA_DIR = "data"
CHAIN_FILE = os.path.join(DATA_DIR, "chain.json")
STATE_FILE = os.path.join(DATA_DIR, "state_config.json")


class ChainState:
    """Zarządza globalnym stanem węzła, w tym pamięcią trwałą i rejestrem wyborców."""

    def __init__(self):
        self.chain: List[Block] = []
        self._elections: Dict[str, Dict] = {}
        self._validators: List[str] = []
        self._last_nonces: Dict[str, int] = {}

        self._ensure_data_dir()
        self.load_state()
        self.load_chain()

    def _ensure_data_dir(self):
        if not os.path.exists(DATA_DIR):
            os.makedirs(DATA_DIR)

    @property
    def last_hash(self) -> str:
        """Zwraca skrót ostatniego bloku lub skrót wyzerowany, jeśli łańcuch jest pusty."""
        if not self.chain:
            return "0" * 64  
        return self.chain[-1].block_hash

    def get_chain_height(self) -> int:
        return len(self.chain)

    # --- Zarządzanie Nonce (Replay Attack Protection) ---

    def get_last_nonce(self, pubkey: str) -> int:
        """Zwraca ostatni użyty nonce dla danego klucza lub -1 w przypadku jego braku."""
        return self._last_nonces.get(pubkey, -1)

    def update_nonce(self, pubkey: str, nonce: int):
        self._last_nonces[pubkey] = nonce

    # --- Operacje na łańcuchu ---

    def append_block(self, block: Block):
        """Osadza blok w łańcuchu lokalnym i aktualizuje stan w pamięci."""
        self.chain.append(block)
        self.save_chain()
        for tx in block.txs:
            # Usunięto mark_voted, zostawiamy tylko aktualizację nonce
            self.update_nonce(tx.voter_pubkey, tx.nonce)

    # --- Zarządzanie wyborami i walidatorami ---

    def create_election(self, election_id: str, candidates: List[str]):
        self._elections[election_id] = {
            "candidates": candidates,
            "whitelist": [],
        }
        self.save_state()

    def add_voters(self, election_id: str, pubkeys: List[str]):
        if election_id in self._elections:
            current = set(self._elections[election_id]["whitelist"])
            current.update(pubkeys)
            self._elections[election_id]["whitelist"] = list(current)
            self.save_state()

    def candidates(self, election_id: str) -> List[str]:
        return self._elections.get(election_id, {}).get("candidates", [])

    def is_voter_registered(self, election_id: str, pubkey: str) -> bool:
        if election_id not in self._elections:
            return False
        whitelist = self._elections[election_id]["whitelist"]
        return pubkey in whitelist if whitelist else False

    def set_validators(self, validators: List[str]):
        self._validators = validators
        self.save_state()

    def get_validators(self) -> List[str]:
        return self._validators

    def count_votes(self, election_id: str) -> Dict[str, int]:
        """
        Zlicza głosy. Wykorzystuje logikę Revoting, uwzględniając 
        wyłącznie transakcję z najwyższym licznikiem nonce dla każdego wyborcy.
        """
        latest_votes: Dict[str, tuple] = {}

        for block in self.chain:
            for tx in block.txs:
                if tx.election_id == election_id:
                    voter = tx.voter_pubkey
                    if voter not in latest_votes or tx.nonce > latest_votes[voter][0]:
                        latest_votes[voter] = (tx.nonce, tx.candidate_id)

        results = {c: 0 for c in self.candidates(election_id)}
        for _, candidate_id in latest_votes.values():
            if candidate_id in results:
                results[candidate_id] += 1
        return results

    # --- Persistence (Zapis/Odczyt) ---

    def save_state(self):
        """Zapisuje bieżącą konfigurację węzła do pliku JSON."""
        data = {
            "elections": self._elections, 
            "validators": self._validators,
            "nonces": self._last_nonces  
        }
        with open(STATE_FILE, "w") as f:
            json.dump(data, f, indent=2)

    def load_state(self):
        """Wczytuje konfigurację węzła z pliku JSON."""
        if not os.path.exists(STATE_FILE):
            return
        try:
            with open(STATE_FILE, "r") as f:
                data = json.load(f)
                self._elections = data.get("elections", {})
                self._validators = data.get("validators", [])
                self._last_nonces = data.get("nonces", {})
        except json.JSONDecodeError:
            print("Błąd odczytu pliku stanu.")

    def save_chain(self):
        """Zapisuje strukturę łańcucha do pliku."""
        chain_data = [asdict(b) for b in self.chain]
        with open(CHAIN_FILE, "w") as f:
            json.dump(chain_data, f, indent=2)

    def load_chain(self):
        """Odtwarza pełny stan rejestru bloków (State Replay)."""
        if not os.path.exists(CHAIN_FILE):
            return
        try:
            with open(CHAIN_FILE, "r") as f:
                chain_data = json.load(f)

            self.chain = []
            self._last_nonces.clear() 

            for b_data in chain_data:
                txs_objs = [VoteTx(**tx) for tx in b_data["txs"]]

                block = Block(
                    index=b_data["index"],
                    prev_hash=b_data["prev_hash"],
                    timestamp=b_data["timestamp"],
                    merkle_root=b_data["merkle_root"],
                    proposer_pubkey=b_data["proposer_pubkey"],
                    txs=txs_objs,
                    validator_signatures=b_data["validator_signatures"],
                    block_hash=b_data["block_hash"],
                )
                self.chain.append(block)

                for tx in block.txs:
                    # Usunięto mark_voted, zostawiamy tylko aktualizację nonce
                    self.update_nonce(tx.voter_pubkey, tx.nonce)

            print(f"Załadowano łańcuch: {len(self.chain)} bloków. Odtworzono {len(self._last_nonces)} rekordów nonce.")

        except json.JSONDecodeError:
            print("Błąd odczytu pliku łańcucha.")
        except Exception as e:
            print(f"Błąd krytyczny przy ładowaniu łańcucha: {e}")