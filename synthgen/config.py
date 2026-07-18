"""
Synthgen Configuration
Reads from environment and provides validated config to generators
"""
import os
from dataclasses import dataclass
from typing import Dict


@dataclass
class SynthgenConfig:
    """Configuration for synthetic data generation"""

    # Scale
    small_mode: bool
    n_accounts: int
    history_months: int
    seed: int

    # Product mix (percentages)
    product_mix: Dict[str, int]

    # Behavioral archetypes (percentages, must sum to 100)
    archetype_dist: Dict[str, int]

    # Agent counts
    n_fos: int
    n_telecallers: int
    n_tl: int
    n_acm: int
    n_rcm: int

    # Database
    database_url: str

    @classmethod
    def from_env(cls) -> "SynthgenConfig":
        """Load configuration from environment variables"""
        small_mode = os.getenv("SMALL_MODE", "1") == "1"

        # If SMALL_MODE, override to 30k accounts
        if small_mode:
            n_accounts = 30000
        else:
            n_accounts = int(os.getenv("N_ACCOUNTS", "300000"))

        product_mix = {
            "HCV": int(os.getenv("PRODUCT_MIX_HCV", "22")),
            "LCV": int(os.getenv("PRODUCT_MIX_LCV", "28")),
            "TIPPER": int(os.getenv("PRODUCT_MIX_TIPPER", "15")),
            "TRACTOR": int(os.getenv("PRODUCT_MIX_TRACTOR", "18")),
            "CE": int(os.getenv("PRODUCT_MIX_CE", "17")),
        }

        archetype_dist = {
            "PRIME": int(os.getenv("ARCHETYPE_PRIME", "55")),
            "SPORADIC": int(os.getenv("ARCHETYPE_SPORADIC", "25")),
            "STRESSED": int(os.getenv("ARCHETYPE_STRESSED", "12")),
            "CHRONIC": int(os.getenv("ARCHETYPE_CHRONIC", "6")),
            "STRATEGIC": int(os.getenv("ARCHETYPE_STRATEGIC", "2")),
        }

        # Validate archetype distribution sums to 100
        archetype_sum = sum(archetype_dist.values())
        if archetype_sum != 100:
            raise ValueError(
                f"Archetype distribution must sum to 100, got {archetype_sum}"
            )

        # Agent counts (scale down in SMALL_MODE)
        if small_mode:
            # Scale agents proportionally for 30k accounts
            scale_factor = 30000 / 300000
            n_fos = int(int(os.getenv("N_FOS", "1500")) * scale_factor)
            n_telecallers = int(int(os.getenv("N_TELECALLERS", "300")) * scale_factor)
        else:
            n_fos = int(os.getenv("N_FOS", "1500"))
            n_telecallers = int(os.getenv("N_TELECALLERS", "300"))

        # TLs, ACMs, RCMs derived from FOS/TC counts
        n_tl = max(1, n_fos // 15 + n_telecallers // 15)  # 1:15 span
        n_acm = max(1, n_tl // 7)  # 1:7 span
        n_rcm = max(1, n_acm // 3)  # 1:3 span (zones)

        database_url = os.getenv(
            "DATABASE_URL",
            "postgresql://collectos:collectos_dev_password@localhost:5432/collectos"
        )

        return cls(
            small_mode=small_mode,
            n_accounts=n_accounts,
            history_months=int(os.getenv("HISTORY_MONTHS", "24")),
            seed=int(os.getenv("SEED", "42")),
            product_mix=product_mix,
            archetype_dist=archetype_dist,
            n_fos=n_fos,
            n_telecallers=n_telecallers,
            n_tl=n_tl,
            n_acm=n_acm,
            n_rcm=n_rcm,
            database_url=database_url,
        )

    @property
    def n_customers(self) -> int:
        """Number of unique customers (some may have multiple accounts)"""
        # ~90% unique customers, 10% have 2 accounts
        return int(self.n_accounts * 0.95)

    def get_agent_counts_by_role(self) -> Dict[str, int]:
        """Get agent counts by role"""
        return {
            "FOS": self.n_fos,
            "TC": self.n_telecallers,
            "TL": self.n_tl,
            "ACM": self.n_acm,
            "RCM": self.n_rcm,
        }


# Product specifications (realistic CV/CE loan parameters)
PRODUCT_SPECS = {
    "HCV": {
        "description": "Heavy Commercial Vehicle",
        "asset_examples": ["Tata Prima", "Ashok Leyland U-Truck", "Mahindra Blazo"],
        "ticket_range": (2500000, 6000000),  # 25L - 60L
        "tenure_range": (36, 60),
        "roi_range": (9.5, 12.5),
    },
    "LCV": {
        "description": "Light Commercial Vehicle",
        "asset_examples": ["Tata Ace", "Mahindra Bolero Pickup", "Ashok Leyland Dost"],
        "ticket_range": (400000, 1200000),  # 4L - 12L
        "tenure_range": (24, 48),
        "roi_range": (10.5, 13.5),
    },
    "TIPPER": {
        "description": "Tipper Truck",
        "asset_examples": ["Tata LPK 2518", "Ashok Leyland 3118", "Mahindra Blazo X"],
        "ticket_range": (1800000, 4500000),  # 18L - 45L
        "tenure_range": (36, 60),
        "roi_range": (10.0, 13.0),
    },
    "TRACTOR": {
        "description": "Farm Tractor",
        "asset_examples": ["Mahindra 575 DI", "John Deere 5050D", "Swaraj 744 FE"],
        "ticket_range": (600000, 1500000),  # 6L - 15L
        "tenure_range": (36, 60),
        "roi_range": (9.0, 11.5),
    },
    "CE": {
        "description": "Construction Equipment",
        "asset_examples": ["JCB 3DX", "Tata Hitachi EX 200", "L&T 9018"],
        "ticket_range": (1500000, 5000000),  # 15L - 50L
        "tenure_range": (36, 60),
        "roi_range": (11.0, 14.0),
    },
}

# Behavioral archetype parameters (bounce probabilities - the hidden truth)
ARCHETYPE_PARAMS = {
    "PRIME": {
        "base_bounce_prob": 0.04,
        "selfcure_prob": 0.85,
        "ptp_keep_rate": 0.90,
        "contact_responsiveness": 0.80,
    },
    "SPORADIC": {
        "base_bounce_prob": 0.18,
        "selfcure_prob": 0.45,
        "ptp_keep_rate": 0.60,
        "contact_responsiveness": 0.65,
    },
    "STRESSED": {
        "base_bounce_prob": 0.35,
        "selfcure_prob": 0.25,
        "ptp_keep_rate": 0.45,
        "contact_responsiveness": 0.70,
    },
    "CHRONIC": {
        "base_bounce_prob": 0.55,
        "selfcure_prob": 0.10,
        "ptp_keep_rate": 0.25,
        "contact_responsiveness": 0.50,
    },
    "STRATEGIC": {
        "base_bounce_prob": 0.65,
        "selfcure_prob": 0.05,
        "ptp_keep_rate": 0.15,
        "contact_responsiveness": 0.20,  # Deliberately avoids contact
    },
}
