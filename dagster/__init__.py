"""
CollectOS Dagster Data Pipeline
Daily pipeline engine for dbt marts, scoring, treatment, and allocation.
"""

from dagster import Definitions
from .assets import dbt_assets, all_assets
from .resources import dbt_resource

defs = Definitions(
    assets=all_assets,
    resources={
        "dbt": dbt_resource,
    },
)
