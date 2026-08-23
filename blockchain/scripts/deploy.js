const { ethers } = require("hardhat");
const fs = require("fs");
const path = require("path");

async function main() {
  console.log("=================================================");
  console.log("TIDE Blue Carbon Registry - Smart Contract Deployment");
  console.log("=================================================");

  const [deployer, auditor, oracle, recipient] = await ethers.getSigners();

  console.log(`Deployer address: ${deployer.address}`);
  console.log(`Deployer balance: ${ethers.formatEther(await ethers.provider.getBalance(deployer.address))} ETH`);

  const BASE_URI = "https://api.tide-bluecarbon.org/metadata/";
  const TIDEContract = await ethers.getContractFactory("TIDEBlueCarbonRegistry");

  console.log("\n1. Deploying TIDEBlueCarbonRegistry contract...");
  const registry = await TIDEContract.deploy(BASE_URI);
  await registry.waitForDeployment();

  const contractAddress = await registry.getAddress();
  console.log(`✔ TIDEBlueCarbonRegistry deployed to: ${contractAddress}`);

  console.log("\n2. Setting up Roles (AUDITOR_ROLE & ORACLE_ROLE)...");
  const AUDITOR_ROLE = await registry.AUDITOR_ROLE();
  const ORACLE_ROLE = await registry.ORACLE_ROLE();

  if (auditor) {
    await (await registry.grantRole(AUDITOR_ROLE, auditor.address)).wait();
    console.log(`✔ Granted AUDITOR_ROLE to: ${auditor.address}`);
  }

  if (oracle) {
    await (await registry.grantRole(ORACLE_ROLE, oracle.address)).wait();
    console.log(`✔ Granted ORACLE_ROLE to: ${oracle.address}`);
  }

  console.log("\n3. Registering Sample Mangrove Plot (MNG-001)...");
  const plotTx = await registry.registerPlot(
    "MNG-001",
    "Sundarbans Delta Mangrove Restoration Plot Alpha",
    "ipfs://QmSundarbansBoundaryPolygon123",
    "Mangrove",
    50 // 50 Hectares
  );
  await plotTx.wait();
  console.log("✔ Registered plot MNG-001 (50 Ha, Sundarbans Delta)");

  console.log("\n4. Minting Initial Verified Living Credit Batch (Token ID #1)...");
  const mintTx = await registry.connect(auditor || deployer).mintLivingCredit(
    (recipient || deployer).address,
    "MNG-001",
    2025,
    42, // total estimated tCO2e
    32, // lower-bound C_lower creditable tCO2e
    90, // confidence score %
    88, // health score 88/100
    "ipfs://QmInitialMRVEvidenceBundle123"
  );
  await mintTx.wait();
  console.log(`✔ Minted 32 Living Carbon Credits (Token ID #1) to ${(recipient || deployer).address}`);

  // Export SDK Artifacts for Teammates
  console.log("\n5. Exporting SDK Config & ABIs for Frontend/Backend Teammates...");
  const sdkAbiDir = path.join(__dirname, "../sdk/abi");
  if (!fs.existsSync(sdkAbiDir)) {
    fs.mkdirSync(sdkAbiDir, { recursive: true });
  }

  const artifactPath = path.join(__dirname, "../artifacts/contracts/TIDEBlueCarbonRegistry.sol/TIDEBlueCarbonRegistry.json");
  let artifact = {};
  if (fs.existsSync(artifactPath)) {
    artifact = JSON.parse(fs.readFileSync(artifactPath, "utf8"));
  }

  const config = {
    network: (await ethers.provider.getNetwork()).name,
    chainId: Number((await ethers.provider.getNetwork()).chainId),
    contractAddress: contractAddress,
    deployer: deployer.address,
    auditor: auditor ? auditor.address : deployer.address,
    oracle: oracle ? oracle.address : deployer.address,
    deployedAt: new Date().toISOString()
  };

  fs.writeFileSync(path.join(__dirname, "../sdk/contract-config.json"), JSON.stringify(config, null, 2));
  if (artifact.abi) {
    fs.writeFileSync(path.join(sdkAbiDir, "TIDEBlueCarbonRegistryABI.json"), JSON.stringify(artifact.abi, null, 2));
  }

  console.log("✔ Contract Config written to: blockchain/sdk/contract-config.json");
  console.log("✔ Contract ABI written to:    blockchain/sdk/abi/TIDEBlueCarbonRegistryABI.json");

  console.log("\n=================================================");
  console.log("Deployment Complete!");
  console.log("=================================================");
}

main().catch((error) => {
  console.error("Deployment failed:", error);
  process.exitCode = 1;
});
