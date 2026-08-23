const { ethers } = require("ethers");
const {
  getTIDEContract,
  CreditStatusMap,
  formatCreditBatch,
  contractConfig,
  contractABI
} = require("./helper");

class TIDEBlockchainSDK {
  /**
   * @param {ethers.Provider | ethers.Signer} signerOrProvider 
   */
  constructor(signerOrProvider) {
    this.contract = getTIDEContract(signerOrProvider);
    this.signerOrProvider = signerOrProvider;
  }

  /**
   * Fetch details of a registered plot
   * @param {string} plotId 
   */
  async getPlot(plotId) {
    const plot = await this.contract.plots(plotId);
    if (!plot.isRegistered) return null;
    return {
      plotId: plot.plotId,
      name: plot.name,
      boundaryIpfsCid: plot.boundaryIpfsCid,
      ecosystemType: plot.ecosystemType,
      areaHectares: Number(plot.areaHectares),
      registrationTimestamp: new Date(Number(plot.registrationTimestamp) * 1000).toISOString(),
      isRegistered: plot.isRegistered
    };
  }

  /**
   * Fetch full metadata for a Living Credit batch
   * @param {number} tokenId 
   */
  async getCreditBatch(tokenId) {
    const rawBatch = await this.contract.creditBatches(tokenId);
    if (Number(rawBatch.tokenId) === 0) return null;
    return formatCreditBatch(rawBatch);
  }

  /**
   * Register a new plot (Requires Admin / Developer account)
   */
  async registerPlot(plotId, plotName, boundaryIpfsCid, ecosystemType, areaHectares) {
    const tx = await this.contract.registerPlot(plotId, plotName, boundaryIpfsCid, ecosystemType, areaHectares);
    const receipt = await tx.wait();
    return { txHash: receipt.hash, blockNumber: receipt.blockNumber };
  }

  /**
   * Mint Living Credits for a verified plot (Requires AUDITOR_ROLE)
   */
  async mintLivingCredit(toAddress, plotId, vintageYear, totalEstimate, lowerBound, confidenceScore, healthScore, evidenceCid) {
    const tx = await this.contract.mintLivingCredit(
      toAddress,
      plotId,
      vintageYear,
      totalEstimate,
      lowerBound,
      confidenceScore,
      healthScore,
      evidenceCid
    );
    const receipt = await tx.wait();
    return { txHash: receipt.hash, blockNumber: receipt.blockNumber };
  }

  /**
   * Trigger Oracle Freeze when continuous MRV detects anomaly (Requires ORACLE_ROLE or AUDITOR_ROLE)
   */
  async freezeCredit(tokenId, reason) {
    const tx = await this.contract.freezeCredit(tokenId, reason);
    const receipt = await tx.wait();
    return { txHash: receipt.hash, blockNumber: receipt.blockNumber };
  }

  /**
   * Reverify a frozen/under-review credit (Requires AUDITOR_ROLE)
   */
  async reverifyCredit(tokenId, reason, newHealthScore) {
    const tx = await this.contract.reverifyCredit(tokenId, reason, newHealthScore);
    const receipt = await tx.wait();
    return { txHash: receipt.hash, blockNumber: receipt.blockNumber };
  }

  /**
   * Update ecosystem health score dynamically via continuous MRV feed (Requires ORACLE_ROLE)
   */
  async updateHealthScore(tokenId, newHealthScore, evidenceCid) {
    const tx = await this.contract.updateHealthScore(tokenId, newHealthScore, evidenceCid);
    const receipt = await tx.wait();
    return { txHash: receipt.hash, blockNumber: receipt.blockNumber };
  }

  /**
   * Retire credits for carbon offset claim (Requires credit holder wallet)
   */
  async retireCredit(tokenId, amountTonnes, beneficiaryName, offsetReason) {
    const tx = await this.contract.retireCredit(tokenId, amountTonnes, beneficiaryName, offsetReason);
    const receipt = await tx.wait();
    return { txHash: receipt.hash, blockNumber: receipt.blockNumber };
  }

  /**
   * Get immutable retirement history for a token ID
   */
  async getRetirementHistory(tokenId) {
    const history = await this.contract.getRetirementHistory(tokenId);
    return history.map(rec => ({
      tokenId: Number(rec.tokenId),
      retiree: rec.retiree,
      amountTonnes: Number(rec.amountTonnes),
      beneficiaryName: rec.beneficiaryName,
      offsetReason: rec.offsetReason,
      timestamp: new Date(Number(rec.timestamp) * 1000).toISOString()
    }));
  }

  /**
   * Listen for real-time blockchain events (Useful for Web Dashboard notification widgets)
   */
  onCreditStatusUpdated(callback) {
    this.contract.on("CreditStatusUpdated", (tokenId, prevStatus, newStatus, reason, updatedBy, event) => {
      callback({
        tokenId: Number(tokenId),
        prevStatusCode: Number(prevStatus),
        newStatusCode: Number(newStatus),
        newStatusInfo: CreditStatusMap[Number(newStatus)],
        reason,
        updatedBy,
        txHash: event.log.transactionHash
      });
    });
  }

  onCarbonRetired(callback) {
    this.contract.on("CarbonRetired", (tokenId, retiree, amountTonnes, beneficiaryName, offsetReason, timestamp, event) => {
      callback({
        tokenId: Number(tokenId),
        retiree,
        amountTonnes: Number(amountTonnes),
        beneficiaryName,
        offsetReason,
        timestamp: new Date(Number(timestamp) * 1000).toISOString(),
        txHash: event.log.transactionHash
      });
    });
  }
}

module.exports = {
  TIDEBlockchainSDK,
  getTIDEContract,
  CreditStatusMap,
  formatCreditBatch,
  contractConfig,
  contractABI
};
