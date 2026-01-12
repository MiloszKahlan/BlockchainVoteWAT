# VoteBlock – Blockchain-Based Voting System  

## Overview

VoteBlock is a Proof of Authority (PoA) blockchain implementation designed specifically for electronic voting scenarios.  
It features:

- a REST API node responsible for consensus and state management
- a CLI client used for secure, local vote signing and interaction with the network

The system focuses on transparency, integrity, and cryptographic security while remaining simple enough for educational and research purposes.

---

## Key Features

- **Proof of Authority (PoA)**  
  A permissioned consensus mechanism where only authorized Validator nodes can propose and finalize blocks.

- **Client-Side Signing**  
  Uses Ed25519 elliptic curve cryptography.  
  Private keys never leave the client’s device; only signed transactions are sent to the network.

- **Tamper-Evident History**  
  Merkle Trees and hash-linked blocks ensure immutability and data integrity.

- **State Persistence**  
  Blockchain state and election configurations are stored persistently in JSON files and survive node restarts.

- **REST API**  
  High-performance API built with FastAPI and Uvicorn.

---

## Prerequisites & Installation

### Requirements

- Python 3.10 or higher

---

### Clone the Repository

Clone the repository and navigate to the application directory.

```bash
git clone [https://github.com/twoj-nick/voteblock.git](https://github.com/twoj-nick/voteblock.git)
cd voteblock/app
```

### Set Up a Virtual Environment

Create and activate a Python virtual environment appropriate for your operating system.

```bash
python -m venv venv
    
# Windows:
venv\Scripts\activate
# Linux/MacOS:
source ../venv/bin/activate
```

### Install Dependencies

Install all required Python dependencies using the package manager.

```bash
pip install fastapi uvicorn cryptography requests pydantic
```

## Comprehensive Testing Guide

To test the full lifecycle of a vote, you need two separate terminal windows.

## Terminal 1: Blockchain Node (Server)

```bash
uvicorn api:app --reload
```

### Important – Validator Key

After startup, check the logs carefully.  
You will see a line similar to:

My Public Key (Validator ID): `<SOME_LONG_KEY_STRING>`

Copy this key.  
You will need it to authorize this node as a validator.

### API Access

- API URL: http://127.0.0.1:8000  
- Swagger UI: http://127.0.0.1:8000/docs

---

## Terminal 2: Client (CLI)

In the second terminal, ensure the virtual environment is activated.  
All interactions with the system are performed using `cli.py`.

---

### Step 1: Authorize the Validator

You must explicitly add the running node to the validator list.

Replace `<NODE_KEY>` with the key copied from Terminal 1.

```bash
# Replace <NODE_KEY> with the key copied from Terminal 1
python cli.py set-validator <NODE_KEY>
```

### Step 2: Generate Voter Identity

Create a secure wallet (Ed25519 key pair) for a voter.

As a result:
- a file named `voter_key.json` is created
- copy the public key displayed in the terminal

```bash
python cli.py keygen
```

### Step 3: Create an Election (Admin Action)

Initialize a new election with a unique identifier and a list of candidates.

```bash
python cli.py create-election presidential-2025 "Alice" "Bob"
```

### Step 4: Register the Voter (Admin Action)

Add the voter’s public key to the election whitelist.

Replace `<VOTER_KEY>` with the public key generated in the previous step.

```bash
# Replace <VOTER_KEY> with the key from Step 2
python cli.py register presidential-2025 <VOTER_KEY>
```

### Step 5: Cast a Vote

```bash
python cli.py vote presidential-2025 Alice
```

### Step 6: Mining & Consensus (Manual Trigger)

In this educational MVP, the consensus process is triggered manually to demonstrate the internal mechanics of block creation and validation.

1. Open Swagger UI in your browser.
2. Navigate to the POST `/api/propose` endpoint.
3. Execute the request and copy the full JSON response body.
4. Navigate to the POST `/api/finalize` endpoint.
5. Paste the copied JSON into the request body and execute the request.

If the response status is 200 OK, the block has been validated and appended to the blockchain.

---

### Step 7: Verify Results

Verify the election results and inspect the current blockchain status.

```bash
python cli.py results presidential-2025
python cli.py info
```

---

## Resetting the System

To completely reset the blockchain and all election data:

1. Stop the running server.
2. Delete the persistent data directory.
3. Restart the server.

```bash
rm -rf data
```

Note:  
Node identity (`node_key.json`) and voter identity (`voter_key.json`) are stored in the project root directory and are not removed automatically.

---

## Academic Context

This project was developed as part of a Master’s Thesis and demonstrates:

- practical application of blockchain technology
- cryptographic vote integrity
- permissioned consensus using Proof of Authority
- transparent and auditable electronic voting systems
