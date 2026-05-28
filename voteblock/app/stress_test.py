import requests
import time
from crypto import generate_keypair, sign
import json

API_URL = "http://localhost:8000/api"
ELECTION_ID = "stress_test_1"  
NUM_VOTERS = 10000

print("--- INICJALIZACJA TESTU ---")
print(f"1. Tworzenie wyborów '{ELECTION_ID}'...")
r_elec = requests.post(f"{API_URL}/elections", json={
    "election_id": ELECTION_ID,
    "candidates": ["Kandydat_A", "Kandydat_B"]
})
if r_elec.status_code not in [200, 400]: 
    print(f"[-] Błąd tworzenia wyborów: {r_elec.text}")
    exit()

print(f"2. Generowanie {NUM_VOTERS} kluczy (to potrwa kilka sekund)...")
voters = [generate_keypair() for _ in range(NUM_VOTERS)]
pubkeys = [pub for priv, pub in voters]

print("3. Rejestracja wyborców na białej liście...")
for i in range(0, len(pubkeys), 500):
    r_reg = requests.post(f"{API_URL}/elections/{ELECTION_ID}/registry", json={"voters_pubkeys": pubkeys[i:i+500]})
    if r_reg.status_code != 200:
        print(f"[-] Błąd rejestracji (Whitelist): {r_reg.text}")
        exit()
print("[+] Wszyscy wyborcy zarejestrowani pomyślnie.")

print("\n--- START TESTU OBCIĄŻENIOWEGO ---")
tx_start = time.time()
success_count = 0
error_msg = ""

for priv, pub in voters:
    tx_data = {
        "election_id": ELECTION_ID,
        "voter_pubkey": pub,
        "candidate_id": "Kandydat_A",
        "nonce": 0,
        "timestamp": int(time.time()),
    }
    
    d_canonical = json.dumps(tx_data, sort_keys=True).encode()
    tx_data["signature"] = sign(priv, d_canonical)
    
    r_tx = requests.post(f"{API_URL}/tx", json=tx_data)
    if r_tx.status_code == 200:
        success_count += 1
    else:
        error_msg = r_tx.text 

tx_end = time.time()
print(f"\nWysłano {NUM_VOTERS} transakcji w {tx_end - tx_start:.2f} s.")
print(f"Udane: {success_count} / {NUM_VOTERS}")
if success_count < NUM_VOTERS:
    print(f"[-] Przykładowy błąd z serwera: {error_msg}")

print("\n5. Zamykanie transakcji w bloku (Propose & Finalize)...")
mine_start = time.time()
r_prop = requests.post(f"{API_URL}/propose")
if r_prop.status_code == 200:
    r_fin = requests.post(f"{API_URL}/finalize", json=r_prop.json())
    mine_end = time.time()
    print(f"[+] Blok sfinalizowany w {mine_end - mine_start:.2f} s. Status HTTP: {r_fin.status_code}")
else:
    print(f"[-] Błąd podczas tworzenia bloku (/propose): {r_prop.text}")