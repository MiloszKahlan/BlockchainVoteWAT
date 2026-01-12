from typing import Tuple
import base64, hashlib
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives import serialization


def generate_keypair() -> Tuple[str, str]:
    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key()
    priv_b = priv.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    pub_b = pub.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return base64.b64encode(priv_b).decode(), base64.b64encode(pub_b).decode()


def _priv_from_b64(priv_b64: str) -> Ed25519PrivateKey:
    return Ed25519PrivateKey.from_private_bytes(base64.b64decode(priv_b64))


def _pub_from_b64(pub_b64: str) -> Ed25519PublicKey:
    return Ed25519PublicKey.from_public_bytes(base64.b64decode(pub_b64))


def sign(priv_key_b64: str, msg: bytes) -> str:
    sig = _priv_from_b64(priv_key_b64).sign(msg)
    return base64.b64encode(sig).decode()


def verify(pub_key_b64: str, msg: bytes, signature_b64: str) -> bool:
    try:
        _pub_from_b64(pub_key_b64).verify(base64.b64decode(signature_b64), msg)
        return True
    except Exception:
        return False


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
