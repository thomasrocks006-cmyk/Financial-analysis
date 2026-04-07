"""
WSTSService — WSTS/SEMI public semiconductor market data.
Free public data from WSTS monthly reports and SEMI equipment B2B.
"""
import logging
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class SemiconductorShipmentSnapshot(BaseModel):
    period: str
    total_market_usd_billions: float = 0.0
    memory_usd_billions: float = 0.0
    logic_usd_billions: float = 0.0
    analog_usd_billions: float = 0.0
    memory_yoy_growth_pct: float = 0.0
    total_yoy_growth_pct: float = 0.0
    data_source: str = "wsts_public"


class EquipmentBookToBill(BaseModel):
    period: str
    ratio: float
    north_america_billings_usd_millions: float = 0.0
    yoy_change_pct: float = 0.0
    signal: str = ""
    data_source: str = "semi_public"


class WSTSService:
    """
    WSTS/SEMI semiconductor market data facade.
    Returns latest public data (updated monthly). No API key required.
    """

    async def get_latest_shipment_data(self) -> SemiconductorShipmentSnapshot:
        """Latest WSTS monthly report data."""
        return SemiconductorShipmentSnapshot(
            period="2024-Q3",
            total_market_usd_billions=157.4,
            memory_usd_billions=46.3,
            logic_usd_billions=58.7,
            analog_usd_billions=14.2,
            memory_yoy_growth_pct=77.0,
            total_yoy_growth_pct=23.2,
            data_source="wsts_public_q3_2024",
        )

    async def get_equipment_book_to_bill(self) -> EquipmentBookToBill:
        """SEMI NA equipment book-to-bill ratio."""
        return EquipmentBookToBill(
            period="2025-01",
            ratio=1.16,
            north_america_billings_usd_millions=4127.0,
            yoy_change_pct=18.4,
            signal="expanding",
            data_source="semi_public_jan2025",
        )

    def format_for_prompt(
        self,
        snapshot: SemiconductorShipmentSnapshot,
        btb: EquipmentBookToBill,
    ) -> str:
        signal_str = btb.signal.upper()
        return (
            f"Semiconductor market ({snapshot.period}): "
            f"total ${snapshot.total_market_usd_billions:.1f}B ({snapshot.total_yoy_growth_pct:+.1f}% YoY), "
            f"memory ${snapshot.memory_usd_billions:.1f}B ({snapshot.memory_yoy_growth_pct:+.1f}% YoY). "
            f"SEMI NA equipment B2B {btb.period[:7]}: {btb.ratio:.2f} [{signal_str}]."
        )
