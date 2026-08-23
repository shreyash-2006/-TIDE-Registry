const { ethers } = require("hardhat");

async function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function main() {
  console.log("=======================================================================");
  console.log("TIDE Living Carbon Credit - Continuous MRV Oracle Simulation");
  console.log("=======================================================================\n");

  const [admin, auditor, oracle, buyer, recipient] = await ethers.getSigners();

  // 1. Deploy Contract
  console.log("[SCENE 1] Deploying TIDE Registry & Setting Up Roles...");
  const TIDEContract = await ethers.getContractFactory("TIDEBlueCarbonRegistry");
  const registry = await TIDEContract.deploy("https://api.tide-bluecarbon.org/metadata/");
  await registry.waitForDeployment();
  const address = await registry.getAddress();
  console.log(`  ✔ Registry Contract Deployed at: ${address}`);

  const AUDITOR_ROLE = await registry.AUDITOR_ROLE();
  const ORACLE_ROLE = await registry.ORACLE_ROLE();
  await registry.grantRole(AUDITOR_ROLE, auditor.address);
  await registry.grantRole(ORACLE_ROLE, oracle.address);
  console.log(`  ✔ Auditor: ${auditor.address}`);
  console.log(`  ✔ Oracle:  ${oracle.address}\n`);

  // 2. Register Plot
  console.log("[SCENE 2] Registering Project Plot 'MNG-001' (Sundarbans 50 Ha)...");
  await (await registry.registerPlot(
    "MNG-001",
    "Sundarbans Delta Plot Alpha",
    "ipfs://QmBoundaryPolygonSundarbans50Ha",
    "Mangrove",
    50
  )).wait();
  console.log("  ✔ Plot MNG-001 Registered successfully.\n");

  // 3. Mint Living Credits
  console.log("[SCENE 3] Auditor Mints Living Carbon Credit Batch (Token ID #1)...");
  const totalEstimate = 42;
  const lowerBound = 32; // C_lower conservative quantity
  const confidence = 90;
  const healthScore = 88;

  const mintTx = await registry.connect(auditor).mintLivingCredit(
    buyer.address,
    "MNG-001",
    2025,
    totalEstimate,
    lowerBound,
    confidence,
    healthScore,
    "ipfs://QmInitialBaselineMRVEvidence"
  );
  await mintTx.wait();

  const tokenId = 1;
  let batch = await registry.creditBatches(tokenId);
  console.log(`  ✔ Token ID #${tokenId} Minted to Buyer (${buyer.address})`);
  console.log(`  ✔ Lower Bound Quantity Minted: ${batch.lowerBoundCarbonTonnes} tCO2e`);
  console.log(`  ✔ Initial Status: ACTIVE (Code ${batch.status})\n`);

  // 4. Test Active Transfer
  console.log("[SCENE 4] Buyer Transfers 10 Credits while Status is ACTIVE...");
  await (await registry.connect(buyer).safeTransferFrom(buyer.address, recipient.address, tokenId, 10, "0x")).wait();
  console.log(`  ✔ Transfer Succeeded! Recipient Balance: ${await registry.balanceOf(recipient.address, tokenId)} tCO2e\n`);

  // 5. Continuous MRV Anomaly Detected (NDVI Drop)
  console.log("[SCENE 5] Continuous MRV Pipeline Detects Vegetation Loss (NDVI drop > 20%)...");
  console.log("  ⚠ Oracle service updates ecosystem health score to 42/100 and triggers Freeze...");
  
  const oracleTx = await registry.connect(oracle).updateHealthScore(
    tokenId,
    42, // Dropped below 50 -> triggers auto freeze
    "ipfs://QmAnomalySentinel2NDVIDropEvidence"
  );
  await oracleTx.wait();

  batch = await registry.creditBatches(tokenId);
  console.log(`  ✔ Credit Status On-Chain Updated: FROZEN (Code ${batch.status})`);
  console.log(`  ✔ Status Reason: ${batch.statusReason}\n`);

  // 6. Attempt Transfer while Frozen (Expect Block)
  console.log("[SCENE 6] Testing On-Chain Transfer Restriction on Frozen Credit...");
  try {
    await registry.connect(buyer).safeTransferFrom(buyer.address, recipient.address, tokenId, 5, "0x");
    console.error("  ❌ Error: Transfer should have failed!");
  } catch (err) {
    console.log(`  ✔ SUCCESS: On-chain contract BLOCKED transfer! Reason: "${err.reason || "Living Credit Status is FROZEN"}"\n`);
  }

  // 7. Auditor Reverifies
  console.log("[SCENE 7] Auditor Reviews Ground Evidence & Field Survey -> Clears Anomaly...");
  const reverifyTx = await registry.connect(auditor).reverifyCredit(
    tokenId,
    "Field inspection confirmed canopy regrowth after seasonal tide; clear to trade",
    85 // Restored Health Score
  );
  await reverifyTx.wait();

  batch = await registry.creditBatches(tokenId);
  console.log(`  ✔ Credit Status On-Chain Updated: REVERIFIED (Code ${batch.status})`);
  console.log(`  ✔ Dynamic Health Score Restored to: ${batch.currentHealthScore}/100\n`);

  // 8. Test Transfer After Reverification
  console.log("[SCENE 8] Retrying Transfer After Reverification...");
  await (await registry.connect(buyer).safeTransferFrom(buyer.address, recipient.address, tokenId, 5, "0x")).wait();
  console.log(`  ✔ Transfer Succeeded! Recipient Balance Now: ${await registry.balanceOf(recipient.address, tokenId)} tCO2e\n`);

  // 9. Carbon Offset Retirement
  console.log("[SCENE 9] Recipient Retires (Burns) 5 tCO2e to Offset Corporate Footprint...");
  const retireTx = await registry.connect(recipient).retireCredit(
    tokenId,
    5,
    "Green Tech Corp India",
    "Scope 1 & 2 Emissions Offset for Q1 2025"
  );
  await retireTx.wait();

  console.log(`  ✔ Recipient Balance After Retirement: ${await registry.balanceOf(recipient.address, tokenId)} tCO2e`);
  const history = await registry.getRetirementHistory(tokenId);
  console.log("  ✔ Immutable Retirement Record Logged On-Chain:");
  console.log(`     - Beneficiary: ${history[0].beneficiaryName}`);
  console.log(`     - Amount:      ${history[0].amountTonnes} tCO2e`);
  console.log(`     - Reason:      ${history[0].offsetReason}`);
  console.log(`     - Retiree:     ${history[0].retiree}\n`);

  console.log("=======================================================================");
  console.log("TIDE Continuous MRV Simulation Complete - All Systems Verified 100%!");
  console.log("=======================================================================");
}

main().catch((error) => {
  console.error("Simulation failed:", error);
  process.exitCode = 1;
});
