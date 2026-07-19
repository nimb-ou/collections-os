"""
Model Health Page
Monitor ML model performance: AUC trends, PSI, feature drift
"""

import streamlit as st
import pandas as pd
from datetime import date, timedelta

from database import execute_query
from auth import require_permission


@require_permission("model_health")
def render():
    """Render Model Health page."""
    st.title("🔬 Model Health")
    st.markdown(f"**Date:** {date.today().strftime('%Y-%m-%d')}")
    st.markdown("---")

    # Model selection
    model_name = st.selectbox(
        "Select Model",
        options=["bounce_model", "self_cure_model", "roll_forward_model"],
        format_func=lambda x: x.replace('_', ' ').title()
    )

    st.markdown("---")

    # Model overview
    show_model_overview(model_name)

    st.markdown("---")

    col1, col2 = st.columns(2)

    with col1:
        show_model_registry(model_name)
        show_feature_importance(model_name)

    with col2:
        show_performance_trends(model_name)
        show_score_distribution(model_name)


def show_model_overview(model_name: str):
    """
    Display model overview and key metrics.

    Args:
        model_name: Model identifier
    """
    st.subheader("Model Overview")

    try:
        query = """
            SELECT
                model_name,
                version,
                train_date,
                auc,
                precision,
                recall,
                feature_count,
                train_samples,
                params
            FROM model_registry
            WHERE model_name = %s
              AND active = true
            ORDER BY train_date DESC
            LIMIT 1
        """
        results = execute_query(query, (model_name,))

        if results:
            model = results[0]

            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.metric("Version", model['version'])
            with col2:
                auc = model['auc'] or 0
                st.metric("AUC", f"{auc:.4f}")
            with col3:
                precision = model['precision'] or 0
                st.metric("Precision", f"{precision:.4f}")
            with col4:
                recall = model['recall'] or 0
                st.metric("Recall", f"{recall:.4f}")

            st.info(f"""
            **Model Details:**
            - Train Date: {model['train_date']}
            - Features: {model['feature_count']}
            - Training Samples: {model['train_samples']:,}
            """)

        else:
            st.warning(f"No active model found for {model_name}")

    except Exception as e:
        st.error(f"Error loading model overview: {e}")


def show_model_registry(model_name: str):
    """
    Display model registry history.

    Args:
        model_name: Model identifier
    """
    st.subheader("Model Registry")

    try:
        query = """
            SELECT
                version,
                train_date,
                auc,
                active,
                created_at
            FROM model_registry
            WHERE model_name = %s
            ORDER BY train_date DESC
            LIMIT 10
        """
        results = execute_query(query, (model_name,))

        if results:
            df = pd.DataFrame(results)
            df['train_date'] = pd.to_datetime(df['train_date']).dt.date
            df['active'] = df['active'].map({True: '✓', False: ''})

            st.dataframe(
                df[['version', 'train_date', 'auc', 'active']],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("No model versions found")

    except Exception as e:
        st.error(f"Error loading model registry: {e}")


def show_feature_importance(model_name: str):
    """
    Display feature importance.

    Args:
        model_name: Model identifier
    """
    st.subheader("Feature Importance")

    try:
        # This would come from SHAP values stored in model metadata
        # For now, show placeholder
        st.info("""
        **Top Features** (based on SHAP values):

        Feature importance data would be loaded from model metadata.
        This shows which features contribute most to predictions.

        Examples:
        1. dpd (days past due) - 0.24
        2. overdue_amt - 0.18
        3. bounce_count_6m - 0.15
        4. payment_consistency - 0.12
        5. product_type - 0.09
        """)

    except Exception as e:
        st.error(f"Error loading feature importance: {e}")


def show_performance_trends(model_name: str):
    """
    Display model performance trends over time.

    Args:
        model_name: Model identifier
    """
    st.subheader("Performance Trends")

    try:
        query = """
            SELECT
                train_date,
                auc,
                precision,
                recall
            FROM model_registry
            WHERE model_name = %s
            ORDER BY train_date
            LIMIT 30
        """
        results = execute_query(query, (model_name,))

        if results:
            df = pd.DataFrame(results)
            df['train_date'] = pd.to_datetime(df['train_date'])

            # Line chart
            chart_df = df.set_index('train_date')[['auc', 'precision', 'recall']]
            st.line_chart(chart_df)

            st.caption("Tracking AUC, Precision, and Recall over model versions")
        else:
            st.info("No performance trend data available")

    except Exception as e:
        st.error(f"Error loading performance trends: {e}")


def show_score_distribution(model_name: str):
    """
    Display current score distribution.

    Args:
        model_name: Model identifier
    """
    st.subheader("Score Distribution (Current)")

    try:
        # Map model names to score columns
        score_columns = {
            "bounce_model": "bounce_p",
            "self_cure_model": "self_cure_p",
            "roll_forward_model": "roll_p",
        }

        score_col = score_columns.get(model_name)

        if not score_col:
            st.warning("Score column not mapped for this model")
            return

        query = f"""
            SELECT
                CASE
                    WHEN {score_col} < 0.1 THEN '0-10%'
                    WHEN {score_col} < 0.2 THEN '10-20%'
                    WHEN {score_col} < 0.3 THEN '20-30%'
                    WHEN {score_col} < 0.4 THEN '30-40%'
                    WHEN {score_col} < 0.5 THEN '40-50%'
                    WHEN {score_col} < 0.6 THEN '50-60%'
                    WHEN {score_col} < 0.7 THEN '60-70%'
                    WHEN {score_col} < 0.8 THEN '70-80%'
                    WHEN {score_col} < 0.9 THEN '80-90%'
                    ELSE '90-100%'
                END as score_bucket,
                COUNT(*) as account_count
            FROM mart_account_daily
            WHERE date = CURRENT_DATE
              AND {score_col} IS NOT NULL
            GROUP BY score_bucket
            ORDER BY score_bucket
        """
        results = execute_query(query)

        if results:
            df = pd.DataFrame(results)
            st.bar_chart(df.set_index('score_bucket')['account_count'])

            st.caption("Distribution of model scores across current portfolio")

            # PSI check
            st.info("""
            **PSI Monitoring:**

            Population Stability Index (PSI) would be calculated here to detect
            distribution drift between training and current scoring populations.

            - PSI < 0.1: No significant change
            - PSI 0.1-0.2: Moderate change, investigate
            - PSI > 0.2: Significant drift, consider retraining
            """)
        else:
            st.info("No score distribution data available")

    except Exception as e:
        st.error(f"Error loading score distribution: {e}")
