"""
Metabase Dashboard Bootstrap Script
Auto-provisions dashboards and SQL queries via Metabase API.
"""

import requests
import yaml
import os
import re
from pathlib import Path
from typing import Dict, List, Optional


class MetabaseBootstrap:
    """Bootstrap Metabase with CollectOS dashboards."""

    def __init__(
        self,
        metabase_url: str = "http://localhost:3000",
        username: str = "admin@collectos.local",
        password: str = "changeme"
    ):
        """Initialize Metabase API client."""
        self.base_url = metabase_url
        self.username = username
        self.password = password
        self.session_token = None
        self.database_id = None

    def authenticate(self) -> bool:
        """Authenticate with Metabase and get session token."""
        try:
            response = requests.post(
                f"{self.base_url}/api/session",
                json={"username": self.username, "password": self.password}
            )
            response.raise_for_status()
            self.session_token = response.json()["id"]
            print(f"✓ Authenticated with Metabase as {self.username}")
            return True
        except Exception as e:
            print(f"✗ Authentication failed: {e}")
            return False

    def get_headers(self) -> Dict[str, str]:
        """Get authorization headers for API requests."""
        return {"X-Metabase-Session": self.session_token}

    def find_database(self, db_name: str = "collectos") -> Optional[int]:
        """Find the CollectOS database ID."""
        try:
            response = requests.get(
                f"{self.base_url}/api/database",
                headers=self.get_headers()
            )
            response.raise_for_status()
            databases = response.json()["data"]

            for db in databases:
                if db["name"].lower() == db_name.lower():
                    self.database_id = db["id"]
                    print(f"✓ Found database '{db_name}' (ID: {self.database_id})")
                    return self.database_id

            print(f"⚠️  Database '{db_name}' not found")
            return None
        except Exception as e:
            print(f"✗ Error finding database: {e}")
            return None

    def create_dashboard(self, name: str, description: str) -> Optional[int]:
        """Create a new dashboard."""
        try:
            response = requests.post(
                f"{self.base_url}/api/dashboard",
                headers=self.get_headers(),
                json={
                    "name": name,
                    "description": description,
                }
            )
            response.raise_for_status()
            dashboard_id = response.json()["id"]
            print(f"✓ Created dashboard '{name}' (ID: {dashboard_id})")
            return dashboard_id
        except Exception as e:
            print(f"✗ Error creating dashboard '{name}': {e}")
            return None

    def extract_query_from_file(self, file_path: Path, section: str) -> Optional[str]:
        """
        Extract a specific SQL query from a file by section comment.

        Args:
            file_path: Path to SQL file
            section: Section identifier (e.g., "Query 1")

        Returns:
            SQL query string or None
        """
        try:
            with open(file_path, 'r') as f:
                content = f.read()

            # Find the section
            pattern = rf"-- {re.escape(section)}:.*?\n(.*?)(?=\n-- Query|\Z)"
            match = re.search(pattern, content, re.DOTALL)

            if match:
                query = match.group(1).strip()
                # Remove comments
                query = re.sub(r'--.*$', '', query, flags=re.MULTILINE)
                # Clean up whitespace
                query = '\n'.join(line for line in query.split('\n') if line.strip())
                return query
            else:
                print(f"⚠️  Section '{section}' not found in {file_path.name}")
                return None
        except Exception as e:
            print(f"✗ Error reading {file_path}: {e}")
            return None

    def create_question(
        self,
        name: str,
        sql: str,
        database_id: int,
        viz_type: str = "table"
    ) -> Optional[int]:
        """
        Create a SQL question (card).

        Args:
            name: Question name
            sql: SQL query
            database_id: Database ID
            viz_type: Visualization type (table, line, bar, scalar, pie)

        Returns:
            Question ID or None
        """
        try:
            # Map viz types to Metabase display types
            display_map = {
                "table": "table",
                "line": "line",
                "bar": "bar",
                "scalar": "scalar",
                "pie": "pie",
            }

            response = requests.post(
                f"{self.base_url}/api/card",
                headers=self.get_headers(),
                json={
                    "name": name,
                    "dataset_query": {
                        "type": "native",
                        "native": {
                            "query": sql,
                        },
                        "database": database_id,
                    },
                    "display": display_map.get(viz_type, "table"),
                    "visualization_settings": {},
                }
            )
            response.raise_for_status()
            question_id = response.json()["id"]
            print(f"  ✓ Created question '{name}' (ID: {question_id})")
            return question_id
        except Exception as e:
            print(f"  ✗ Error creating question '{name}': {e}")
            return None

    def add_card_to_dashboard(
        self,
        dashboard_id: int,
        card_id: int,
        row: int,
        col: int,
        width: int,
        height: int
    ) -> bool:
        """Add a card to a dashboard with positioning."""
        try:
            response = requests.post(
                f"{self.base_url}/api/dashboard/{dashboard_id}/cards",
                headers=self.get_headers(),
                json={
                    "cardId": card_id,
                    "row": row,
                    "col": col,
                    "sizeX": width,
                    "sizeY": height,
                }
            )
            response.raise_for_status()
            return True
        except Exception as e:
            print(f"  ✗ Error adding card to dashboard: {e}")
            return False

    def bootstrap_dashboards(self, config_path: Path, queries_dir: Path) -> bool:
        """
        Bootstrap all dashboards from configuration.

        Args:
            config_path: Path to dashboards config.yaml
            queries_dir: Path to queries directory

        Returns:
            Success status
        """
        # Load configuration
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)

        total_dashboards = len(config["dashboards"])
        print(f"\nBootstrapping {total_dashboards} dashboards...\n")

        for dashboard_config in config["dashboards"]:
            dashboard_name = dashboard_config["name"]
            dashboard_desc = dashboard_config["description"]

            print(f"\n{'='*60}")
            print(f"Dashboard: {dashboard_name}")
            print(f"{'='*60}")

            # Create dashboard
            dashboard_id = self.create_dashboard(dashboard_name, dashboard_desc)
            if not dashboard_id:
                continue

            # Add queries as cards
            row = 0
            col = 0

            for query_config in dashboard_config["queries"]:
                query_name = query_config["name"]
                query_file = queries_dir / query_config["file"]
                query_section = query_config["section"]
                viz_type = query_config.get("viz_type", "table")
                size = query_config.get("size", {"width": 6, "height": 4})

                # Extract SQL
                sql = self.extract_query_from_file(query_file, query_section)
                if not sql:
                    continue

                # Create question
                question_id = self.create_question(
                    query_name, sql, self.database_id, viz_type
                )
                if not question_id:
                    continue

                # Add to dashboard with layout
                self.add_card_to_dashboard(
                    dashboard_id,
                    question_id,
                    row=row,
                    col=col,
                    width=size["width"],
                    height=size["height"]
                )

                # Update position for next card (simple grid layout)
                col += size["width"]
                if col >= 12:  # Metabase uses 12-column grid
                    col = 0
                    row += size["height"]

            print(f"\n✓ Dashboard '{dashboard_name}' complete\n")

        return True


