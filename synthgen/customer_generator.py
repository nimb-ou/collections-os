"""
Customer Generator
Creates realistic customer profiles with Indian names and contacts
"""
import random
from datetime import date, timedelta
from typing import List, Dict
from dataclasses import dataclass
from faker import Faker

from .geo_generator import GeoData


@dataclass
class CustomerData:
    """Customer profile data"""

    customer_id: str
    name: str
    dob: date
    segment: str
    lang_pref: str
    addr_line1: str
    addr_line2: str
    city: str
    state: str
    pincode: str
    geo_id: int
    primary_phone: str
    alternate_phones: List[str]


class CustomerGenerator:
    """Generates realistic customer profiles"""

    # Customer segments (business type)
    SEGMENTS = ["FTB", "SRTO", "MRTO", "LRTO", "CAPTIVE"]
    SEGMENT_WEIGHTS = [30, 25, 25, 15, 5]  # Weights for distribution

    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)
        # Use both Hindi and English faker for variety
        self.faker_hi = Faker("hi_IN")
        self.faker_en = Faker("en_IN")
        self.faker_hi.seed_instance(seed)
        self.faker_en.seed_instance(seed + 1)

    def generate_customers(
        self, n: int, geos: List[GeoData], geo_start_id: int = 1
    ) -> List[CustomerData]:
        """Generate n customer profiles with geographic distribution"""
        customers = []

        # Create geo_id mapping
        geo_by_idx = {i: geo_start_id + i for i in range(len(geos))}

        for i in range(n):
            customer_id = f"CUST{i+1:08d}"

            # Pick geography
            geo_idx = i % len(geos)  # Distribute customers across geographies
            geo = geos[geo_idx]
            geo_id = geo_by_idx[geo_idx]

            # Generate name (mix of Hindi and English)
            if self.rng.random() < 0.6:
                # Use Hindi names
                name = self.faker_hi.name()
            else:
                # Use English/common Indian names
                name = self.faker_en.name()

            # Generate DOB (age between 25-65 for business owners)
            age_days = self.rng.randint(25 * 365, 65 * 365)
            dob = date.today() - timedelta(days=age_days)

            # Assign segment
            segment = self.rng.choices(self.SEGMENTS, self.SEGMENT_WEIGHTS)[0]

            # Language preference based on state
            lang_pref = self._get_lang_for_state(geo.state)

            # Generate address
            addr_line1 = self.faker_en.street_address()
            # Generate secondary address (shop/floor details)
            if self.rng.random() < 0.3:
                addr_line2 = self.rng.choice([
                    f"Shop {self.rng.randint(1, 50)}",
                    f"Floor {self.rng.randint(1, 10)}",
                    f"Building {self.rng.choice(['A', 'B', 'C', 'D'])}",
                    "Near Market",
                    "Main Road"
                ])
            else:
                addr_line2 = ""

            # Generate phone numbers (Indian format)
            primary_phone = self._generate_phone()
            alternate_phones = []
            if self.rng.random() < 0.4:  # 40% have alternate number
                alternate_phones.append(self._generate_phone())

            customers.append(
                CustomerData(
                    customer_id=customer_id,
                    name=name,
                    dob=dob,
                    segment=segment,
                    lang_pref=lang_pref,
                    addr_line1=addr_line1,
                    addr_line2=addr_line2,
                    city=geo.city,
                    state=geo.state,
                    pincode=geo.pincode,
                    geo_id=geo_id,
                    primary_phone=primary_phone,
                    alternate_phones=alternate_phones,
                )
            )

        return customers

    def _generate_phone(self) -> str:
        """Generate Indian mobile number (10 digits, starts with 6-9)"""
        first_digit = self.rng.choice(["6", "7", "8", "9"])
        remaining = "".join([str(self.rng.randint(0, 9)) for _ in range(9)])
        return first_digit + remaining

    def _get_lang_for_state(self, state: str) -> str:
        """Get language code for state"""
        lang_map = {
            "Maharashtra": "mr",
            "Uttar Pradesh": "hi",
            "Gujarat": "gu",
            "Rajasthan": "hi",
            "Madhya Pradesh": "hi",
            "Tamil Nadu": "ta",
            "Karnataka": "kn",
            "Punjab": "pa",
            "Haryana": "hi",
            "Andhra Pradesh": "te",
            "Telangana": "te",
            "West Bengal": "bn",
            "Bihar": "hi",
            "Kerala": "ml",
        }
        return lang_map.get(state, "en")
