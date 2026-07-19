"""
Model registry - tracks model versions, performance, and metadata in PostgreSQL.
"""

import psycopg2
from psycopg2.extras import execute_values
from datetime import datetime
from typing import Dict, List, Optional
import json

from .config import DB_CONFIG


class ModelRegistry:
    """
    Manages model versioning and metadata in the model_registry table.
    """

    def __init__(self):
        self.conn = psycopg2.connect(**DB_CONFIG)
        self.cursor = self.conn.cursor()

    def __del__(self):
        if hasattr(self, 'cursor'):
            self.cursor.close()
        if hasattr(self, 'conn'):
            self.conn.close()

    def register_model(
        self,
        model_name: str,
        version: str,
        model_path: str,
        metrics: Dict,
        feature_names: List[str],
        config: Dict,
        notes: Optional[str] = None
    ) -> int:
        """
        Register a trained model in the registry.

        Args:
            model_name: Model identifier (e.g., 'M1_Bounce')
            version: Version string (e.g., '1.0.0')
            model_path: Path to saved model artifacts
            metrics: Dictionary of performance metrics (must include 'auc')
            feature_names: List of feature names used
            config: Model configuration dict
            notes: Optional notes about the model

        Returns:
            model_id of the registered model
        """
        query = """
        INSERT INTO model_registry (
            model_name, version, model_type, trained_on, training_rows, auc,
            model_path, feature_list, hyperparameters, notes, is_champion
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING model_id
        """

        values = (
            model_name,
            version,
            'lightgbm',  # Model type
            datetime.now(),
            metrics.get('test_size', 0),  # Training rows
            metrics.get('auc'),
            model_path,
            json.dumps(feature_names),
            json.dumps(config.get('lgbm_params', {})),
            notes,
            False  # Not champion yet - requires manual promotion
        )

        try:
            self.cursor.execute(query, values)
            model_id = self.cursor.fetchone()[0]
            self.conn.commit()
            print(f"✅ Model registered: {model_name} v{version} (ID: {model_id})")
            return model_id
        except Exception as e:
            self.conn.rollback()
            print(f"❌ Error registering model: {e}")
            raise

    def get_champion_model(self, model_name: str) -> Optional[Dict]:
        """
        Get the currently champion model for a given model name.

        Args:
            model_name: Model identifier

        Returns:
            Dictionary with model metadata, or None if not found
        """
        query = """
        SELECT model_id, model_name, version, trained_on, auc,
               model_path, feature_list, is_champion
        FROM model_registry
        WHERE model_name = %s AND is_champion = TRUE
        ORDER BY trained_on DESC
        LIMIT 1
        """

        self.cursor.execute(query, (model_name,))
        row = self.cursor.fetchone()

        if row:
            return {
                'model_id': row[0],
                'model_name': row[1],
                'version': row[2],
                'trained_on': row[3],
                'auc': row[4],
                'model_path': row[5],
                'feature_names': json.loads(row[6]) if row[6] else [],
                'is_champion': row[7],
            }
        return None

    def promote_to_champion(self, model_id: int):
        """
        Promote a model to champion (demotes existing champion).

        Args:
            model_id: ID of the model to promote
        """
        # Get model name
        self.cursor.execute("SELECT model_name FROM model_registry WHERE model_id = %s", (model_id,))
        row = self.cursor.fetchone()
        if not row:
            raise ValueError(f"Model {model_id} not found")

        model_name = row[0]

        # Demote existing champion
        self.cursor.execute(
            "UPDATE model_registry SET is_champion = FALSE WHERE model_name = %s AND is_champion = TRUE",
            (model_name,)
        )

        # Promote new champion
        self.cursor.execute(
            "UPDATE model_registry SET is_champion = TRUE, promoted_at = %s WHERE model_id = %s",
            (datetime.now(), model_id)
        )

        self.conn.commit()
        print(f"✅ Model {model_id} promoted to champion for {model_name}")

    def get_model_history(self, model_name: str, limit: int = 10) -> List[Dict]:
        """
        Get training history for a model.

        Args:
            model_name: Model identifier
            limit: Number of recent versions to return

        Returns:
            List of model metadata dictionaries
        """
        query = """
        SELECT model_id, version, trained_on, auc, is_champion
        FROM model_registry
        WHERE model_name = %s
        ORDER BY trained_on DESC
        LIMIT %s
        """

        self.cursor.execute(query, (model_name, limit))
        rows = self.cursor.fetchall()

        return [
            {
                'model_id': row[0],
                'version': row[1],
                'trained_on': row[2],
                'auc': row[3],
                'is_champion': row[4],
            }
            for row in rows
        ]

    def close(self):
        """Close database connection."""
        if hasattr(self, 'cursor'):
            self.cursor.close()
        if hasattr(self, 'conn'):
            self.conn.close()
