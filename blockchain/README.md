# 🌊 TIDE — Blockchain-Based Blue Carbon Registry & Living Credit System

> **Problem Statement ID:** SIH25038 — _Blockchain-Based Blue Carbon Registry (MRV System)_  
> **Ministry:** Ministry of Earth Sciences (MoES), Smart India Hackathon  
> **Role:** Blockchain Lead (M4)  
> **Standard:** ERC-1155 Semi-Fungible Tokens (OpenZeppelin v5) with Dynamic Living Credit State Machine

---

## 📌 Executive Overview

The **TIDE (Trusted Intelligent Digital Ecosystem Registry)** blockchain layer is not a simple "tokenize once and stop" marketplace token. Traditional carbon offset projects issue static tokens that remain tradeable even if the underlying mangrove forest dies or suffers severe degradation.

**Our Core Differentiator:**

> _"Anyone can tokenize a tree when it's planted. TIDE is the registry that keeps watching after the credit is issued — and automatically flags or freezes the credit on-chain the moment the environmental claim stops being true."_

---

## 🛠 Living Credit State Machine

Each carbon credit token batch represents verified conservative lower-bound carbon (`C_lower`) for a specific plot and vintage year. On-chain transfers are governed by a dynamic state machine:

```
    ┌──────────┐
    │ PROPOSED │ (Plot registered with IPFS boundary polygon)
    └────┬─────┘
         │ Auditor approval & minting (lower-bound C_lower)
         ▼
    ┌──────────┐
    │  ACTIVE  │ ◄──────┐ (Credit tradeable & transferable)
    └────┬─────┘        │
         │              │ Auditor reverification after field inspection
         │ Continuous   │
         │ MRV Anomaly  │
         │ (NDVI drop)  │
         ▼              │
    ┌──────────┐        │
    │  FROZEN  ├────────┘ (Transfers BLOCKED on-chain!)
    └────┬─────┘
         │ Permanent loss confirmed
         ▼
    ┌──────────┐
    │ REVOKED  │ (Permanently invalidated)
    └──────────┘

    [ RETIRED ] ───► Carbon offset claimed by buyer, tokens burned on-chain
```

---

## 📁 Repository Structure

```
blockchain/
├── contracts/
│   └── TIDEBlueCarbonRegistry.sol    # Core ERC-1155 Living Credit Smart Contract
├── test/
│   └── TIDEBlueCarbonRegistry.test.js # Hardhat unit tests (100% pass)
├── scripts/
│   ├── deploy.js                      # Network deployment script
│   └── simulate-oracle-events.js      # Interactive 9-scene demo simulation
├── sdk/
│   ├── index.js                       # Main TIDE SDK class for teammates
│   ├── helper.js                      # Status formatting & contract initialization
│   ├── contract-config.json           # Exported contract addresses & network info
│   └── abi/
│       └── TIDEBlueCarbonRegistryABI.json # Contract ABI JSON
├── hardhat.config.js                  # Hardhat configuration (Solidity 0.8.24, Cancun EVM)
├── package.json                       # Dependencies & npm scripts
└── README.md                          # Teammate integration guide & documentation
```

---

## 🚀 Quick Start Guide

### 1. Installation

```bash
cd blockchain
npm install
```

### 2. Compile Smart Contracts

```bash
npm run compile
```

### 3. Run Automated Unit Tests

```bash
npm run test
```

### 4. Deploy to Local Hardhat Network

```bash
# Terminal 1: Start local node
npx hardhat node

# Terminal 2: Deploy contract
npm run deploy:local
```

### 5. Run Live Oracle Continuous MRV Simulation

```bash
npm run simulate
```

---

## 🤝 Teammate Web Dashboard Integration Guide

This guide explains how **Frontend Lead (M6)** and **Backend Lead (M5)** can seamlessly connect their applications to the TIDE Blockchain Layer.

---

### A. Frontend Web Dashboard Integration (React / Next.js / HTML)

#### 1. Importing the SDK / ABIs

Copy `blockchain/sdk/contract-config.json` and `blockchain/sdk/abi/TIDEBlueCarbonRegistryABI.json` into your web project or import directly:

```javascript
import { ethers } from "ethers";
import { TIDEBlockchainSDK, CreditStatusMap } from "./blockchain/sdk";

// Initialize with Browser Wallet (MetaMask)
async function connectWalletAndSDK() {
  if (!window.ethereum) throw new Error("MetaMask not found!");

  const provider = new ethers.BrowserProvider(window.ethereum);
  const signer = await provider.getSigner();

  const tideSDK = new TIDEBlockchainSDK(signer);
  return { provider, signer, tideSDK };
}
```

#### 2. Displaying Credit Status & Metadata

