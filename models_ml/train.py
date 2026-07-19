"""
Training script for CollectOS ML models.
Trains M1 (Bounce) and M2 (Self-cure) models.

Usage:
    python -m models_ml.train --model bounce --as-of-date 2026-06-30
    python -m models_ml.train --model selfcure --as-of-date 2026-06-30
"""

import argparse
from datetime import datetime, timedelta
import sys

from .features import FeatureEngineer
from .trainer import ModelTrainer
from .registry import ModelRegistry


def train_model(model_name: str, as_of_date: str):
    """
    Train a model with the specified configuration.

    Args:
        model_name: One of 'bounce', 'selfcure'
        as_of_date: Date to build features as of (YYYY-MM-DD)
    """
    print(f"\n{'='*80}")
    print(f"CollectOS ML Training Pipeline")
    print(f"Model: {model_name.upper()}")
    print(f"As-of Date: {as_of_date}")
    print(f"{'='*80}\n")

    # Step 1: Feature Engineering
    print("Step 1: Building features...")
    feature_engineer = FeatureEngineer()

    if model_name == 'bounce':
        df = feature_engineer.build_bounce_features(
            as_of_date=as_of_date,
            lookback_months=24
        )
    elif model_name == 'selfcure':
        df = feature_engineer.build_selfcure_features(
            as_of_date=as_of_date,
            lookback_months=12
        )
    else:
        raise ValueError(f"Unknown model: {model_name}")

    feature_engineer.close()

    if len(df) < 100:
        print(f"❌ Insufficient data: only {len(df)} samples. Need at least 100.")
        sys.exit(1)

    print(f"✅ Built {len(df)} training samples")
    print(f"   Positive rate: {df['target'].mean():.2%}")

    # Step 2: Train Model
    print("\nStep 2: Training model...")
    trainer = ModelTrainer(model_name)

    X_train, y_train, X_val, y_val, X_test, y_test = trainer.prepare_data(df)
    trainer.train(X_train, y_train, X_val, y_val)

    # Step 3: Calibrate
    print("\nStep 3: Calibrating probabilities...")
    trainer.calibrate(X_val, y_val)

    # Step 4: Evaluate
    print("\nStep 4: Evaluating on test set...")
    metrics = trainer.evaluate(X_test, y_test)

    # Step 5: SHAP Explainability
    print("\nStep 5: Generating SHAP explanations...")
    shap_importance = trainer.explain_with_shap(X_test, save_summary=True)

    # Step 6: Save Model
    print("\nStep 6: Saving model artifacts...")
    version = "1.0.0"
    model_path = trainer.save_model(version=version)

    # Step 7: Register in Database (optional - requires migration 006)
    print("\nStep 7: Registering model in database...")
    model_id = None
    try:
        registry = ModelRegistry()
        model_id = registry.register_model(
            model_name=trainer.config['name'],
            version=version,
            model_path=model_path,
            metrics=metrics,
            feature_names=trainer.feature_names,
            config=trainer.config,
            notes=f"Trained on synthetic data as of {as_of_date}"
        )
        registry.close()
    except Exception as e:
        print(f"⚠️  Model registry unavailable (table not found). Model saved to disk only.")
        print(f"    To enable registry, ensure migration 006 is applied.")

    # Final summary
    print(f"\n{'='*80}")
    print("TRAINING COMPLETE")
    print(f"{'='*80}")
    if model_id:
        print(f"Model ID: {model_id}")
    print(f"Model Path: {model_path}")
    print(f"AUC: {metrics['auc']:.4f}")
    print(f"Target AUC: {metrics['target_auc']:.2f}")
    print(f"Status: {'✅ PASS' if metrics['auc'] >= metrics['min_auc'] else '❌ FAIL'}")
    print(f"{'='*80}\n")

    return metrics


def main():
    parser = argparse.ArgumentParser(description="Train CollectOS ML models")
    parser.add_argument(
        '--model',
        type=str,
        required=True,
        choices=['bounce', 'selfcure'],
        help="Model to train: bounce or selfcure"
    )
    parser.add_argument(
        '--as-of-date',
        type=str,
        default=(datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'),
        help="As-of date for features (YYYY-MM-DD). Defaults to 30 days ago."
    )

    args = parser.parse_args()

    try:
        metrics = train_model(args.model, args.as_of_date)
        sys.exit(0 if metrics['auc'] >= metrics['min_auc'] else 1)
    except Exception as e:
        print(f"\n❌ Training failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
