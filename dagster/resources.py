"""
Dagster resources for CollectOS pipeline.
"""

from dagster_dbt import DbtCliResource
import os

# dbt resource pointing to our dbt project
dbt_resource = DbtCliResource(
    project_dir=os.path.join(os.path.dirname(__file__), "..", "dbt"),
    profiles_dir=os.path.join(os.path.dirname(__file__), "..", "dbt"),
)