```javascript
async function renderCreditCard(tokenId) {
  const credit = await tideSDK.getCreditBatch(tokenId);

  console.log(`Credit #${credit.tokenId} - Plot: ${credit.plotId}`);
  console.log(`Status: ${credit.statusLabel}`); // e.g. "Active & Tradeable" or "Frozen / Anomaly Alert"
  console.log(`Status Color Badge: ${credit.statusColor}`); // Green (#22c55e) or Red (#ef4444)
  console.log(`Lower-bound Carbon: ${credit.lowerBoundCarbonTonnes} tCO2e`);
  console.log(`Is Transferable: ${credit.isTransferable}`);
}
```

#### 3. Buyer Retiring Carbon Credits (Offset Certificate)

```javascript
async function handleRetire(
  tokenId,
  amountTonnes,
  beneficiaryName,
  offsetReason,
) {
  try {
    const res = await tideSDK.retireCredit(
      tokenId,
      amountTonnes,
      beneficiaryName,
      offsetReason,
    );
    alert(`Success! Carbon Retired. Tx Hash: ${res.txHash}`);
  } catch (err) {
    alert(`Retirement failed: ${err.message}`);
  }
}
```

#### 4. Subscribing to Real-Time Event Alerts (Toast Notifications)

```javascript
tideSDK.onCreditStatusUpdated((event) => {
  if (event.newStatusCode === 3) {
    // FROZEN
    showToastAlert(
      `🚨 ALERT: Credit #${event.tokenId} has been FROZEN! Reason: ${event.reason}`,
    );
  }
});
```

---

### B. Backend MRV Engine / Oracle Integration (Node.js / Express)

#### 1. Automated Freeze Trigger (When Sensor/Satellite Disagrees)

```javascript
const { ethers } = require("ethers");
const { TIDEBlockchainSDK } = require("./blockchain/sdk");

// Connect backend with Oracle Private Key
const provider = new ethers.JsonRpcProvider("http://127.0.0.1:8545");
const oracleWallet = new ethers.Wallet(
  process.env.ORACLE_PRIVATE_KEY,
  provider,
);
const oracleSDK = new TIDEBlockchainSDK(oracleWallet);

// Continuous MRV Pipeline callback
async function onEcosystemAnomalyDetected(
  tokenId,
  ndviDropPercent,
  evidenceIpfsCid,
) {
  if (ndviDropPercent > 20) {
    console.log(
      `Vegetation loss > 20% detected for Token #${tokenId}. Executing On-Chain Freeze...`,
    );

    const result = await oracleSDK.freezeCredit(
      tokenId,
      `Continuous MRV Alert: Sentinel-2 NDVI dropped by ${ndviDropPercent}%. Evidence: ${evidenceIpfsCid}`,
    );

    console.log(`On-Chain Freeze Confirmed. Tx Hash: ${result.txHash}`);
  }
}
```

---

### C. Python Integration (Flask / FastAPI / Web3.py)

If your backend is written in Python, use `web3.py` with the exported ABI:

```python
import json
from web3 import Web3

# Connect to local Hardhat node
w3 = Web3(Web3.HTTPProvider("http://127.0.0.1:8545"))

# Load ABI and Config
with open("./blockchain/sdk/contract-config.json") as f:
    config = json.load(f)

with open("./blockchain/sdk/abi/TIDEBlueCarbonRegistryABI.json") as f:
    abi = json.load(f)

contract = w3.eth.contract(address=config["contractAddress"], abi=abi)

def check_credit_status(token_id):
    batch = contract.functions.creditBatches(token_id).call()
    status_code = batch[9] # Status enum
    is_transferable = contract.functions.isTransferable(token_id).call()
    return {
        "token_id": token_id,
        "status_code": status_code,
        "lower_bound_tonnes": batch[4],
        "health_score": batch[7],
        "is_transferable": is_transferable
    }
```

---

## 🛡 Verification & Test Results

Run `npm run test` inside `blockchain/` to verify smart contract execution:

```
  TIDEBlueCarbonRegistry
    Deployment & Setup
      ✔ Should assign correct roles and metadata
    Plot Registration
      ✔ Should allow registering a new mangrove plot
      ✔ Should fail if plot ID is already registered or empty
    Living Carbon Credit Minting (C_lower)
      ✔ Should allow Auditor to mint living credits based on conservative lower bound
      ✔ Should reject non-Auditors from minting credits
      ✔ Should validate parameters (lower bound <= total estimate)
    Continuous Post-Issuance MRV & Transfer Restrictions
      ✔ Should allow transfer when credit status is ACTIVE
      ✔ Should block transfers when Oracle triggers a Freeze due to anomaly/NDVI drop
      ✔ Should auto-freeze if continuous MRV health score drops below 50%
      ✔ Should allow Auditor to reverify frozen credit back to ACTIVE
      ✔ Should permanently block transfers if Auditor revokes credit
    Carbon Retirement & Offsetting
      ✔ Should burn credits and emit CarbonRetired event when user retires carbon
      ✔ Should fail if user tries to retire frozen or revoked credits

  13 passing (1s)
```

---

## 🏆 SIH Pitch One-Liner

> _"Traditional registries tokenize carbon once and walk away. TIDE maintains a live smart-contract claim on Polygon testnet whose on-chain transferability changes with the physical health of the mangrove ecosystem."_
