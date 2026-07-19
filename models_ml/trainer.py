"""
Model training pipeline with calibration and SHAP explainability.
"""

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import roc_auc_score, classification_report, confusion_matrix
import shap
import pickle
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Tuple, List, Optional
import warnings
warnings.filterwarnings('ignore')

from .config import (
    TRAINING_CONFIG,
    MODEL_CONFIGS,
    FEATURE_IMPORTANCE_THRESHOLD,
    MODEL_ARTIFACTS_DIR,
    SHAP_ARTIFACTS_DIR,
)


class CalibratedLGBM:
    """Wrapper for LightGBM model with calibration."""

    def __init__(self, lgbm_model, calibrator):
        self.lgbm_model = lgbm_model
        self.calibrator = calibrator

    def predict_proba(self, X):
        # Get LightGBM predictions
        preds = self.lgbm_model.predict(X)
        # Calibrate
        calibrated = self.calibrator.predict(preds.reshape(-1, 1))
        # Return as [P(0), P(1)] format
        return np.column_stack([1 - calibrated, calibrated])

    def predict(self, X):
        probs = self.predict_proba(X)[:, 1]
        return (probs >= 0.5).astype(int)


class ModelTrainer:
    """
    Trains LightGBM models with calibration and SHAP explainability.
    """

    def __init__(self, model_name: str):
        """
        Initialize trainer for a specific model.

        Args:
            model_name: One of 'bounce', 'selfcure', 'rollforward'
        """
        if model_name not in MODEL_CONFIGS:
            raise ValueError(f"Unknown model: {model_name}")

        self.model_name = model_name
        self.config = MODEL_CONFIGS[model_name]
        self.model = None
        self.calibrated_model = None
        self.feature_names = None
        self.feature_importance = None
        self.shap_explainer = None
        self.metrics = {}

        # Create artifact directories
        Path(MODEL_ARTIFACTS_DIR).mkdir(parents=True, exist_ok=True)
        Path(SHAP_ARTIFACTS_DIR).mkdir(parents=True, exist_ok=True)

    def prepare_data(
        self,
        df: pd.DataFrame,
        target_col: str = "target"
    ) -> Tuple[pd.DataFrame, pd.Series, pd.DataFrame, pd.Series, pd.DataFrame, pd.Series]:
        """
        Prepare data for training with train/val/test split.

        Args:
            df: Feature dataframe with target column
            target_col: Name of target column

        Returns:
            X_train, y_train, X_val, y_val, X_test, y_test
        """
        # Separate features and target
        y = df[target_col]
        X = df.drop(columns=[target_col, 'account_id'], errors='ignore')

        # Handle categorical variables
        categorical_cols = X.select_dtypes(include=['object', 'category']).columns
        for col in categorical_cols:
            X[col] = X[col].astype('category')

        self.feature_names = X.columns.tolist()

        # Split: 70% train, 10% val, 20% test
        X_temp, X_test, y_temp, y_test = train_test_split(
            X, y,
            test_size=TRAINING_CONFIG['test_size'],
            random_state=TRAINING_CONFIG['random_state'],
            stratify=y if y.value_counts().min() > 10 else None
        )

        X_train, X_val, y_train, y_val = train_test_split(
            X_temp, y_temp,
            test_size=TRAINING_CONFIG['val_size'] / (1 - TRAINING_CONFIG['test_size']),
            random_state=TRAINING_CONFIG['random_state'],
            stratify=y_temp if y_temp.value_counts().min() > 10 else None
        )

        print(f"Data split: Train={len(X_train)}, Val={len(X_val)}, Test={len(X_test)}")
        print(f"Target distribution in train: {y_train.value_counts().to_dict()}")

        return X_train, y_train, X_val, y_val, X_test, y_test

    def train(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_val: pd.DataFrame,
        y_val: pd.Series
    ):
        """
        Train LightGBM model with early stopping.

        Args:
            X_train: Training features
            y_train: Training target
            X_val: Validation features
            y_val: Validation target
        """
        print(f"\n{'='*60}")
        print(f"Training {self.config['name']}")
        print(f"Description: {self.config['description']}")
        print(f"Target AUC: {self.config['target_auc']}")
        print(f"{'='*60}\n")

        # Create datasets
        train_data = lgb.Dataset(X_train, label=y_train)
        val_data = lgb.Dataset(X_val, label=y_val, reference=train_data)

        # Train model
        params = self.config['lgbm_params'].copy()
        num_boost_round = params.pop('num_boost_round', 100)

        self.model = lgb.train(
            params,
            train_data,
            num_boost_round=num_boost_round,
            valid_sets=[train_data, val_data],
            valid_names=['train', 'val'],
            callbacks=[
                lgb.early_stopping(stopping_rounds=20, verbose=True),
                lgb.log_evaluation(period=50)
            ]
        )

        # Feature importance
        self.feature_importance = pd.DataFrame({
            'feature': self.feature_names,
            'importance': self.model.feature_importance(importance_type='gain')
        }).sort_values('importance', ascending=False)

        print(f"\nTop 10 important features:")
        print(self.feature_importance.head(10))

    def calibrate(
        self,
        X_val: pd.DataFrame,
        y_val: pd.Series
    ):
        """
        Calibrate model probabilities using isotonic regression.

        Args:
            X_val: Validation features
            y_val: Validation target
        """
        print(f"\nCalibrating model using {TRAINING_CONFIG['calibration_method']} method...")

        # Get uncalibrated predictions from LightGBM model
        from sklearn.isotonic import IsotonicRegression
        from sklearn.calibration import CalibratedClassifierCV

        y_pred_uncalibrated = self.model.predict(X_val)

        # Fit calibrator
        if TRAINING_CONFIG['calibration_method'] == 'isotonic':
            self.calibrator = IsotonicRegression(out_of_bounds='clip')
        else:  # sigmoid
            from sklearn.linear_model import LogisticRegression
            self.calibrator = LogisticRegression()

        self.calibrator.fit(y_pred_uncalibrated.reshape(-1, 1), y_val)

        # Create calibrated model wrapper
        self.calibrated_model = CalibratedLGBM(self.model, self.calibrator)

        print("Calibration complete.")

    def evaluate(
        self,
        X_test: pd.DataFrame,
        y_test: pd.Series
    ) -> Dict:
        """
        Evaluate model on test set.

        Args:
            X_test: Test features
            y_test: Test target

        Returns:
            Dictionary of metrics
        """
        print("\nEvaluating model on test set...")

        # Predictions
        y_pred_proba = self.calibrated_model.predict_proba(X_test)[:, 1]
        y_pred = (y_pred_proba >= 0.5).astype(int)

        # Metrics
        auc = roc_auc_score(y_test, y_pred_proba)

        self.metrics = {
            'model_name': self.config['name'],
            'auc': float(auc),
            'target_auc': self.config['target_auc'],
            'min_auc': self.config['min_auc'],
            'test_size': len(y_test),
            'positive_rate': float(y_test.mean()),
            'trained_at': datetime.now().isoformat(),
        }

        print(f"\n{'='*60}")
        print(f"RESULTS: {self.config['name']}")
        print(f"{'='*60}")
        print(f"AUC: {auc:.4f} (Target: {self.config['target_auc']:.2f}, Min: {self.config['min_auc']:.2f})")
        print(f"Test samples: {len(y_test)} (Positive: {y_test.sum()}, Negative: {(1-y_test).sum()})")
        print(f"\nConfusion Matrix:")
        print(confusion_matrix(y_test, y_pred))

        if auc >= self.config['min_auc']:
            print(f"\n✅ Model meets minimum AUC threshold!")
        else:
            print(f"\n❌ Model below minimum AUC threshold. Needs improvement.")

        return self.metrics

    def explain_with_shap(
        self,
        X_sample: pd.DataFrame,
        save_summary: bool = True
    ):
        """
        Generate SHAP explanations for model predictions.

        Args:
            X_sample: Sample of features for SHAP (typically X_test sample)
            save_summary: Whether to save SHAP summary plot
        """
        print("\nGenerating SHAP explanations...")

        # Sample for SHAP (computational cost)
        if len(X_sample) > TRAINING_CONFIG['shap_sample_size']:
            X_sample = X_sample.sample(
                n=TRAINING_CONFIG['shap_sample_size'],
                random_state=TRAINING_CONFIG['random_state']
            )

        # Create SHAP explainer
        self.shap_explainer = shap.TreeExplainer(self.model)
        shap_values = self.shap_explainer.shap_values(X_sample)

        # Global feature importance (mean absolute SHAP)
        if isinstance(shap_values, list):  # Binary classification returns list
            shap_values = shap_values[1]  # Positive class

        shap_importance = pd.DataFrame({
            'feature': self.feature_names,
            'mean_abs_shap': np.abs(shap_values).mean(axis=0)
        }).sort_values('mean_abs_shap', ascending=False)

        print(f"\nTop 10 features by SHAP importance:")
        print(shap_importance.head(10))

        # Save SHAP values
        if save_summary:
            shap_path = Path(SHAP_ARTIFACTS_DIR) / f"{self.model_name}_shap.pkl"
            with open(shap_path, 'wb') as f:
                pickle.dump({
                    'shap_values': shap_values,
                    'feature_names': self.feature_names,
                    'importance': shap_importance
                }, f)
            print(f"SHAP values saved to {shap_path}")

        return shap_importance

    def save_model(self, version: str = "1.0.0"):
        """
        Save trained model and metadata.

        Args:
            version: Model version string
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        model_dir = Path(MODEL_ARTIFACTS_DIR) / f"{self.model_name}_v{version}_{timestamp}"
        model_dir.mkdir(parents=True, exist_ok=True)

        # Save LightGBM model
        model_path = model_dir / "model.txt"
        self.model.save_model(str(model_path))

        # Save calibrated model
        calibrated_path = model_dir / "calibrated_model.pkl"
        with open(calibrated_path, 'wb') as f:
            pickle.dump(self.calibrated_model, f)

        # Save metadata
        metadata = {
            'model_name': self.config['name'],
            'version': version,
            'trained_at': datetime.now().isoformat(),
            'feature_names': self.feature_names,
            'metrics': self.metrics,
            'config': self.config,
        }

        metadata_path = model_dir / "metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)

        # Save feature importance
        importance_path = model_dir / "feature_importance.csv"
        self.feature_importance.to_csv(importance_path, index=False)

        print(f"\nModel saved to: {model_dir}")
        return str(model_dir)
