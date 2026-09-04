"""
Route optimizer.

Deliberately a transparent lookup table, not a model. Real routing needs
live settlement data (fees, cutoff times, corridor availability) from
actual rail integrations we don't have yet - pretending this is "AI-driven"
would be a claim we can't back up. What we CAN back up: given a
destination and a risk tier, recommend the cheapest/fastest available
rail, and say exactly why.

Figures below are illustrative placeholders for the demo, sourced from
typical PayShap/PAPSS/SWIFT positioning (PayShap = fast South African
domestic rail, PAPSS = pan-African settlement, SWIFT = international
fallback) - NOT live pricing. This is flagged in the API response itself
via the "estimate_basis" field, not hidden.
"""
from dataclasses import dataclass

DOMESTIC_COUNTRY = "South Africa"
PAPSS_CORRIDOR = {"Kenya", "Nigeria", "Ghana", "Zambia", "Botswana"}


@dataclass
class RouteRecommendation:
    rail: str
    estimated_cost_zar: float
    estimated_time_hours: float
    reliability_score: float  # 0-1, illustrative
    reason: str
    estimate_basis: str = "illustrative placeholder - not live rail pricing"


def recommend_route(destination_country: str, risk_tier: str, amount: float) -> RouteRecommendation:
    # high-risk transactions never get the fastest rail - always routed
    # through the path with more manual checkpoints, regardless of cost
    if risk_tier == "high":
        return RouteRecommendation(
            rail="SWIFT (manual review)",
            estimated_cost_zar=round(amount * 0.02, 2),
            estimated_time_hours=48,
            reliability_score=0.99,
            reason="High risk tier - routed for manual compliance review before any transfer, regardless of destination.",
        )

    if destination_country == DOMESTIC_COUNTRY:
        return RouteRecommendation(
            rail="PayShap",
            estimated_cost_zar=round(min(15.0, amount * 0.001), 2),
            estimated_time_hours=0.05,  # ~3 minutes
            reliability_score=0.97,
            reason="Domestic South African payment - PayShap is the fastest, cheapest available rail.",
        )

    if destination_country in PAPSS_CORRIDOR:
        return RouteRecommendation(
            rail="PAPSS",
            estimated_cost_zar=round(amount * 0.008, 2),
            estimated_time_hours=2,
            reliability_score=0.90,
            reason=f"Destination ({destination_country}) is in the PAPSS pan-African settlement corridor - avoids costlier correspondent banking.",
        )

    return RouteRecommendation(
        rail="SWIFT",
        estimated_cost_zar=round(amount * 0.015, 2),
        estimated_time_hours=24,
        reliability_score=0.95,
        reason=f"Destination ({destination_country}) has no direct low-cost rail available yet - SWIFT is the reliable fallback.",
    )
