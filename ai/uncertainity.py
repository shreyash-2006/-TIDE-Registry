"""
uncertainity.py — Conservative Crediting Formula (Blue Carbon MRV)

Implements the one-sided confidence interval lower bound that makes
carbon crediting conservative and defensible.

Standard: VCS VM0007 / Verra Blue Carbon guidance — credits issued at
the lower bound of a 90% one-sided confidence interval.

z = 1.645 corresponds to the 90th percentile of N(0,1),
meaning the true value lies above the lower bound with 90% probability.

Reference:
  Verra VM0007 v1.6 §5 "Conservative estimation approach"
  Wilson et al. 2017, Estuarine, Coastal and Shelf Science
"""


def creditable_carbon(
    estimate: float,
    sigma: float,
    confidence_z: float = 1.645,  # 90% one-sided
) -> float:
    """
    Return the conservative creditable carbon amount (tonne CO2e).

    Parameters
    ----------
    estimate     : float — central CO2e estimate (t)
    sigma        : float — 1-sigma uncertainty (t), from calibration RMSE
    confidence_z : float — z-score for the chosen confidence level
                           (default 1.645 = 90%, per Verra conservative crediting)

    Returns
    -------
    float — lower confidence bound, always >= 0
    """
    lower_bound = estimate - confidence_z * sigma
    return max(0.0, round(lower_bound, 2))


def uncertainty_breakdown(
    estimate: float,
    sigma: float,
    confidence_z: float = 1.645,
) -> dict:
    """
    Return a full uncertainty breakdown dict for the API response.
    """
    lower  = creditable_carbon(estimate, sigma, confidence_z)
    upper  = round(estimate + confidence_z * sigma, 2)
    pct    = round((sigma / estimate * 100), 1) if estimate > 0 else 0.0
    buffer = round(estimate - lower, 2)

    return {
        "central_estimate":    round(estimate, 2),
        "sigma_1":             round(sigma, 2),
        "creditable_carbon":   lower,
        "upper_bound":         upper,
        "uncertainty_pct":     pct,
        "conservatism_buffer": buffer,
        "confidence_level":    round(confidence_z, 3),
        "confidence_pct":      90.0,
        "method": (
            "Verra VM0007 conservative crediting: "
            "lower bound of 90% one-sided confidence interval"
        ),
    }


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import json

    print("=" * 55)
    print("Uncertainty / Conservative Crediting — Self-test")
    print("=" * 55)

    cases = [
        (1000.0, 80.0,  "Normal case"),
        (500.0,  250.0, "High uncertainty (σ > 40%)"),
        (100.0,  100.0, "Extreme uncertainty (σ = estimate)"),
        (50.0,   200.0, "Sigma > estimate → clips to 0"),
    ]

    for estimate, sigma, label in cases:
        result = uncertainty_breakdown(estimate, sigma)
        credit = result["creditable_carbon"]
        print(f"\n{label}")
        print(f"  estimate={estimate:.1f}  sigma={sigma:.1f}"
              f"  → creditable={credit:.1f}  upper={result['upper_bound']:.1f}")
        assert credit <= estimate, "creditable_carbon must be ≤ estimate"
        assert credit >= 0.0,      "creditable_carbon must be ≥ 0"

    print("\n✓ All assertions passed")
    print("\nFull breakdown for normal case:")
    print(json.dumps(uncertainty_breakdown(1000.0, 80.0), indent=2))
