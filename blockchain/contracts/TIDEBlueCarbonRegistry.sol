// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import "@openzeppelin/contracts/token/ERC1155/extensions/ERC1155Supply.sol";
import "@openzeppelin/contracts/access/AccessControl.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import "@openzeppelin/contracts/utils/Strings.sol";

/**
 * @title TIDEBlueCarbonRegistry
 * @dev Trusted Intelligent Digital Ecosystem Registry (TIDE)
 * Smart contract implementing the Living Carbon Credit model for SIH25038.
 * Features:
 *  - ERC-1155 Semi-Fungible living credit minting tied to lower-bound carbon estimates (C_lower)
 *  - Continuous post-issuance MRV status machine (PROPOSED -> ACTIVE -> FROZEN -> REVERIFIED / REVOKED -> RETIRED)
 *  - Transfer blocking when environmental degradation triggers an Oracle freeze
 *  - Proof-of-Permanence evidence hash anchoring (IPFS CIDs)
 *  - Carbon retirement & certificate generation
 */
contract TIDEBlueCarbonRegistry is ERC1155Supply, AccessControl, ReentrancyGuard {
    using Strings for uint256;

    // Roles
    bytes32 public constant AUDITOR_ROLE = keccak256("AUDITOR_ROLE");
    bytes32 public constant ORACLE_ROLE = keccak256("ORACLE_ROLE");

    // Lifecycle Status Enum
    enum CreditStatus {
        PROPOSED,     // 0: Plot registered, initial baseline documentation uploaded
        ACTIVE,       // 1: Verified by Auditor, credits minted and active
        UNDER_REVIEW, // 2: Flagged for manual review due to data disagreement
        FROZEN,       // 3: Environmental anomaly detected (NDVI drop / sensor alert); transfers restricted
        REVERIFIED,   // 4: Auditor reverified and confirmed cleared after anomaly review
        REVOKED,      // 5: Permanent ecosystem failure/loss; credit permanently invalidated
        RETIRED       // 6: Carbon offset claimed by buyer and burned on-chain
    }

    // Structs
    struct PlotDetails {
        string plotId;
        string name;
        string boundaryIpfsCid;
        string ecosystemType;
        uint256 areaHectares;
        uint256 registrationTimestamp;
        bool isRegistered;
    }

    struct CreditBatch {
        uint256 tokenId;
        string plotId;
        uint256 vintageYear;
        uint256 totalEstimatedCarbonTonnes; // Raw estimated CO2e
        uint256 lowerBoundCarbonTonnes;     // Conservative lower-bound creditable CO2e (C_lower)
        uint256 confidenceScore;            // 0 - 100 percentage
        uint256 healthScoreAtIssuance;      // Ecosystem Health Score 0 - 100
        uint256 currentHealthScore;         // Dynamic Health Score 0 - 100
        string evidenceIpfsCid;             // Provenance evidence CID
        CreditStatus status;
        uint256 issuanceTimestamp;
        uint256 lastVerifiedTimestamp;
        string statusReason;
    }

    struct RetirementRecord {
        uint256 tokenId;
        address retiree;
        uint256 amountTonnes;
        string beneficiaryName;
        string offsetReason;
        uint256 timestamp;
    }

    // State Variables
    uint256 private _nextTokenId = 1;
    string public name = "TIDE Living Blue Carbon Credit";
    string public symbol = "TIDE-BCC";
    string private _baseTokenUri;

    // Storage Mappings
    mapping(string => PlotDetails) public plots;
    mapping(uint256 => CreditBatch) public creditBatches;
    mapping(uint256 => RetirementRecord[]) public retirementRecords;
    mapping(string => uint256[]) public plotToTokenIds;

    // Events
    event PlotRegistered(
        string indexed plotId,
        string name,
        string boundaryIpfsCid,
        string ecosystemType,
        uint256 areaHectares,
        address indexed registrar
    );

    event CreditBatchMinted(
        uint256 indexed tokenId,
        string indexed plotId,
        uint256 vintageYear,
        uint256 totalEstimatedCarbonTonnes,
        uint256 lowerBoundCarbonTonnes,
        uint256 confidenceScore,
        uint256 healthScore,
        string evidenceIpfsCid,
        address indexed recipient
    );

    event CreditStatusUpdated(
        uint256 indexed tokenId,
        CreditStatus indexed previousStatus,
        CreditStatus indexed newStatus,
        string reason,
        address updatedBy
    );

    event HealthScoreUpdated(
        uint256 indexed tokenId,
        uint256 oldScore,
        uint256 newScore,
        string evidenceIpfsCid,
        address updatedBy
    );

    event CarbonRetired(
        uint256 indexed tokenId,
        address indexed retiree,
        uint256 amountTonnes,
        string beneficiaryName,
        string offsetReason,
        uint256 timestamp
    );

    /**
     * @dev Constructor initializes roles and base URI
     * @param baseUri Base URI for metadata queries
     */
    constructor(string memory baseUri) ERC1155(baseUri) {
        _baseTokenUri = baseUri;
        _grantRole(DEFAULT_ADMIN_ROLE, msg.sender);
        _grantRole(AUDITOR_ROLE, msg.sender);
        _grantRole(ORACLE_ROLE, msg.sender);
    }

    /**
     * @dev Register a new Blue Carbon plot with boundary details
     */
    function registerPlot(
        string memory plotId,
        string memory plotName,
        string memory boundaryIpfsCid,
        string memory ecosystemType,
        uint256 areaHectares
    ) external {
        require(bytes(plotId).length > 0, "TIDE: Plot ID cannot be empty");
        require(!plots[plotId].isRegistered, "TIDE: Plot already registered");
        require(areaHectares > 0, "TIDE: Area must be greater than zero");

        plots[plotId] = PlotDetails({
            plotId: plotId,
            name: plotName,
            boundaryIpfsCid: boundaryIpfsCid,
            ecosystemType: ecosystemType,
            areaHectares: areaHectares,
            registrationTimestamp: block.timestamp,
            isRegistered: true
        });

        emit PlotRegistered(
            plotId,
            plotName,
            boundaryIpfsCid,
            ecosystemType,
            areaHectares,
            msg.sender
        );
    }

    /**
     * @dev Mint living carbon credits based on conservative lower-bound estimation (C_lower)
     * Only accounts with AUDITOR_ROLE can issue verified credits.
     */
    function mintLivingCredit(
        address to,
        string memory plotId,
        uint256 vintageYear,
        uint256 totalEstimatedCarbonTonnes,
        uint256 lowerBoundCarbonTonnes,
        uint256 confidenceScore,
        uint256 healthScore,
        string memory evidenceIpfsCid
    ) external onlyRole(AUDITOR_ROLE) returns (uint256) {
        require(plots[plotId].isRegistered, "TIDE: Plot is not registered");
        require(lowerBoundCarbonTonnes > 0, "TIDE: Lower bound carbon must be > 0");
        require(lowerBoundCarbonTonnes <= totalEstimatedCarbonTonnes, "TIDE: Lower bound cannot exceed total estimate");
        require(confidenceScore <= 100, "TIDE: Confidence score max 100%");
        require(healthScore <= 100, "TIDE: Health score max 100");

        uint256 tokenId = _nextTokenId++;

        creditBatches[tokenId] = CreditBatch({
            tokenId: tokenId,
            plotId: plotId,
            vintageYear: vintageYear,
            totalEstimatedCarbonTonnes: totalEstimatedCarbonTonnes,
            lowerBoundCarbonTonnes: lowerBoundCarbonTonnes,
            confidenceScore: confidenceScore,
            healthScoreAtIssuance: healthScore,
            currentHealthScore: healthScore,
            evidenceIpfsCid: evidenceIpfsCid,
            status: CreditStatus.ACTIVE,
            issuanceTimestamp: block.timestamp,
            lastVerifiedTimestamp: block.timestamp,
            statusReason: "Initial Auditor Verification & Minting"
        });

        plotToTokenIds[plotId].push(tokenId);

        // Mint ERC-1155 tokens equal to lowerBoundCarbonTonnes (1 token = 1 tCO2e)
        _mint(to, tokenId, lowerBoundCarbonTonnes, "");

        emit CreditBatchMinted(
            tokenId,
            plotId,
            vintageYear,
            totalEstimatedCarbonTonnes,
            lowerBoundCarbonTonnes,
            confidenceScore,
            healthScore,
            evidenceIpfsCid,
            to
        );

        return tokenId;
    }

    /**
     * @dev Continuous MRV Oracle function to freeze credit when ecosystem degradation or data mismatch is detected
     */
    function freezeCredit(
        uint256 tokenId,
        string memory reason
    ) external {
        require(
            hasRole(ORACLE_ROLE, msg.sender) || hasRole(AUDITOR_ROLE, msg.sender),
            "TIDE: Caller is neither Oracle nor Auditor"
        );
        require(exists(tokenId), "TIDE: Token ID does not exist");
        
        CreditBatch storage batch = creditBatches[tokenId];
        require(batch.status != CreditStatus.REVOKED, "TIDE: Cannot freeze a revoked credit");

        CreditStatus prevStatus = batch.status;
        batch.status = CreditStatus.FROZEN;
        batch.statusReason = reason;

        emit CreditStatusUpdated(tokenId, prevStatus, CreditStatus.FROZEN, reason, msg.sender);
    }

    /**
     * @dev Auditor reverifies a frozen or under-review credit back to ACTIVE
     */
    function reverifyCredit(
        uint256 tokenId,
        string memory reason,
        uint256 newHealthScore
    ) external onlyRole(AUDITOR_ROLE) {
        require(exists(tokenId), "TIDE: Token ID does not exist");
        require(newHealthScore <= 100, "TIDE: Health score max 100");

        CreditBatch storage batch = creditBatches[tokenId];
        require(batch.status != CreditStatus.REVOKED, "TIDE: Cannot reverify a revoked credit");

        CreditStatus prevStatus = batch.status;
        batch.status = CreditStatus.REVERIFIED;
        batch.currentHealthScore = newHealthScore;
        batch.lastVerifiedTimestamp = block.timestamp;
        batch.statusReason = reason;

        emit CreditStatusUpdated(tokenId, prevStatus, CreditStatus.REVERIFIED, reason, msg.sender);
    }

    /**
     * @dev Auditor permanently revokes a credit due to irrecoverable loss/reversal
     */
    function revokeCredit(
        uint256 tokenId,
        string memory reason
    ) external onlyRole(AUDITOR_ROLE) {
        require(exists(tokenId), "TIDE: Token ID does not exist");

        CreditBatch storage batch = creditBatches[tokenId];
        CreditStatus prevStatus = batch.status;
        batch.status = CreditStatus.REVOKED;
        batch.statusReason = reason;

        emit CreditStatusUpdated(tokenId, prevStatus, CreditStatus.REVOKED, reason, msg.sender);
    }

    /**
     * @dev Update ecosystem dynamic health score via continuous satellite/sensor MRV feed
     */
    function updateHealthScore(
        uint256 tokenId,
        uint256 newHealthScore,
        string memory evidenceIpfsCid
    ) external {
        require(
            hasRole(ORACLE_ROLE, msg.sender) || hasRole(AUDITOR_ROLE, msg.sender),
            "TIDE: Caller must be Oracle or Auditor"
        );
        require(exists(tokenId), "TIDE: Token ID does not exist");
        require(newHealthScore <= 100, "TIDE: Health score max 100");

        CreditBatch storage batch = creditBatches[tokenId];
        uint256 oldScore = batch.currentHealthScore;
        batch.currentHealthScore = newHealthScore;

        if (bytes(evidenceIpfsCid).length > 0) {
            batch.evidenceIpfsCid = evidenceIpfsCid;
        }

        emit HealthScoreUpdated(tokenId, oldScore, newHealthScore, evidenceIpfsCid, msg.sender);

        // Auto-freeze if health drops below 50%
        if (newHealthScore < 50 && batch.status == CreditStatus.ACTIVE) {
            CreditStatus prevStatus = batch.status;
            batch.status = CreditStatus.FROZEN;
            batch.statusReason = "Auto-frozen: Ecosystem Health Score dropped below 50%";
            emit CreditStatusUpdated(tokenId, prevStatus, CreditStatus.FROZEN, batch.statusReason, msg.sender);
        }
    }

    /**
     * @dev Retire (burn) carbon credits to claim environmental offsets
     */
    function retireCredit(
        uint256 tokenId,
        uint256 amountTonnes,
        string memory beneficiaryName,
        string memory offsetReason
    ) external nonReentrant {
        require(exists(tokenId), "TIDE: Token ID does not exist");
        require(amountTonnes > 0, "TIDE: Amount to retire must be > 0");
        require(balanceOf(msg.sender, tokenId) >= amountTonnes, "TIDE: Insufficient credit balance to retire");

        CreditBatch storage batch = creditBatches[tokenId];
        require(
            batch.status == CreditStatus.ACTIVE || batch.status == CreditStatus.REVERIFIED,
            "TIDE: Cannot retire frozen, under review, or revoked credits"
        );

        // Burn tokens
        _burn(msg.sender, tokenId, amountTonnes);

        // Record retirement
        retirementRecords[tokenId].push(RetirementRecord({
            tokenId: tokenId,
            retiree: msg.sender,
            amountTonnes: amountTonnes,
            beneficiaryName: beneficiaryName,
            offsetReason: offsetReason,
            timestamp: block.timestamp
        }));

        emit CarbonRetired(
            tokenId,
            msg.sender,
            amountTonnes,
            beneficiaryName,
            offsetReason,
            block.timestamp
        );
    }

    /**
     * @dev Check if a credit batch is currently eligible for trading/transfer
     */
    function isTransferable(uint256 tokenId) public view returns (bool) {
        if (!exists(tokenId)) return false;
        CreditStatus status = creditBatches[tokenId].status;
        return (status == CreditStatus.ACTIVE || status == CreditStatus.REVERIFIED);
    }

    /**
     * @dev Token URI override returning full metadata string
     */
    function uri(uint256 tokenId) public view override returns (string memory) {
        require(exists(tokenId), "TIDE: URI query for nonexistent token");
        return string(abi.encodePacked(_baseTokenUri, tokenId.toString(), ".json"));
    }

    /**
     * @dev Helper to get all token IDs associated with a plot ID
     */
    function getPlotTokenIds(string memory plotId) external view returns (uint256[] memory) {
        return plotToTokenIds[plotId];
    }

    /**
     * @dev Helper to get retirement history of a credit batch
     */
    function getRetirementHistory(uint256 tokenId) external view returns (RetirementRecord[] memory) {
        return retirementRecords[tokenId];
    }

    /**
     * @dev Set base URI
     */
    function setBaseURI(string memory newBaseUri) external onlyRole(DEFAULT_ADMIN_ROLE) {
        _baseTokenUri = newBaseUri;
    }

    /**
     * @dev OpenZeppelin 5.x ERC-1155 transfer hook blocking transfer of FROZEN, UNDER_REVIEW, or REVOKED credits
     */
    function _update(
        address from,
        address to,
        uint256[] memory ids,
        uint256[] memory values
    ) internal override(ERC1155Supply) {
        // Enforce transfer restrictions for user-to-user transfers (ignore minting from==0 and burning to==0)
        if (from != address(0) && to != address(0)) {
            for (uint256 i = 0; i < ids.length; i++) {
                uint256 tokenId = ids[i];
                CreditStatus status = creditBatches[tokenId].status;
                require(
                    status == CreditStatus.ACTIVE || status == CreditStatus.REVERIFIED,
                    "TIDE: Transfer blocked! Living Credit status is FROZEN, UNDER_REVIEW, or REVOKED"
                );
            }
        }
        super._update(from, to, ids, values);
    }

    /**
     * @dev AccessControl supportsInterface override
     */
    function supportsInterface(bytes4 interfaceId)
        public
        view
        override(ERC1155, AccessControl)
        returns (bool)
    {
        return super.supportsInterface(interfaceId);
    }
}
