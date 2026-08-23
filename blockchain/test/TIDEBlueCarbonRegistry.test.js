const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("TIDEBlueCarbonRegistry", function () {
  let registry;
  let admin, auditor, oracle, user1, user2;
  const BASE_URI = "https://api.tide-bluecarbon.org/metadata/";

  beforeEach(async function () {
    [admin, auditor, oracle, user1, user2] = await ethers.getSigners();

    const TIDEContract = await ethers.getContractFactory("TIDEBlueCarbonRegistry");
    registry = await TIDEContract.deploy(BASE_URI);
    await registry.waitForDeployment();

    // Grant roles
    const AUDITOR_ROLE = await registry.AUDITOR_ROLE();
    const ORACLE_ROLE = await registry.ORACLE_ROLE();

    await registry.grantRole(AUDITOR_ROLE, auditor.address);
    await registry.grantRole(ORACLE_ROLE, oracle.address);
  });

  describe("Deployment & Setup", function () {
    it("Should assign correct roles and metadata", async function () {
      const DEFAULT_ADMIN_ROLE = await registry.DEFAULT_ADMIN_ROLE();
      const AUDITOR_ROLE = await registry.AUDITOR_ROLE();
      const ORACLE_ROLE = await registry.ORACLE_ROLE();

      expect(await registry.hasRole(DEFAULT_ADMIN_ROLE, admin.address)).to.be.true;
      expect(await registry.hasRole(AUDITOR_ROLE, auditor.address)).to.be.true;
      expect(await registry.hasRole(ORACLE_ROLE, oracle.address)).to.be.true;
      expect(await registry.name()).to.equal("TIDE Living Blue Carbon Credit");
      expect(await registry.symbol()).to.equal("TIDE-BCC");
    });
  });

  describe("Plot Registration", function () {
    it("Should allow registering a new mangrove plot", async function () {
      await expect(
        registry.registerPlot("MNG-001", "Sundarbans Sector A", "ipfs://QmBoundary123", "Mangrove", 50)
      )
        .to.emit(registry, "PlotRegistered")
        .withArgs("MNG-001", "Sundarbans Sector A", "ipfs://QmBoundary123", "Mangrove", 50, admin.address);

      const plot = await registry.plots("MNG-001");
      expect(plot.isRegistered).to.be.true;
      expect(plot.name).to.equal("Sundarbans Sector A");
      expect(plot.areaHectares).to.equal(50);
    });

    it("Should fail if plot ID is already registered or empty", async function () {
      await registry.registerPlot("MNG-001", "Sundarbans Sector A", "ipfs://QmBoundary123", "Mangrove", 50);

      await expect(
        registry.registerPlot("MNG-001", "Sundarbans Sector A", "ipfs://QmBoundary123", "Mangrove", 50)
      ).to.be.revertedWith("TIDE: Plot already registered");

      await expect(
        registry.registerPlot("", "Empty ID Plot", "ipfs://QmBoundary", "Mangrove", 10)
      ).to.be.revertedWith("TIDE: Plot ID cannot be empty");
    });
  });

  describe("Living Carbon Credit Minting (C_lower)", function () {
    beforeEach(async function () {
      await registry.registerPlot("MNG-001", "Sundarbans Sector A", "ipfs://QmBoundary123", "Mangrove", 50);
    });

    it("Should allow Auditor to mint living credits based on conservative lower bound", async function () {
      // 42 tCO2e total estimate, 32 tCO2e lower bound (C_lower), 90% confidence, 87% health score
      await expect(
        registry.connect(auditor).mintLivingCredit(
          user1.address,
          "MNG-001",
          2025,
          42,
          32,
          90,
          87,
          "ipfs://QmEvidence123"
        )
      )
        .to.emit(registry, "CreditBatchMinted")
        .withArgs(1, "MNG-001", 2025, 42, 32, 90, 87, "ipfs://QmEvidence123", user1.address);

      const balance = await registry.balanceOf(user1.address, 1);
      expect(balance).to.equal(32); // Exact lower-bound amount minted

      const batch = await registry.creditBatches(1);
      expect(batch.plotId).to.equal("MNG-001");
      expect(batch.lowerBoundCarbonTonnes).to.equal(32);
      expect(batch.status).to.equal(1); // ACTIVE
    });

    it("Should reject non-Auditors from minting credits", async function () {
      await expect(
        registry.connect(user1).mintLivingCredit(
          user1.address,
          "MNG-001",
          2025,
          42,
          32,
          90,
          87,
          "ipfs://QmEvidence123"
        )
      ).to.be.revertedWithCustomError(registry, "AccessControlUnauthorizedAccount");
    });

    it("Should validate parameters (lower bound <= total estimate)", async function () {
      await expect(
        registry.connect(auditor).mintLivingCredit(
          user1.address,
          "MNG-001",
          2025,
          30,
          40, // lower bound > total estimate
          90,
          87,
          "ipfs://QmEvidence123"
        )
      ).to.be.revertedWith("TIDE: Lower bound cannot exceed total estimate");
    });
  });

  describe("Continuous Post-Issuance MRV & Transfer Restrictions", function () {
    let tokenId;

    beforeEach(async function () {
      await registry.registerPlot("MNG-001", "Sundarbans Sector A", "ipfs://QmBoundary123", "Mangrove", 50);
      const tx = await registry.connect(auditor).mintLivingCredit(
        user1.address,
        "MNG-001",
        2025,
        42,
        32,
        90,
        87,
        "ipfs://QmEvidence123"
      );
      const receipt = await tx.wait();
      tokenId = 1;
    });

    it("Should allow transfer when credit status is ACTIVE", async function () {
      expect(await registry.isTransferable(tokenId)).to.be.true;

      await registry.connect(user1).safeTransferFrom(user1.address, user2.address, tokenId, 10, "0x");
      expect(await registry.balanceOf(user2.address, tokenId)).to.equal(10);
      expect(await registry.balanceOf(user1.address, tokenId)).to.equal(22);
    });

    it("Should block transfers when Oracle triggers a Freeze due to anomaly/NDVI drop", async function () {
      await registry.connect(oracle).freezeCredit(tokenId, "Continuous MRV alert: NDVI drop > 20% detected");

      expect(await registry.isTransferable(tokenId)).to.be.false;

      const batch = await registry.creditBatches(tokenId);
      expect(batch.status).to.equal(3); // FROZEN

      await expect(
        registry.connect(user1).safeTransferFrom(user1.address, user2.address, tokenId, 5, "0x")
      ).to.be.revertedWith("TIDE: Transfer blocked! Living Credit status is FROZEN, UNDER_REVIEW, or REVOKED");
    });

    it("Should auto-freeze if continuous MRV health score drops below 50%", async function () {
      await expect(
        registry.connect(oracle).updateHealthScore(tokenId, 42, "ipfs://QmDegradedEvidence")
      )
        .to.emit(registry, "CreditStatusUpdated")
        .withArgs(tokenId, 1, 3, "Auto-frozen: Ecosystem Health Score dropped below 50%", oracle.address);

      expect(await registry.isTransferable(tokenId)).to.be.false;
    });

    it("Should allow Auditor to reverify frozen credit back to ACTIVE", async function () {
      await registry.connect(oracle).freezeCredit(tokenId, "Anomaly detected");
      expect(await registry.isTransferable(tokenId)).to.be.false;

      await registry.connect(auditor).reverifyCredit(tokenId, "Field survey cleared anomaly", 85);
      expect(await registry.isTransferable(tokenId)).to.be.true;

      const batch = await registry.creditBatches(tokenId);
      expect(batch.status).to.equal(4); // REVERIFIED

      // Transfer should work now
      await registry.connect(user1).safeTransferFrom(user1.address, user2.address, tokenId, 5, "0x");
      expect(await registry.balanceOf(user2.address, tokenId)).to.equal(5);
    });

    it("Should permanently block transfers if Auditor revokes credit", async function () {
      await registry.connect(auditor).revokeCredit(tokenId, "Permanent mangrove loss confirmed");

      const batch = await registry.creditBatches(tokenId);
      expect(batch.status).to.equal(5); // REVOKED

      await expect(
        registry.connect(user1).safeTransferFrom(user1.address, user2.address, tokenId, 5, "0x")
      ).to.be.revertedWith("TIDE: Transfer blocked! Living Credit status is FROZEN, UNDER_REVIEW, or REVOKED");
    });
  });

  describe("Carbon Retirement & Offsetting", function () {
    let tokenId;

    beforeEach(async function () {
      await registry.registerPlot("MNG-001", "Sundarbans Sector A", "ipfs://QmBoundary123", "Mangrove", 50);
      await registry.connect(auditor).mintLivingCredit(
        user1.address,
        "MNG-001",
        2025,
        42,
        32,
        90,
        87,
        "ipfs://QmEvidence123"
      );
      tokenId = 1;
    });

    it("Should burn credits and emit CarbonRetired event when user retires carbon", async function () {
      await expect(
        registry.connect(user1).retireCredit(
          tokenId,
          10,
          "Green Corp India",
          "Offsetting FY25 Scope 1 & 2 Emissions"
        )
      )
        .to.emit(registry, "CarbonRetired")
        .withArgs(tokenId, user1.address, 10, "Green Corp India", "Offsetting FY25 Scope 1 & 2 Emissions", (val) => val > 0);

      // Balance reduced from 32 to 22
      expect(await registry.balanceOf(user1.address, tokenId)).to.equal(22);

      const history = await registry.getRetirementHistory(tokenId);
      expect(history.length).to.equal(1);
      expect(history[0].beneficiaryName).to.equal("Green Corp India");
      expect(history[0].amountTonnes).to.equal(10);
    });

    it("Should fail if user tries to retire frozen or revoked credits", async function () {
      await registry.connect(oracle).freezeCredit(tokenId, "Frozen due to risk alert");

      await expect(
        registry.connect(user1).retireCredit(tokenId, 5, "Corp X", "Offset")
      ).to.be.revertedWith("TIDE: Cannot retire frozen, under review, or revoked credits");
    });
  });
});
