"""
CollectOS Dagster Assets
"""

from .dbt_assets import dbt_staging_assets, dbt_marts_assets

# Combine all dbt assets
dbt_assets = [*dbt_staging_assets, *dbt_marts_assets]

# All assets for the Definitions
all_assets = dbt_assets
