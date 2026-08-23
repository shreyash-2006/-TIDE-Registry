const { ethers } = require("ethers");
const contractConfig = require("./contract-config.json");
const contractABI = require("./abi/TIDEBlueCarbonRegistryABI.json");

/**
 * Get an initialized instance of the TIDEBlueCarbonRegistry contract
 * @param {ethers.Signer | ethers.Provider} signerOrProvider - Ethers Signer or Provider instance
 * @returns {ethers.Contract} Initialized Contract
 */
function getTIDEContract(signerOrProvider) {
  if (!contractConfig.contractAddress || contractConfig.contractAddress === "") {
    throw new Error("TIDE SDK Error: Contract address not configured in contract-config.json");
  }
  return new ethers.Contract(contractConfig.contractAddress, contractABI, signerOrProvider);
}

/**
 * Status Code Helper Mapping
 */
const CreditStatusMap = {
  0: { code: "PROPOSED", label: "Proposed / Pending Verification", color: "#eab308" },
  1: { code: "ACTIVE", label: "Active & Tradeable", color: "#22c55e" },
  2: { code: "UNDER_REVIEW", label: "Under Manual Review", color: "#f97316" },
  3: { code: "FROZEN", label: "Frozen / Anomaly Alert", color: "#ef4444" },
  4: { code: "REVERIFIED", label: "Reverified & Active", color: "#10b981" },
  5: { code: "REVOKED", label: "Revoked / Invalidated", color: "#6b7280" },
  6: { code: "RETIRED", label: "Retired / Offset Claimed", color: "#8b5cf6" }
};

/**
 * Format raw credit batch struct from contract into clean JS object
 * @param {Object} rawBatch - Raw tuple returned from smart contract
 * @returns {Object} Formatted credit object
 */
function formatCreditBatch(rawBatch) {
  const statusCode = Number(rawBatch.status);
  const statusInfo = CreditStatusMap[statusCode] || { code: "UNKNOWN", label: "Unknown Status", color: "#6b7280" };

  return {
    tokenId: Number(rawBatch.tokenId),
    plotId: rawBatch.plotId,
    vintageYear: Number(rawBatch.vintageYear),
    totalEstimatedCarbonTonnes: Number(rawBatch.totalEstimatedCarbonTonnes),
    lowerBoundCarbonTonnes: Number(rawBatch.lowerBoundCarbonTonnes), // C_lower
    confidenceScore: Number(rawBatch.confidenceScore),
    healthScoreAtIssuance: Number(rawBatch.healthScoreAtIssuance),
    currentHealthScore: Number(rawBatch.currentHealthScore),
    evidenceIpfsCid: rawBatch.evidenceIpfsCid,
    status: statusInfo.code,
    statusCode: statusCode,
    statusLabel: statusInfo.label,
    statusColor: statusInfo.color,
    isTransferable: statusCode === 1 || statusCode === 4,
    issuanceTimestamp: new Date(Number(rawBatch.issuanceTimestamp) * 1000).toISOString(),
    lastVerifiedTimestamp: new Date(Number(rawBatch.lastVerifiedTimestamp) * 1000).toISOString(),
    statusReason: rawBatch.statusReason
  };
}

module.exports = {
  getTIDEContract,
  CreditStatusMap,
  formatCreditBatch,
  contractConfig,
  contractABI
};
