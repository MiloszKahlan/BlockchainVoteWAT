from typing import Tuple, List, Dict
from models import Block
from crypto import sign, verify
from state import ChainState


class PoALite:
    """
    Implementacja mechanizmu konsensusu Proof of Authority (PoA) w wersji Lite.
    """

    def __init__(self, state: ChainState):
        self.state = state

    def is_validator(self, pubkey: str) -> bool:
        """Sprawdza, czy klucz publiczny należy do autoryzowanych walidatorów."""
        validators = self.state.get_validators()
        if not validators:
            return True
        return pubkey in validators

    def sign_block(self, block: Block, priv_key: str, pub_key: str):
        """Dodaje podpis cyfrowy walidatora do nagłówka bloku."""
        signature = sign(priv_key, block.block_hash.encode())
        sig_entry = {"pubkey": pub_key, "signature": signature}
        block.validator_signatures.append(sig_entry)

    def verify_proposer(self, block: Block) -> Tuple[bool, str]:
        """
        Weryfikuje, czy proponujący blok (Proposer) jest na białej liście 
        oraz czy jego podpis kryptograficzny pasuje do hasha bloku.
        """
        proposer_pub = block.proposer_pubkey

        if not self.is_validator(proposer_pub):
            return (
                False,
                f"Proposer {proposer_pub[:8]}... nie jest na liscie walidatorow.",
            )

        proposer_signature = None
        for entry in block.validator_signatures:
            if entry.get("pubkey") == proposer_pub:
                proposer_signature = entry.get("signature")
                break

        if not proposer_signature:
            return False, "Blok nie zawiera podpisu tworcy (Proposera)."

        if not verify(proposer_pub, block.block_hash.encode(), proposer_signature):
            return False, "Podpis kryptograficzny Proposera jest nieprawidlowy."

        return True, "OK"

    def verify_quorum(self, block: Block) -> bool:
        """Weryfikuje, czy blok osiągnął kworum podpisów (powyżej 50% walidatorów)."""
        validators = self.state.get_validators()
        if not validators:
            return True  

        required_votes = (len(validators) // 2) + 1
        valid_votes = 0
        seen_validators = set()

        for entry in block.validator_signatures:
            pub = entry.get("pubkey")
            sig = entry.get("signature")

            if pub in validators and pub not in seen_validators:
                if verify(pub, block.block_hash.encode(), sig):
                    valid_votes += 1
                    seen_validators.add(pub)

        return valid_votes >= required_votes