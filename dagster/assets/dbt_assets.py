"""
dbt model assets for CollectOS.
These assets represent the dbt staging and mart models.
"""

from dagster import asset, AssetExecutionContext, Output
from dagster_dbt import DbtCliResource, dbt_assets as dagster_dbt_assets
import os

DBT_PROJECT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "dbt")
DBT_MANIFEST_PATH = os.path.join(DBT_PROJECT_DIR, "target", "manifest.json")


@asset(
    group_name="dbt_staging",
    compute_kind="dbt",
    description="dbt staging models (presentations, payments, calls, visits, accounts)",
)
def dbt_staging_models(context: AssetExecutionContext, dbt: DbtCliResource):
    """
    Runs all dbt staging models.
    These are lightweight views that add derived fields to raw tables.
    """
    dbt_run_result = dbt.cli(["run", "--select", "staging.*"], context=context)
    return Output(value=dbt_run_result)


@asset(
    group_name="dbt_marts",
    compute_kind="dbt",
    description="dbt mart models (portfolio monthly, collection performance, agent scorecards)",
    deps=[dbt_staging_models],
)
def dbt_marts_models(context: AssetExecutionContext, dbt: DbtCliResource):
    """
    Runs all dbt mart models.
    These are materialized tables with business-level aggregates.
    Depends on staging models being built first.
    """
    dbt_run_result = dbt.cli(["run", "--select", "marts.*"], context=context)
    return Output(value=dbt_run_result)


# Export lists for easier imports
dbt_staging_assets = [dbt_staging_models]
dbt_marts_assets = [dbt_marts_models]
