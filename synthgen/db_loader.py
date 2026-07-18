"""
Database Loader
Loads generated synthetic data into PostgreSQL
"""
import psycopg2
from psycopg2.extras import execute_batch
from typing import List
import logging

from .geo_generator import GeoData
from .customer_generator import CustomerData
from .portfolio_generator import AccountData, EMIScheduleData
from .roster_generator import TeamData, AgentData

logger = logging.getLogger(__name__)


class DatabaseLoader:
    """Loads synthetic data into PostgreSQL database"""

    def __init__(self, database_url: str):
        self.database_url = database_url
        self.conn = None

    def connect(self):
        """Connect to database"""
        self.conn = psycopg2.connect(self.database_url)
        self.conn.autocommit = False

    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()

    def load_geos(self, geos: List[GeoData]) -> dict:
        """Load geography data and return pincode->geo_id mapping"""
        logger.info(f"Loading {len(geos)} geography records...")

        sql = """
            INSERT INTO dim_geo (pincode, city, district, state, zone, lat, lon)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (pincode) DO UPDATE SET
                city = EXCLUDED.city,
                district = EXCLUDED.district,
                state = EXCLUDED.state,
                zone = EXCLUDED.zone,
                lat = EXCLUDED.lat,
                lon = EXCLUDED.lon
            RETURNING pincode, geo_id
        """

        data = [
            (g.pincode, g.city, g.district, g.state, g.zone, g.lat, g.lon)
            for g in geos
        ]

        geo_id_map = {}
        with self.conn.cursor() as cur:
            for row in data:
                cur.execute(sql, row)
                result = cur.fetchone()
                if result:
                    pincode, geo_id = result
                    geo_id_map[pincode] = geo_id
            self.conn.commit()

        logger.info(f"✓ Loaded {len(geos)} geography records")
        return geo_id_map

    def load_customers(self, customers: List[CustomerData], geo_id_map: dict):
        """Load customer data using correct geo_ids from database"""
        logger.info(f"Loading {len(customers)} customer records...")

        # Load customers - look up geo_id by pincode
        sql_customer = """
            INSERT INTO dim_customer (
                customer_id, name, dob, segment, lang_pref,
                addr_line1, addr_line2, city, state, pincode, geo_id
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (customer_id) DO NOTHING
        """

        customer_data = [
            (
                c.customer_id, c.name, c.dob, c.segment, c.lang_pref,
                c.addr_line1, c.addr_line2, c.city, c.state, c.pincode,
                geo_id_map.get(c.pincode, 1)  # Look up by pincode, default to 1
            )
            for c in customers
        ]

        with self.conn.cursor() as cur:
            execute_batch(cur, sql_customer, customer_data, page_size=1000)

        # Load contacts
        sql_contact = """
            INSERT INTO dim_customer_contacts (
                customer_id, phone, phone_type, is_primary, dnc_flag
            )
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (customer_id, phone) DO NOTHING
        """

        contact_data = []
        for c in customers:
            # Primary phone
            contact_data.append((c.customer_id, c.primary_phone, "mobile", True, False))
            # Alternate phones
            for phone in c.alternate_phones:
                contact_data.append((c.customer_id, phone, "mobile", False, False))

        with self.conn.cursor() as cur:
            execute_batch(cur, sql_contact, contact_data, page_size=1000)

        self.conn.commit()
        logger.info(f"✓ Loaded {len(customers)} customers with {len(contact_data)} contacts")

    def load_accounts(
        self,
        accounts: List[AccountData],
        emi_schedules: List[EMIScheduleData],
        geo_id_map: dict
    ):
        """Load account and EMI schedule data using correct geo_ids from database"""
        logger.info(f"Loading {len(accounts)} accounts...")

        # Load accounts (store archetype in a temp table for later use in history gen)
        sql_account = """
            INSERT INTO dim_account (
                account_id, customer_id, product_type, asset_desc,
                disbursal_date, disbursal_amt, tenure_m, roi, emi_amt,
                cycle_day, branch, state, city, pincode, geo_id, status
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'ACTIVE')
            ON CONFLICT (account_id) DO NOTHING
        """

        account_data = [
            (
                a.account_id, a.customer_id, a.product_type, a.asset_desc,
                a.disbursal_date, a.disbursal_amt, a.tenure_m, a.roi, a.emi_amt,
                a.cycle_day, a.branch, a.state, a.city, a.pincode,
                geo_id_map.get(a.pincode, 1)  # Look up by pincode, default to 1
            )
            for a in accounts
        ]

        with self.conn.cursor() as cur:
            execute_batch(cur, sql_account, account_data, page_size=1000)
            self.conn.commit()

        logger.info(f"✓ Loaded {len(accounts)} accounts")

        # Store archetypes in permanent table for history generation (Session 3)
        logger.info("Storing archetypes for history generation...")

        archetype_data = [(a.account_id, a.archetype) for a in accounts]
        sql_archetype = """
            INSERT INTO account_archetypes (account_id, archetype)
            VALUES (%s, %s)
            ON CONFLICT (account_id) DO UPDATE SET archetype = EXCLUDED.archetype
        """

        with self.conn.cursor() as cur:
            execute_batch(cur, sql_archetype, archetype_data, page_size=1000)
            self.conn.commit()

        logger.info(f"✓ Stored {len(accounts)} archetypes")

        # Load EMI schedules
        logger.info(f"Loading {len(emi_schedules)} EMI schedule entries...")

        sql_schedule = """
            INSERT INTO dim_emi_schedule (
                account_id, inst_no, due_date, emi_amt, principal, interest
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (account_id, inst_no) DO NOTHING
        """

        schedule_data = [
            (s.account_id, s.inst_no, s.due_date, s.emi_amt, s.principal, s.interest)
            for s in emi_schedules
        ]

        with self.conn.cursor() as cur:
            execute_batch(cur, sql_schedule, schedule_data, page_size=5000)
            self.conn.commit()

        logger.info(f"✓ Loaded {len(emi_schedules)} EMI schedule entries")

    def load_teams(self, teams: List[TeamData]):
        """Load team data"""
        logger.info(f"Loading {len(teams)} teams...")

        sql = """
            INSERT INTO dim_team (team_id, team_name, team_type, parent_team_id, zone)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (team_name) DO NOTHING
        """

        data = [
            (t.team_id, t.team_name, t.team_type, t.parent_team_id, t.zone)
            for t in teams
        ]

        with self.conn.cursor() as cur:
            execute_batch(cur, sql, data, page_size=1000)
            self.conn.commit()

        logger.info(f"✓ Loaded {len(teams)} teams")

    def load_agents(self, agents: List[AgentData], geo_id_map: dict):
        """Load agent data using correct geo_ids from database"""
        logger.info(f"Loading {len(agents)} agents...")

        sql = """
            INSERT INTO dim_agent (
                agent_id, name, role, team_id, supervisor_id,
                base_pincode, base_geo_id, langs, capacity_override, active
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """

        data = [
            (
                a.agent_id, a.name, a.role, a.team_id, a.supervisor_id,
                a.base_pincode,
                geo_id_map.get(a.base_pincode, None) if a.base_pincode else None,  # Look up by pincode
                a.langs, a.capacity_override, a.active
            )
            for a in agents
        ]

        with self.conn.cursor() as cur:
            execute_batch(cur, sql, data, page_size=1000)
            self.conn.commit()

        logger.info(f"✓ Loaded {len(agents)} agents")

    def get_stats(self) -> dict:
        """Get database statistics"""
        stats = {}

        with self.conn.cursor() as cur:
            # Count records
            tables = [
                "dim_geo",
                "dim_customer",
                "dim_customer_contacts",
                "dim_account",
                "dim_emi_schedule",
                "dim_team",
                "dim_agent",
            ]

            for table in tables:
                cur.execute(f"SELECT COUNT(*) FROM {table}")
                count = cur.fetchone()[0]
                stats[table] = count

        return stats
