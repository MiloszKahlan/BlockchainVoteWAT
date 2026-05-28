import argparse
import requests
import json
import time
import sys
from typing import Dict

from crypto import generate_keypair, sign

API_URL = "http://localhost:8000/api"
KEY_FILE = "voter_key.json"


def load_keys():
    """Wczytuje parę kluczy z pliku JSON."""
    try:
        with open(KEY_FILE, "r") as f:
            data = json.load(f)
            return data["priv"], data["pub"]
    except FileNotFoundError:
        print(f"Błąd: Nie znaleziono pliku {KEY_FILE}. Użyj komendy 'keygen' najpierw.")
        sys.exit(1)


def _tx_payload_canonical(tx_dict: Dict) -> bytes:
    """Tworzy kanoniczną postać danych do podpisu. Zgodne z formatem węzła."""
    d = {
        "election_id": tx_dict["election_id"],
        "voter_pubkey": tx_dict["voter_pubkey"],
        "candidate_id": tx_dict["candidate_id"],
        "nonce": tx_dict["nonce"],
        "timestamp": tx_dict["timestamp"],
    }
    return json.dumps(d, sort_keys=True).encode()


def cmd_keygen(args):
    """Generuje nową tożsamość wyborcy (portfel)."""
    priv, pub = generate_keypair()
    data = {"priv": priv, "pub": pub}
    filename = args.filename or KEY_FILE
    with open(filename, "w") as f:
        json.dump(data, f)
    print(f"[+] Wygenerowano klucze w '{filename}'")
    print(f"Twój Public Key (ID): {pub}")


def cmd_create_election(args):
    """Admin: Tworzy nowe wybory."""
    payload = {"election_id": args.id, "candidates": args.candidates}
    r = requests.post(f"{API_URL}/elections", json=payload)
    if r.status_code == 200:
        print(f"[+] Wybory '{args.id}' utworzone.")
    else:
        print(f"[-] Błąd: {r.text}")


def cmd_register(args):
    """Admin: Dodaje wyborców do listy uprawnionych (whitelist)."""
    keys = [k.strip() for k in args.pubkeys.split(",")]
    payload = {"voters_pubkeys": keys}
    r = requests.post(f"{API_URL}/elections/{args.id}/registry", json=payload)
    if r.status_code == 200:
        print(f"[+] Zarejestrowano {len(keys)} wyborców w '{args.id}'.")
    else:
        print(f"[-] Błąd: {r.text}")


def cmd_set_validator(args):
    """Admin: Ustawia walidatora w węźle."""
    payload = {"validators": [args.pubkey]}
    r = requests.post(f"{API_URL}/validators", json=payload)
    print(f"Odp serwera: {r.json()}")


def cmd_vote(args):
    """
    User: Pobiera status licznika, inkrementuje go (obsługa Revoting),
    podpisuje transakcję i przesyła do Mempoola.
    """
    priv_key, pub_key = load_keys()
    calculated_nonce = 0

    try:
        r_nonce = requests.get(f"{API_URL}/verify-vote/{args.election_id}", params={"voter_pubkey": pub_key})
        if r_nonce.status_code == 200:
            print("[*] Wykryto istniejący głos w łańcuchu. Inkrementacja licznika (Revoting)...")
            calculated_nonce = 1
        else:
            calculated_nonce = 0
    except Exception:
        calculated_nonce = 0

    tx_data = {
        "election_id": args.election_id,
        "voter_pubkey": pub_key,
        "candidate_id": args.candidate,
        "nonce": calculated_nonce,
        "timestamp": int(time.time()),
    }

    payload_bytes = _tx_payload_canonical(tx_data)
    signature = sign(priv_key, payload_bytes)
    tx_data["signature"] = signature

    print(f"[*] Wysyłanie głosu na kandydata '{args.candidate}' z nonce={calculated_nonce}...")
    try:
        r = requests.post(f"{API_URL}/tx", json=tx_data)
        if r.status_code == 200:
            resp = r.json()
            if resp.get("accepted", True):
                print(f"[+] Głos przyjęty do Mempoola! Status: {resp.get('tx_hash', 'pending')}")
            else:
                print(f"[-] Głos odrzucony przez węzeł: {resp.get('reason', 'unknown')}")
        else:
            print(f"[-] Błąd HTTP {r.status_code}: {r.text}")
    except Exception as e:
        print(f"[-] Błąd połączenia: {e}")


def cmd_results(args):
    """Pobiera i wyświetla wyniki z łańcucha."""
    r = requests.get(f"{API_URL}/results/{args.id}")
    if r.status_code == 200:
        res = r.json()
        print(f"Wyniki wyborów '{res['election_id']}':")
        for cand, count in res["counts"].items():
            print(f"  - {cand}: {count} głosów")
    else:
        print(f"[-] Błąd: {r.text}")


def cmd_info(args):
    """Zwraca status lokalnego węzła."""
    r = requests.get(f"{API_URL}/chain")
    print(json.dumps(r.json(), indent=2))


def main():
    parser = argparse.ArgumentParser(description="VoteBlock CLI Client")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_keygen = subparsers.add_parser("keygen", help="Generuj klucze wyborcy")
    p_keygen.add_argument("--filename", default=KEY_FILE, help="Plik wyjściowy")
    p_keygen.set_defaults(func=cmd_keygen)

    p_create = subparsers.add_parser("create-election", help="Utwórz wybory (Admin)")
    p_create.add_argument("id", help="ID wyborów (np. prezydenckie-2025)")
    p_create.add_argument("candidates", nargs="+", help="Lista kandydatów")
    p_create.set_defaults(func=cmd_create_election)

    p_reg = subparsers.add_parser("register", help="Zarejestruj wyborcę (Admin)")
    p_reg.add_argument("id", help="ID wyborów")
    p_reg.add_argument("pubkeys", help="Klucz(e) publiczne po przecinku")
    p_reg.set_defaults(func=cmd_reg)

    p_val = subparsers.add_parser("set-validator", help="Ustaw walidatora (Admin)")
    p_val.add_argument("pubkey", help="Klucz publiczny węzła")
    p_val.set_defaults(func=cmd_set_validator)

    p_vote = subparsers.add_parser("vote", help="Oddaj głos")
    p_vote.add_argument("election_id", help="ID wyborów")
    p_vote.add_argument("candidate", help="ID kandydata")
    p_vote.set_defaults(func=cmd_vote)

    p_info = subparsers.add_parser("info", help="Pokaż stan łańcucha")
    p_info.set_defaults(func=cmd_info)

    p_sub_res = subparsers.add_parser("results", help="Pokaż wyniki")
    p_sub_res.add_argument("id", help="ID wyborów")
    p_sub_res.set_defaults(func=cmd_results)

    args = parser.parse_args()
    try:
        args.func(args)
    except requests.exceptions.ConnectionError:
        print(f"CRITICAL: Nie można połączyć się z węzłem pod adresem {API_URL}")
        print("Upewnij się, że uruchomiłeś 'uvicorn api:app' w innym oknie.")


if __name__ == "__main__":
    main()