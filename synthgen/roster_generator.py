"""
Agent Roster Generator
Creates field agents, telecallers, and management hierarchy
"""
import random
from typing import List, Dict, Tuple
from dataclasses import dataclass
from faker import Faker

from .geo_generator import GeoData


@dataclass
class TeamData:
    """Team data"""

    team_id: int
    team_name: str
    team_type: str
    parent_team_id: int | None
    zone: str | None


@dataclass
class AgentData:
    """Agent data"""

    agent_id: str
    name: str
    role: str
    team_id: int
    supervisor_id: str | None
    base_pincode: str | None
    base_geo_id: int | None
    langs: List[str]
    capacity_override: int | None
    active: bool


class RosterGenerator:
    """Generates agent roster with geographic distribution"""

    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)
        self.faker_en = Faker("en_IN")
        self.faker_en.seed_instance(seed)

    def generate_roster(
        self,
        agent_counts: Dict[str, int],
        geos: List[GeoData],
        geo_start_id: int = 1,
    ) -> Tuple[List[TeamData], List[AgentData]]:
        """
        Generate complete agent roster with teams and hierarchy
        Returns (teams, agents)
        """
        teams = []
        agents = []

        # Create geo_id mapping
        geo_by_zone = {}
        for i, geo in enumerate(geos):
            geo_id = geo_start_id + i
            if geo.zone not in geo_by_zone:
                geo_by_zone[geo.zone] = []
            geo_by_zone[geo.zone].append((geo, geo_id))

        zones = list(geo_by_zone.keys())

        # Step 1: Create zonal teams (one per zone for RCMs)
        team_id_counter = 1
        zonal_teams = {}

        for zone in zones:
            team = TeamData(
                team_id=team_id_counter,
                team_name=f"{zone} Zone",
                team_type="MIXED",
                parent_team_id=None,
                zone=zone,
            )
            teams.append(team)
            zonal_teams[zone] = team_id_counter
            team_id_counter += 1

        # Step 2: Create RCM agents (one per zone)
        rcm_agents = {}
        agent_id_counter = 1

        for zone in zones[:agent_counts.get("RCM", 5)]:  # Limit to actual RCM count
            agent_id = f"RCM{agent_id_counter:04d}"
            agent = AgentData(
                agent_id=agent_id,
                name=self.faker_en.name(),
                role="RCM",
                team_id=zonal_teams[zone],
                supervisor_id=None,  # Top of hierarchy
                base_pincode=None,
                base_geo_id=None,
                langs=["en", "hi"],
                capacity_override=None,
                active=True,
            )
            agents.append(agent)
            rcm_agents[zone] = agent_id
            agent_id_counter += 1

        # Step 3: Create ACM agents and their teams
        acm_agents = []
        acm_teams_by_zone = {zone: [] for zone in zones}

        for i in range(agent_counts.get("ACM", 15)):
            zone = zones[i % len(zones)]
            team_id = team_id_counter
            team = TeamData(
                team_id=team_id,
                team_name=f"{zone} ACM {len(acm_teams_by_zone[zone])+1}",
                team_type="MIXED",
                parent_team_id=zonal_teams[zone],
                zone=zone,
            )
            teams.append(team)
            acm_teams_by_zone[zone].append(team_id)
            team_id_counter += 1

            agent_id = f"ACM{i+1:04d}"
            supervisor = rcm_agents.get(zone)
            agent = AgentData(
                agent_id=agent_id,
                name=self.faker_en.name(),
                role="ACM",
                team_id=team_id,
                supervisor_id=supervisor,
                base_pincode=None,
                base_geo_id=None,
                langs=["en", "hi"],
                capacity_override=None,
                active=True,
            )
            agents.append(agent)
            acm_agents.append((agent_id, zone, team_id))

        # Step 4: Create TL agents and their teams
        tl_agents_fos = []
        tl_agents_tc = []

        # FOS Team Leads
        n_tl_fos = int(agent_counts.get("TL", 20) * 0.6)  # 60% for field
        for i in range(n_tl_fos):
            zone = zones[i % len(zones)]
            # Pick ACM team from zone, or any available if zone has none
            if acm_teams_by_zone[zone]:
                acm_team = self.rng.choice(acm_teams_by_zone[zone])
            else:
                # Fall back to any available ACM team
                all_acm_teams = [t for teams in acm_teams_by_zone.values() for t in teams]
                acm_team = self.rng.choice(all_acm_teams) if all_acm_teams else zonal_teams[zone]
            team_id = team_id_counter
            team = TeamData(
                team_id=team_id,
                team_name=f"Field Team {i+1}",
                team_type="FOS",
                parent_team_id=acm_team,
                zone=zone,
            )
            teams.append(team)
            team_id_counter += 1

            agent_id = f"TL{i+1:04d}"
            # Find ACM supervisor for this team
            supervisor = next((a[0] for a in acm_agents if a[2] == acm_team), None)
            agent = AgentData(
                agent_id=agent_id,
                name=self.faker_en.name(),
                role="TL",
                team_id=team_id,
                supervisor_id=supervisor,
                base_pincode=None,
                base_geo_id=None,
                langs=["en", "hi"],
                capacity_override=None,
                active=True,
            )
            agents.append(agent)
            tl_agents_fos.append((agent_id, zone, team_id))

        # TC Team Leads
        n_tl_tc = agent_counts.get("TL", 20) - n_tl_fos
        for i in range(n_tl_tc):
            zone = zones[i % len(zones)]
            # Pick ACM team from zone, or any available if zone has none
            if acm_teams_by_zone[zone]:
                acm_team = self.rng.choice(acm_teams_by_zone[zone])
            else:
                # Fall back to any available ACM team
                all_acm_teams = [t for teams in acm_teams_by_zone.values() for t in teams]
                acm_team = self.rng.choice(all_acm_teams) if all_acm_teams else zonal_teams[zone]
            team_id = team_id_counter
            team = TeamData(
                team_id=team_id,
                team_name=f"Telecaller Team {i+1}",
                team_type="TC",
                parent_team_id=acm_team,
                zone=zone,
            )
            teams.append(team)
            team_id_counter += 1

            agent_id = f"TL{n_tl_fos + i+1:04d}"
            supervisor = next((a[0] for a in acm_agents if a[2] == acm_team), None)
            agent = AgentData(
                agent_id=agent_id,
                name=self.faker_en.name(),
                role="TL",
                team_id=team_id,
                supervisor_id=supervisor,
                base_pincode=None,
                base_geo_id=None,
                langs=["en", "hi"],
                capacity_override=None,
                active=True,
            )
            agents.append(agent)
            tl_agents_tc.append((agent_id, zone, team_id))

        # Step 5: Create FOS agents with geographic assignments
        for i in range(agent_counts.get("FOS", 150)):
            zone = zones[i % len(zones)]
            # Assign to a TL team in that zone
            tl_team_options = [t for t in tl_agents_fos if t[1] == zone]
            if not tl_team_options:
                continue
            tl_id, _, team_id = self.rng.choice(tl_team_options)

            # Assign base geography from that zone
            zone_geos = geo_by_zone[zone]
            geo, geo_id = self.rng.choice(zone_geos)

            # Language based on state
            lang = self._get_lang_for_state(geo.state)

            agent_id = f"FOS{i+1:05d}"
            agent = AgentData(
                agent_id=agent_id,
                name=self.faker_en.name(),
                role="FOS",
                team_id=team_id,
                supervisor_id=tl_id,
                base_pincode=geo.pincode,
                base_geo_id=geo_id,
                langs=[lang, "hi", "en"],
                capacity_override=None,
                active=True,
            )
            agents.append(agent)

        # Step 6: Create TC agents (no geographic constraint)
        for i in range(agent_counts.get("TC", 30)):
            zone = zones[i % len(zones)]
            tl_team_options = [t for t in tl_agents_tc if t[1] == zone]
            if not tl_team_options:
                continue
            tl_id, _, team_id = self.rng.choice(tl_team_options)

            agent_id = f"TC{i+1:05d}"
            agent = AgentData(
                agent_id=agent_id,
                name=self.faker_en.name(),
                role="TC",
                team_id=team_id,
                supervisor_id=tl_id,
                base_pincode=None,
                base_geo_id=None,
                langs=["hi", "en"],  # TCs typically speak Hindi/English
                capacity_override=None,
                active=True,
            )
            agents.append(agent)

        return teams, agents

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
