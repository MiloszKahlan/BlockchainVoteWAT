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
    """
    Tworzy kanoniczną postać danych do podpisu.
    UWAGA: Musi być IDENTYCZNA jak w blockchain.py (funkcja _tx_payload).
    W przeciwnym razie weryfikacja na serwerze się nie uda.
    """
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
    """Admin: Rejestruje wyborców (dodaje do whitelist)."""
    keys = [k.strip() for k in args.pubkeys.split(",")]
    payload = {"voters_pubkeys": keys}
    r = requests.post(f"{API_URL}/elections/{args.id}/registry", json=payload)
    if r.status_code == 200:
        print(f"[+] Zarejestrowano {len(keys)} wyborców w '{args.id}'.")
    else:
        print(f"[-] Błąd: {r.text}")


def cmd_set_validator(args):
    """Node Operator: Ustawia listę walidatorów."""
    payload = {"validators": [args.pubkey]}
    r = requests.post(f"{API_URL}/validators", json=payload)
    print(f"Odp serwera: {r.json()}")


def cmd_vote(args):
    """User: Oddaje głos (tworzy transakcję, podpisuje i wysyła)."""
    priv_key, pub_key = load_keys()

    tx_data = {
        "election_id": args.election_id,
        "voter_pubkey": pub_key,
        "candidate_id": args.candidate,
        "nonce": int(time.time() * 1000),
        "timestamp": int(time.time()),
    }

    payload_bytes = _tx_payload_canonical(tx_data)
    signature = sign(priv_key, payload_bytes)

    tx_data["signature"] = signature

    print(f"[*] Wysyłanie głosu na kandydata '{args.candidate}'...")
    try:
        r = requests.post(f"{API_URL}/tx", json=tx_data)
        if r.status_code == 200:
            resp = r.json()
            if resp["accepted"]:
                print(f"[+] Głos przyjęty do Mempoola! Status: {resp['tx_hash']}")
            else:
                print(f"[-] Głos odrzucony przez węzeł: {resp['reason']}")
        else:
            print(f"[-] Błąd HTTP: {r.text}")
    except Exception as e:
        print(f"[-] Błąd połączenia: {e}")


def cmd_mine(args):
    """
    Node Operator: Wymusza utworzenie i finalizację bloku.
    W systemie produkcyjnym działo by się to automatycznie co X sekund.
    W pracy dyplomowej pokazujemy to jako ręczny krok 'symulacji'.
    """
    print("[*] Proponowanie bloku (Propose)...")
    r1 = requests.post(f"{API_URL}/propose", json={})
    if r1.status_code != 200:
        print(f"[-] Błąd Propose: {r1.text}")
        return

    block_data = r1.json()
    tx_count = block_data.get("tx_count", 0)
    print(f"    Utworzono kandydat na blok. Liczba transakcji: {tx_count}")

    print(
        "[-] Aby sfinalizować blok w tym demo, użyj wbudowanego w API mechanizmu 'auto-mine' lub Swaggera."
    )
    print("    (W pełnej wersji P2P blok byłby rozgłaszany automatycznie).")

    pass


def cmd_results(args):
    """Pobiera i wyświetla wyniki."""
    r = requests.get(f"{API_URL}/results/{args.id}")
    if r.status_code == 200:
        res = r.json()
        print(f"Wyniki wyborów '{res['election_id']}':")
        for cand, count in res["counts"].items():
            print(f"  - {cand}: {count} głosów")
    else:
        print(f"[-] Błąd: {r.text}")


def cmd_info(args):
    """Status łańcucha."""
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
    p_reg.set_defaults(func=cmd_register)

    p_val = subparsers.add_parser("set-validator", help="Ustaw walidatora (Admin)")
    p_val.add_argument("pubkey", help="Klucz publiczny węzła")
    p_val.set_defaults(func=cmd_set_validator)

    p_vote = subparsers.add_parser("vote", help="Oddaj głos")
    p_vote.add_argument("election_id", help="ID wyborów")
    p_vote.add_argument("candidate", help="ID kandydata")
    p_vote.set_defaults(func=cmd_vote)

    p_info = subparsers.add_parser("info", help="Pokaż stan łańcucha")
    p_info.set_defaults(func=cmd_info)

    p_res = subparsers.add_parser("results", help="Pokaż wyniki")
    p_res.add_argument("id", help="ID wyborów")
    p_res.set_defaults(func=cmd_results)

    args = parser.parse_args()
    try:
        args.func(args)
    except requests.exceptions.ConnectionError:
        print(f"CRITICAL: Nie można połączyć się z węzłem pod adresem {API_URL}")
        print("Upewnij się, że uruchomiłeś 'uvicorn api:app' w innym oknie.")


if __name__ == "__main__":
    main()
