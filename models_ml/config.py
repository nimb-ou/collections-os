"""
ML model configuration.
Defines model parameters, feature sets, and training config.
"""

from typing import Dict, List, Any
from datetime import date

# Model registry database connection (reuses main DB)
import os
DB_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "localhost"),
    "port": int(os.getenv("POSTGRES_PORT", 5432)),
    "user": os.getenv("POSTGRES_USER", "collectos"),
    "password": os.getenv("POSTGRES_PASSWORD", "collectos_dev_password_change_in_production"),
    "database": os.getenv("POSTGRES_DB", "collectos"),
}

# Training configuration
TRAINING_CONFIG = {
    "test_size": 0.2,
    "val_size": 0.1,
    "random_state": 42,
    "calibration_method": "isotonic",  # isotonic or sigmoid
    "shap_sample_size": 1000,  # Sample for SHAP explanation
}

# LightGBM default parameters (can be overridden per model)
LIGHTGBM_PARAMS = {
    "objective": "binary",
    "metric": "auc",
    "boosting_type": "gbdt",
    "num_leaves": 31,
    "learning_rate": 0.05,
    "feature_fraction": 0.8,
    "bagging_fraction": 0.8,
    "bagging_freq": 5,
    "verbose": -1,
    "seed": 42,
}

# Model-specific configurations
MODEL_CONFIGS: Dict[str, Dict[str, Any]] = {
    "bounce": {
        "name": "M1_Bounce",
        "description": "Predicts probability of EMI presentation bounce",
        "target_auc": 0.78,
        "min_auc": 0.75,
        "features": [
            # Behavioral history features
            "bounce_rate_3m", "bounce_rate_6m", "bounce_rate_12m",
            "avg_days_to_clear_3m", "avg_days_to_clear_6m",
            "max_dpd_3m", "max_dpd_6m", "max_dpd_12m",
            "payment_regularity_6m",  # Coefficient of variation in payment timing

            # Account characteristics
            "product_type", "vintage_months", "emi_amt", "disbursal_amt",
            "roi", "tenure_m", "cycle_day",

            # Current state
            "current_dpd", "current_bucket", "overdue_amt", "pos",
            "emi_to_income_ratio",  # If available

            # Geographic and seasonal
            "state", "seasonality_month",  # Month of year for seasonal patterns

            # Recent activity
            "last_bounce_days_ago", "consecutive_bounces",
        ],
        "lgbm_params": {
            **LIGHTGBM_PARAMS,
            "num_boost_round": 200,
        }
    },

    "selfcure": {
        "name": "M2_SelfCure",
        "description": "Predicts probability of self-cure within 7 days post-bounce",
        "target_auc": 0.75,
        "min_auc": 0.72,
        "features": [
            # Historical self-cure pattern
            "selfcure_rate_6m", "selfcure_rate_12m",
            "avg_days_to_selfcure",

            # Bounce characteristics
            "bounce_reason", "bounce_count_this_month",
            "days_since_last_bounce",

            # Payment patterns
            "payment_regularity_6m",
            "avg_payment_delay_days",
            "typical_payday",  # Day of month customer usually pays

            # Financial stress indicators
            "current_dpd", "overdue_amt", "pos",
            "emi_to_overdue_ratio",

            # Account basics
            "product_type", "vintage_months", "emi_amt",

            # Recent contact
            "calls_last_7d", "last_ptp_status",
        ],
        "lgbm_params": {
            **LIGHTGBM_PARAMS,
            "num_boost_round": 150,
        }
    },

    "rollforward": {
        "name": "M3_RollForward",
        "description": "Predicts probability of rolling to next bucket at month-end",
        "target_auc": 0.75,
        "min_auc": 0.72,
        "features": [
            # Payment behavior
            "payments_to_demand_ratio_3m",
            "partial_payment_rate_6m",
            "payment_amount_cv",  # Coefficient of variation

            # Collection activity
            "call_connect_rate_1m",
            "ptp_made_count_1m", "ptp_kept_rate_6m",
            "last_disposition",

            # Current bucket and trajectory
            "current_bucket", "current_dpd", "bucket_duration_days",
            "dpd_trend_30d",  # Increasing/decreasing

            # Obligations
            "overdue_amt", "total_dues", "pos",
            "emi_amt", "installments_remaining",

            # Account characteristics
            "product_type", "vintage_months",

            # Macro factors
            "state", "seasonality_month",
            "geo_stress_index",  # Aggregate stress in geography
        ],
        "lgbm_params": {
            **LIGHTGBM_PARAMS,
            "num_boost_round": 180,
        }
    },
}

# Feature importance thresholds
FEATURE_IMPORTANCE_THRESHOLD = 0.01  # Drop features with < 1% importance

# Model artifact paths
MODEL_ARTIFACTS_DIR = "models_ml/artifacts"
SHAP_ARTIFACTS_DIR = "models_ml/shap"

# Scoring configuration
BATCH_SCORING_CONFIG = {
    "chunk_size": 10000,  # Process in chunks for memory efficiency
    "n_jobs": -1,  # Use all CPU cores
}
