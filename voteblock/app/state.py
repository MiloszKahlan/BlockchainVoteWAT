import json
import os
from typing import List, Dict, Set, Optional
from dataclasses import asdict

from models import Block, VoteTx

DATA_DIR = "data"
CHAIN_FILE = os.path.join(DATA_DIR, "chain.json")
STATE_FILE = os.path.join(DATA_DIR, "state_config.json")


class ChainState:
    def __init__(self):
        self.chain: List[Block] = []

        self._elections: Dict[str, Dict] = {}

        self._voters_who_voted: Set[tuple] = set()

        self._validators: List[str] = []

        self._ensure_data_dir()
        self.load_state()
        self.load_chain()

    def _ensure_data_dir(self):
        if not os.path.exists(DATA_DIR):
            os.makedirs(DATA_DIR)


    @property
    def last_hash(self) -> str:
        """Zwraca hash ostatniego bloku lub '0' jeśli łańcuch jest pusty."""
        if not self.chain:
            return "0" * 64  # Genesis prev_hash
        return self.chain[-1].block_hash

    def get_chain_height(self) -> int:
        return len(self.chain)

    def append_block(self, block: Block):
        """Dodaje blok do pamięci i zapisuje łańcuch na dysk."""
        self.chain.append(block)
        self.save_chain()
        for tx in block.txs:
            self.mark_voted(tx.election_id, tx.voter_pubkey)


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
        if not whitelist:
            return False
        return pubkey in whitelist

    def has_voted(self, election_id: str, pubkey: str) -> bool:
        return (election_id, pubkey) in self._voters_who_voted

    def mark_voted(self, election_id: str, pubkey: str):
        self._voters_who_voted.add((election_id, pubkey))

    def set_validators(self, validators: List[str]):
        self._validators = validators
        self.save_state()

    def get_validators(self) -> List[str]:
        return self._validators

    def count_votes(self, election_id: str) -> Dict[str, int]:
        """Zlicza głosy przeglądając cały łańcuch bloków."""
        results = {c: 0 for c in self.candidates(election_id)}

        for block in self.chain:
            for tx in block.txs:
                if tx.election_id == election_id:
                    if tx.candidate_id in results:
                        results[tx.candidate_id] += 1
        return results


    def save_state(self):
        """Zapisuje konfigurację wyborów i walidatorów."""
        data = {"elections": self._elections, "validators": self._validators}
        with open(STATE_FILE, "w") as f:
            json.dump(data, f, indent=2)

    def load_state(self):
        if not os.path.exists(STATE_FILE):
            return
        try:
            with open(STATE_FILE, "r") as f:
                data = json.load(f)
                self._elections = data.get("elections", {})
                self._validators = data.get("validators", [])
        except json.JSONDecodeError:
            print("Błąd odczytu pliku stanu.")

    def save_chain(self):
        """Zapisuje listę bloków do pliku JSON."""
        chain_data = [asdict(b) for b in self.chain]
        with open(CHAIN_FILE, "w") as f:
            json.dump(chain_data, f, indent=2)

    def load_chain(self):
        """Wczytuje łańcuch i odtwarza stan głosowania (kto głosował)."""
        if not os.path.exists(CHAIN_FILE):
            return
        try:
            with open(CHAIN_FILE, "r") as f:
                chain_data = json.load(f)

            self.chain = []
            self._voters_who_voted.clear()

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
                    self.mark_voted(tx.election_id, tx.voter_pubkey)

            print(f"Załadowano łańcuch: {len(self.chain)} bloków.")

        except json.JSONDecodeError:
            print("Błąd odczytu pliku łańcucha.")
        except Exception as e:
            print(f"Błąd krytyczny przy ładowaniu łańcucha: {e}")
