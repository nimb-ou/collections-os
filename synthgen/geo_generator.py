"""
Geography Generator
Creates realistic Indian geography distribution for portfolio
"""
import random
from typing import List, Dict, Tuple
from dataclasses import dataclass


@dataclass
class GeoData:
    """Geography data point"""

    pincode: str
    city: str
    district: str
    state: str
    zone: str
    lat: float
    lon: float


class GeoGenerator:
    """Generates realistic Indian geography for loan portfolio"""

    # Major states with CV/CE loan concentrations (weighted distribution)
    STATE_WEIGHTS = {
        "Maharashtra": 15,
        "Uttar Pradesh": 14,
        "Gujarat": 12,
        "Rajasthan": 10,
        "Madhya Pradesh": 9,
        "Tamil Nadu": 8,
        "Karnataka": 7,
        "Punjab": 6,
        "Haryana": 5,
        "Andhra Pradesh": 4,
        "Telangana": 4,
        "West Bengal": 3,
        "Bihar": 2,
        "Kerala": 1,
    }

    # Zone mapping
    ZONE_MAP = {
        "Maharashtra": "West",
        "Uttar Pradesh": "North",
        "Gujarat": "West",
        "Rajasthan": "North",
        "Madhya Pradesh": "Central",
        "Tamil Nadu": "South",
        "Karnataka": "South",
        "Punjab": "North",
        "Haryana": "North",
        "Andhra Pradesh": "South",
        "Telangana": "South",
        "West Bengal": "East",
        "Bihar": "East",
        "Kerala": "South",
    }

    # Sample cities per state (major CV/CE hubs)
    CITIES_BY_STATE = {
        "Maharashtra": [
            ("Mumbai", "400001", 19.0760, 72.8777),
            ("Pune", "411001", 18.5204, 73.8567),
            ("Nagpur", "440001", 21.1458, 79.0882),
            ("Nashik", "422001", 19.9975, 73.7898),
            ("Aurangabad", "431001", 19.8762, 75.3433),
        ],
        "Uttar Pradesh": [
            ("Lucknow", "226001", 26.8467, 80.9462),
            ("Kanpur", "208001", 26.4499, 80.3319),
            ("Agra", "282001", 27.1767, 78.0081),
            ("Varanasi", "221001", 25.3176, 82.9739),
            ("Meerut", "250001", 28.9845, 77.7064),
        ],
        "Gujarat": [
            ("Ahmedabad", "380001", 23.0225, 72.5714),
            ("Surat", "395001", 21.1702, 72.8311),
            ("Vadodara", "390001", 22.3072, 73.1812),
            ("Rajkot", "360001", 22.3039, 70.8022),
            ("Bhavnagar", "364001", 21.7645, 72.1519),
        ],
        "Rajasthan": [
            ("Jaipur", "302001", 26.9124, 75.7873),
            ("Jodhpur", "342001", 26.2389, 73.0243),
            ("Kota", "324001", 25.2138, 75.8648),
            ("Udaipur", "313001", 24.5854, 73.7125),
            ("Ajmer", "305001", 26.4499, 74.6399),
        ],
        "Madhya Pradesh": [
            ("Bhopal", "462001", 23.2599, 77.4126),
            ("Indore", "452001", 22.7196, 75.8577),
            ("Jabalpur", "482001", 23.1815, 79.9864),
            ("Gwalior", "474001", 26.2183, 78.1828),
            ("Ujjain", "456001", 23.1765, 75.7885),
        ],
        "Tamil Nadu": [
            ("Chennai", "600001", 13.0827, 80.2707),
            ("Coimbatore", "641001", 11.0168, 76.9558),
            ("Madurai", "625001", 9.9252, 78.1198),
            ("Tiruchirappalli", "620001", 10.7905, 78.7047),
            ("Salem", "636001", 11.6643, 78.1460),
        ],
        "Karnataka": [
            ("Bangalore", "560001", 12.9716, 77.5946),
            ("Mysore", "570001", 12.2958, 76.6394),
            ("Hubli", "580001", 15.3647, 75.1240),
            ("Mangalore", "575001", 12.9141, 74.8560),
            ("Belgaum", "590001", 15.8497, 74.4977),
        ],
        "Punjab": [
            ("Ludhiana", "141001", 30.9010, 75.8573),
            ("Amritsar", "143001", 31.6340, 74.8723),
            ("Jalandhar", "144001", 31.3260, 75.5762),
            ("Patiala", "147001", 30.3398, 76.3869),
            ("Bathinda", "151001", 30.2110, 74.9455),
        ],
        "Haryana": [
            ("Gurgaon", "122001", 28.4595, 77.0266),
            ("Faridabad", "121001", 28.4089, 77.3178),
            ("Panipat", "132001", 29.3909, 76.9635),
            ("Ambala", "134001", 30.3782, 76.7767),
            ("Hisar", "125001", 29.1492, 75.7217),
        ],
        "Andhra Pradesh": [
            ("Visakhapatnam", "530001", 17.6869, 83.2185),
            ("Vijayawada", "520001", 16.5062, 80.6480),
            ("Guntur", "522001", 16.3067, 80.4365),
            ("Nellore", "524001", 14.4426, 79.9865),
            ("Tirupati", "517001", 13.6288, 79.4192),
        ],
        "Telangana": [
            ("Hyderabad", "500001", 17.3850, 78.4867),
            ("Warangal", "506001", 17.9689, 79.5941),
            ("Nizamabad", "503001", 18.6725, 78.0941),
            ("Khammam", "507001", 17.2473, 80.1514),
            ("Karimnagar", "505001", 18.4386, 79.1288),
        ],
        "West Bengal": [
            ("Kolkata", "700001", 22.5726, 88.3639),
            ("Howrah", "711001", 22.5958, 88.2636),
            ("Durgapur", "713201", 23.5204, 87.3119),
            ("Asansol", "713301", 23.6739, 86.9524),
            ("Siliguri", "734001", 26.7271, 88.3953),
        ],
        "Bihar": [
            ("Patna", "800001", 25.5941, 85.1376),
            ("Gaya", "823001", 24.7955, 85.0002),
            ("Bhagalpur", "812001", 25.2425, 86.9842),
            ("Muzaffarpur", "842001", 26.1225, 85.3906),
            ("Darbhanga", "846001", 26.1542, 85.8918),
        ],
        "Kerala": [
            ("Kochi", "682001", 9.9312, 76.2673),
            ("Thiruvananthapuram", "695001", 8.5241, 76.9366),
            ("Kozhikode", "673001", 11.2588, 75.7804),
            ("Thrissur", "680001", 10.5276, 76.2144),
            ("Kannur", "670001", 11.8745, 75.3704),
        ],
    }

    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)

        # Build weighted state list for sampling
        self.state_list = []
        for state, weight in self.STATE_WEIGHTS.items():
            self.state_list.extend([state] * weight)

    def generate_geo_distribution(self, n: int) -> List[GeoData]:
        """Generate n geography data points with realistic distribution"""
        geos = []

        for _ in range(n):
            # Pick weighted state
            state = self.rng.choice(self.state_list)
            zone = self.ZONE_MAP[state]

            # Pick random city in that state
            cities = self.CITIES_BY_STATE[state]
            city_name, base_pincode, base_lat, base_lon = self.rng.choice(cities)

            # Generate pincode variation (nearby area)
            pincode_num = int(base_pincode)
            pincode_variation = self.rng.randint(0, 99)
            pincode = f"{pincode_num + pincode_variation:06d}"

            # Add small lat/lon jitter for variation
            lat = base_lat + self.rng.uniform(-0.1, 0.1)
            lon = base_lon + self.rng.uniform(-0.1, 0.1)

            # District usually same as city for major cities
            district = city_name

            geos.append(
                GeoData(
                    pincode=pincode,
                    city=city_name,
                    district=district,
                    state=state,
                    zone=zone,
                    lat=round(lat, 6),
                    lon=round(lon, 6),
                )
            )

        return geos

    def get_state_language(self, state: str) -> str:
        """Get primary language for a state"""
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