def main():
    """Main bootstrap script."""
    print("="*60)
    print("CollectOS Metabase Dashboard Bootstrap")
    print("="*60)

    # Configuration
    metabase_url = os.getenv("METABASE_URL", "http://localhost:3000")
    metabase_user = os.getenv("METABASE_USER", "admin@collectos.local")
    metabase_pass = os.getenv("METABASE_PASSWORD", "changeme")

    # Paths
    bi_dir = Path(__file__).parent
    config_path = bi_dir / "dashboards" / "config.yaml"
    queries_dir = bi_dir / "queries"

    # Initialize
    bootstrap = MetabaseBootstrap(metabase_url, metabase_user, metabase_pass)

    # Authenticate
    if not bootstrap.authenticate():
        print("\n✗ Failed to authenticate with Metabase")
        print("  Ensure Metabase is running and credentials are correct")
        return

    # Find database
    if not bootstrap.find_database("collectos"):
        print("\n✗ CollectOS database not found in Metabase")
        print("  You may need to manually add the PostgreSQL connection first")
        return

    # Bootstrap dashboards
    success = bootstrap.bootstrap_dashboards(config_path, queries_dir)

    if success:
        print("\n" + "="*60)
        print("✓ Dashboard bootstrap complete!")
        print("="*60)
        print(f"\nView dashboards at: {metabase_url}/collection/root")
        print("\nDashboards created:")
        print("  1. Portfolio Command")
        print("  2. Calling Ops")
        print("  3. Field Ops")
    else:
        print("\n✗ Dashboard bootstrap failed")


if __name__ == "__main__":
    main()
