"""Economics models for space resource delivery cost and infrastructure value.

Compares in-situ resource delivery cost against Earth-launch cost,
models infrastructure amortization, and calculates break-even
analysis for each technology.
"""

from dataclasses import dataclass


@dataclass
class DeliveryCostProfile:
    resource_type: str
    earth_launch_cost_per_kg: float = 100000.0
    lunar_delivery_cost_per_kg: float = 1_000_000.0
    mars_delivery_cost_per_kg: float = 5_000_000.0
    isru_cost_per_kg: float = 50000.0

    def savings_vs_earth_launch(self, mass_kg: float, destination: str = "lunar") -> float:
        earth_cost = mass_kg * self.earth_launch_cost_per_kg
        if destination == "lunar":
            in_situ_cost = mass_kg * self.isru_cost_per_kg
        elif destination == "mars":
            in_situ_cost = mass_kg * self.isru_cost_per_kg * 1.5
        else:
            in_situ_cost = mass_kg * self.isru_cost_per_kg * 2.0
        return earth_cost - in_situ_cost

    def delivery_cost(self, mass_kg: float, destination: str = "lunar") -> float:
        if destination == "lunar":
            return mass_kg * self.lunar_delivery_cost_per_kg
        elif destination == "mars":
            return mass_kg * self.mars_delivery_cost_per_kg
        return mass_kg * self.earth_launch_cost_per_kg

    def to_dict(self) -> dict:
        return {
            "resource_type": self.resource_type,
            "earth_launch_kg": self.earth_launch_cost_per_kg,
            "lunar_delivery_kg": self.lunar_delivery_cost_per_kg,
            "mars_delivery_kg": self.mars_delivery_cost_per_kg,
            "isru_kg": self.isru_cost_per_kg,
        }


@dataclass
class InfrastructureAsset:
    name: str
    mass_kg: float
    development_cost: float
    unit_cost: float
    production_capacity_kg_per_day: float
    expected_lifespan_days: float = 365.0
    technology_id: str = ""

    @property
    def capital_cost(self) -> float:
        return self.development_cost + self.unit_cost

    @property
    def cost_per_kg_produced(self) -> float:
        if self.production_capacity_kg_per_day <= 0:
            return float("inf")
        total_production = self.production_capacity_kg_per_day * self.expected_lifespan_days
        return self.capital_cost / total_production

    @property
    def break_even_mass_kg(self) -> float:
        if self.cost_per_kg_produced <= 0:
            return 0.0
        profile = DeliveryCostProfile(resource_type="generic")
        return self.capital_cost / profile.earth_launch_cost_per_kg

    def amortized_cost_per_kg(self, destination: str = "lunar") -> float:
        profile = DeliveryCostProfile(resource_type="generic")
        if destination == "lunar":
            base = profile.lunar_delivery_cost_per_kg
        elif destination == "mars":
            base = profile.mars_delivery_cost_per_kg
        else:
            base = profile.earth_launch_cost_per_kg
        return base - self.cost_per_kg_produced

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "capital_cost": self.capital_cost,
            "cost_per_kg": round(self.cost_per_kg_produced, 2),
            "break_even_kg": round(self.break_even_mass_kg, 1),
            "lifespan_days": self.expected_lifespan_days,
            "technology_id": self.technology_id,
        }


class EconomicsModel:
    def __init__(self):
        self._delivery_profiles: dict[str, DeliveryCostProfile] = {
            "water": DeliveryCostProfile(resource_type="water"),
            "oxygen": DeliveryCostProfile(resource_type="oxygen", earth_launch_cost_per_kg=80000),
            "metals": DeliveryCostProfile(resource_type="metals", earth_launch_cost_per_kg=120000),
            "propellant": DeliveryCostProfile(resource_type="propellant", earth_launch_cost_per_kg=90000),
            "construction_material": DeliveryCostProfile(
                resource_type="construction_material", earth_launch_cost_per_kg=60000
            ),
        }
        self._assets: list[InfrastructureAsset] = []

    def add_asset(self, asset: InfrastructureAsset) -> None:
        self._assets.append(asset)

    def get_profile(self, resource_type: str) -> DeliveryCostProfile | None:
        return self._delivery_profiles.get(resource_type)

    def cost_analysis(
        self, resource_type: str, mass_kg: float, destination: str = "lunar"
    ) -> dict:
        profile = self._delivery_profiles.get(resource_type)
        if profile is None:
            return {"error": f"No cost profile for {resource_type}"}
        earth_cost = mass_kg * profile.earth_launch_cost_per_kg
        in_situ_cost = mass_kg * profile.isru_cost_per_kg
        savings = earth_cost - in_situ_cost
        return {
            "resource_type": resource_type,
            "mass_kg": mass_kg,
            "destination": destination,
            "earth_launch_cost": earth_cost,
            "in_situ_cost": in_situ_cost,
            "savings": savings,
            "savings_percent": (savings / earth_cost * 100) if earth_cost > 0 else 0.0,
        }

    def portfolio_analysis(self, destination: str = "lunar") -> dict:
        total_capital = sum(a.capital_cost for a in self._assets)
        total_daily_production = sum(a.production_capacity_kg_per_day for a in self._assets)
        return {
            "destination": destination,
            "total_capital_cost": total_capital,
            "daily_production_kg": round(total_daily_production, 4),
            "asset_count": len(self._assets),
            "assets": [a.to_dict() for a in self._assets],
        }

    def break_even_analysis(self, resource_type: str, destination: str = "lunar") -> dict:
        assets = [a for a in self._assets if a.technology_id.startswith(resource_type)]
        if not assets:
            return {"resource_type": resource_type, "assets": []}
        results = []
        for asset in assets:
            profile = self._delivery_profiles.get(resource_type, DeliveryCostProfile(resource_type=resource_type))
            savings_per_kg = (
                profile.earth_launch_cost_per_kg - profile.isru_cost_per_kg
            )
            if savings_per_kg > 0:
                break_even_kg = asset.capital_cost / savings_per_kg
            else:
                break_even_kg = float("inf")
            break_even_days = (
                break_even_kg / asset.production_capacity_kg_per_day
                if asset.production_capacity_kg_per_day > 0
                else float("inf")
            )
            results.append({
                "asset": asset.name,
                "capital_cost": asset.capital_cost,
                "savings_per_kg": round(savings_per_kg, 2),
                "break_even_kg": round(break_even_kg, 1),
                "break_even_days": round(break_even_days, 1),
            })
        return {"resource_type": resource_type, "assets": results}
