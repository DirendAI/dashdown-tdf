#!/usr/bin/env python3
"""
Train ML models for Tour de France predictions.

This script trains models to predict:
1. Stage winners based on rider characteristics and stage profile
2. General Classification (GC) contenders
3. Points jersey contenders
4. Mountains jersey contenders

Models are saved and can be used to generate predictions for 2026 stages.

Usage:
    python scripts/train_predictions.py --train
    python scripts/train_predictions.py --predict --stage 15
    python scripts/train_predictions.py --predict-all
"""

import argparse
import json
import os
import pickle
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import (
    GradientBoostingClassifier,
    GradientBoostingRegressor,
    RandomForestClassifier,
    RandomForestRegressor,
)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    mean_absolute_error,
    mean_squared_error,
    r2_score,
)


class TDFPredictor:
    """ML models for Tour de France predictions."""
    
    def __init__(self, data_dir: Path = Path("data")):
        self.data_dir = data_dir
        self.models_dir = Path("models")
        self.models_dir.mkdir(parents=True, exist_ok=True)
        
        # Feature engineering parameters
        self.stage_type_order = {"Flat": 0, "Hilly": 1, "Mountain": 2, "Prologue": 3, "Individual Time Trial": 4}
        self.specialist_order = {"Sprinter": 0, "Lead-out": 1, "Puncheur": 2, "All-Rounder": 3, "Climber": 4}
        
        # Models
        self.models = {
            "stage_winner": None,
            "gc_position": None,
            "points_jersey": None,
            "mountains_jersey": None,
            "time_gap": None,
        }
        
        # Feature columns
        self.rider_features = [
            "age", "height_m", "weight_kg", "uci_points", "2026_wins", 
            "grand_tour_wins", "bmi"
        ]
        self.stage_features = [
            "distance_km", "elevation_m", "is_mountain_stage", "is_tt",
            "num_climbs_hc", "num_climbs_cat1", "num_climbs_cat2"
        ]
        self.team_features = ["team_budget_million"]
        
        # Target columns
        self.targets = {
            "stage_winner": "won_stage",
            "gc_position": "gc_position",
            "points_jersey": "points_jersey_contender",
            "mountains_jersey": "mountains_jersey_contender",
            "time_gap": "time_gap_seconds",
        }
    
    def load_data(self) -> Dict[str, pd.DataFrame]:
        """Load training data from parquet files."""
        data = {}
        
        # Load historical results
        historical_path = self.data_dir / "historical" / "results.parquet"
        if historical_path.exists():
            data["historical"] = pd.read_parquet(historical_path)
        
        # Load 2026 data
        live_dir = self.data_dir / "live"
        if live_dir.exists():
            for file in live_dir.glob("*.parquet"):
                name = file.stem
                data[name] = pd.read_parquet(file)
        
        return data
    
    def prepare_training_data(self, data: Dict[str, pd.DataFrame]) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """Prepare training data with feature engineering."""
        if "historical" not in data:
            raise ValueError("Historical data not found")
        
        df = data["historical"].copy()
        
        # Add rider features (mock for now - in production, join with rider table)
        rider_stats = {
            "Jonas Vingegaard": {"age": 27, "height_m": 1.75, "weight_kg": 62, "uci_points": 4500, 
                               "2026_wins": 5, "grand_tour_wins": 3},
            "Tadej Pogacar": {"age": 25, "height_m": 1.76, "weight_kg": 58, "uci_points": 4800,
                              "2026_wins": 8, "grand_tour_wins": 3},
            "Adam Yates": {"age": 31, "height_m": 1.74, "weight_kg": 58, "uci_points": 3500,
                          "2026_wins": 3, "grand_tour_wins": 1},
            "Wout van Aert": {"age": 29, "height_m": 1.87, "weight_kg": 78, "uci_points": 4200,
                             "2026_wins": 10, "grand_tour_wins": 0},
            "Remco Evenepoel": {"age": 24, "height_m": 1.72, "weight_kg": 60, "uci_points": 4000,
                                "2026_wins": 6, "grand_tour_wins": 1},
        }
        
        for rider, stats in rider_stats.items():
            mask = df["rider"] == rider
            for key, value in stats.items():
                df.loc[mask, key] = value
        
        # Calculate BMI
        df["bmi"] = df["weight_kg"] / (df["height_m"] ** 2)
        
        # Add stage features
        stage_profiles = {
            1: {"distance_km": 8.0, "elevation_m": 50, "is_mountain_stage": False, 
                "is_tt": True, "num_climbs_hc": 0, "num_climbs_cat1": 0, "num_climbs_cat2": 0},
            5: {"distance_km": 160, "elevation_m": 3500, "is_mountain_stage": True,
                "is_tt": False, "num_climbs_hc": 2, "num_climbs_cat1": 0, "num_climbs_cat2": 1},
            10: {"distance_km": 180, "elevation_m": 4000, "is_mountain_stage": True,
                 "is_tt": False, "num_climbs_hc": 1, "num_climbs_cat1": 1, "num_climbs_cat2": 0},
            15: {"distance_km": 170, "elevation_m": 4500, "is_mountain_stage": True,
                 "is_tt": False, "num_climbs_hc": 2, "num_climbs_cat1": 1, "num_climbs_cat2": 0},
            20: {"distance_km": 34, "elevation_m": 200, "is_mountain_stage": False,
                 "is_tt": True, "num_climbs_hc": 0, "num_climbs_cat1": 0, "num_climbs_cat2": 0},
        }
        
        for stage, profile in stage_profiles.items():
            mask = df["stage"] == stage
            for key, value in profile.items():
                df.loc[mask, key] = value
        
        # Fill missing stage profiles with defaults
        for col in self.stage_features:
            if col not in df.columns:
                df[col] = 0
            df[col].fillna(0, inplace=True)
        
        # Add team features
        team_budgets = {
            "Team Visma | Lease a Bike": 45,
            "UAE Team Emirates": 50,
            "Soudal Quick-Step": 40,
        }
        df["team_budget_million"] = df["team"].map(team_budgets).fillna(30)
        
        # Create target: won_stage (1 if position == 1, else 0)
        df["won_stage"] = (df["position"] == 1).astype(int)
        
        # Create target: gc_position (for GC prediction)
        # This would come from overall GC standings in real data
        gc_positions = {
            "Jonas Vingegaard": 1,
            "Tadej Pogacar": 2,
            "Adam Yates": 3,
            "Wout van Aert": 4,
            "Remco Evenepoel": 5,
        }
        df["gc_position"] = df["rider"].map(gc_positions).fillna(10)
        
        # Create target: time_gap_seconds
        # Parse time gap and convert to seconds
        def parse_gap(gap_str):
            if gap_str == "0" or pd.isna(gap_str):
                return 0
            if ":" in gap_str:
                parts = gap_str.replace("+", "").split(":")
                if len(parts) == 2:
                    return int(parts[0]) * 60 + int(parts[1])
                elif len(parts) == 3:
                    return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
            return 0
        
        df["time_gap_seconds"] = df["gap"].apply(parse_gap)
        
        # Create specialist features
        specialist_map = {
            "Jonas Vingegaard": "Climber",
            "Tadej Pogacar": "Climber",
            "Adam Yates": "Climber",
            "Wout van Aert": "All-Rounder",
            "Remco Evenepoel": "Climber",
        }
        df["specialist"] = df["rider"].map(specialist_map).fillna("All-Rounder")
        df["specialist_encoded"] = df["specialist"].map(self.specialist_order).fillna(2)
        
        # Create stage type encoded
        df["stage_type_encoded"] = df["stage_type"].map(self.stage_type_order).fillna(0)
        
        # Create jersey contender targets (simplified)
        df["points_jersey_contender"] = ((df["specialist"] == "Sprinter") | (df["position"] <= 3)).astype(int)
        df["mountains_jersey_contender"] = ((df["specialist"] == "Climber") | (df["position"] <= 3)).astype(int)
        
        # Store feature info
        feature_info = {
            "rider_features": self.rider_features,
            "stage_features": self.stage_features,
            "team_features": self.team_features,
            "all_features": self.rider_features + self.stage_features + self.team_features + 
                           ["specialist_encoded", "stage_type_encoded"],
            "categorical_features": ["specialist", "stage_type"],
            "numeric_features": self.rider_features + self.stage_features + self.team_features,
        }
        
        return df, feature_info
    
    def train_models(self, df: pd.DataFrame, feature_info: Dict[str, Any]) -> Dict[str, Any]:
        """Train all ML models."""
        results = {}
        
        # Prepare features and targets
        X = df[feature_info["all_features"]]
        
        # Train stage winner classifier
        print("Training stage winner classifier...")
        y_winner = df["won_stage"]
        X_train, X_test, y_train, y_test = train_test_split(X, y_winner, test_size=0.2, random_state=42)
        
        self.models["stage_winner"] = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            random_state=42,
            class_weight="balanced"
        )
        self.models["stage_winner"].fit(X_train, y_train)
        
        y_pred = self.models["stage_winner"].predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)
        results["stage_winner"] = {
            "accuracy": accuracy,
            "report": classification_report(y_test, y_pred, output_dict=True)
        }
        print(f"  Stage winner model accuracy: {accuracy:.3f}")
        
        # Train GC position regressor
        print("Training GC position predictor...")
        y_gc = df["gc_position"]
        X_train, X_test, y_train, y_test = train_test_split(X, y_gc, test_size=0.2, random_state=42)
        
        self.models["gc_position"] = GradientBoostingRegressor(
            n_estimators=100,
            max_depth=5,
            random_state=42
        )
        self.models["gc_position"].fit(X_train, y_train)
        
        y_pred = self.models["gc_position"].predict(X_test)
        mae = mean_absolute_error(y_test, y_pred)
        results["gc_position"] = {
            "mae": mae,
            "mse": mean_squared_error(y_test, y_pred),
            "r2": r2_score(y_test, y_pred)
        }
        print(f"  GC position model MAE: {mae:.2f}")
        
        # Train time gap predictor
        print("Training time gap predictor...")
        y_gap = df["time_gap_seconds"]
        X_train, X_test, y_train, y_test = train_test_split(X, y_gap, test_size=0.2, random_state=42)
        
        self.models["time_gap"] = RandomForestRegressor(
            n_estimators=100,
            max_depth=10,
            random_state=42
        )
        self.models["time_gap"].fit(X_train, y_train)
        
        y_pred = self.models["time_gap"].predict(X_test)
        mae = mean_absolute_error(y_test, y_pred)
        results["time_gap"] = {
            "mae": mae,
            "mse": mean_squared_error(y_test, y_pred),
            "r2": r2_score(y_test, y_pred)
        }
        print(f"  Time gap model MAE: {mae:.1f} seconds")
        
        # Train jersey contender classifiers
        print("Training jersey contender classifiers...")
        
        for jersey in ["points_jersey", "mountains_jersey"]:
            y_jersey = df[f"{jersey}_contender"]
            X_train, X_test, y_train, y_test = train_test_split(X, y_jersey, test_size=0.2, random_state=42)
            
            self.models[jersey] = RandomForestClassifier(
                n_estimators=50,
                max_depth=8,
                random_state=42
            )
            self.models[jersey].fit(X_train, y_train)
            
            y_pred = self.models[jersey].predict(X_test)
            accuracy = accuracy_score(y_test, y_pred)
            results[jersey] = {
                "accuracy": accuracy,
                "report": classification_report(y_test, y_pred, output_dict=True)
            }
            print(f"  {jersey} model accuracy: {accuracy:.3f}")
        
        return results
    
    def save_models(self):
        """Save trained models to disk."""
        for name, model in self.models.items():
            if model is not None:
                path = self.models_dir / f"{name}_model.pkl"
                joblib.dump(model, path)
                print(f"Saved model: {path}")
    
    def load_models(self):
        """Load trained models from disk."""
        for name in self.models.keys():
            path = self.models_dir / f"{name}_model.pkl"
            if path.exists():
                self.models[name] = joblib.load(path)
                print(f"Loaded model: {path}")
    
    def predict_stage_winners(self, stage_data: pd.DataFrame, riders: pd.DataFrame) -> pd.DataFrame:
        """Predict stage winners for a given stage."""
        if self.models["stage_winner"] is None:
            self.load_models()
        
        predictions = []
        
        for _, rider in riders.iterrows():
            # Create feature vector for this rider on this stage
            features = self._create_rider_stage_features(rider, stage_data)
            
            # Predict probability of winning
            proba = self.models["stage_winner"].predict_proba(features.reshape(1, -1))[0]
            win_prob = proba[1] if len(proba) > 1 else proba[0]
            
            # Predict GC position
            gc_pos = self.models["gc_position"].predict(features.reshape(1, -1))[0]
            
            # Predict time gap
            time_gap = self.models["time_gap"].predict(features.reshape(1, -1))[0]
            
            predictions.append({
                "rider_id": rider["rider_id"],
                "rider": rider["name"],
                "team": rider["team"],
                "nationality": rider["nationality"],
                "specialist": rider["specialist"],
                "win_probability": float(win_prob),
                "predicted_gc_position": int(gc_pos),
                "predicted_time_gap_seconds": float(time_gap),
                "is_points_contender": int(self.models["points_jersey"].predict(features.reshape(1, -1))[0]),
                "is_mountains_contender": int(self.models["mountains_jersey"].predict(features.reshape(1, -1))[0]),
            })
        
        # Sort by win probability
        predictions_df = pd.DataFrame(predictions)
        predictions_df = predictions_df.sort_values("win_probability", ascending=False)
        
        return predictions_df
    
    def _create_rider_stage_features(self, rider: pd.Series, stage_data: pd.DataFrame) -> np.ndarray:
        """Create feature vector for a rider on a specific stage."""
        # Get stage features
        stage_features = {
            "distance_km": stage_data.get("distance_km", 150),
            "elevation_m": stage_data.get("elevation_m", 1000),
            "is_mountain_stage": int(stage_data.get("is_mountain_stage", False)),
            "is_tt": int(stage_data.get("is_tt", False)),
            "num_climbs_hc": stage_data.get("num_climbs_hc", 0),
            "num_climbs_cat1": stage_data.get("num_climbs_cat1", 0),
            "num_climbs_cat2": stage_data.get("num_climbs_cat2", 0),
        }
        
        # Get rider features
        rider_features = {
            "age": rider.get("age", 28),
            "height_m": rider.get("height_m", 1.75),
            "weight_kg": rider.get("weight_kg", 68),
            "uci_points": rider.get("uci_points", 2000),
            "2026_wins": rider.get("2026_wins", 2),
            "grand_tour_wins": rider.get("grand_tour_wins", 0),
            "bmi": rider.get("weight_kg", 68) / (rider.get("height_m", 1.75) ** 2),
        }
        
        # Get team features
        team_budgets = {
            "Team Visma | Lease a Bike": 45,
            "UAE Team Emirates": 50,
            "Soudal Quick-Step": 40,
            "Alpecin-Deceuninck": 25,
            "Lidl-Trek": 35,
            "Intermarché-Wanty": 20,
            "Bora-Hansgrohe": 30,
            "INEOS Grenadiers": 45,
        }
        team_features = {
            "team_budget_million": team_budgets.get(rider.get("team", ""), 30)
        }
        
        # Combine all features
        all_features = {**rider_features, **stage_features, **team_features}
        
        # Add encoded features
        all_features["specialist_encoded"] = self.specialist_order.get(rider.get("specialist", "All-Rounder"), 2)
        all_features["stage_type_encoded"] = self.stage_type_order.get(stage_data.get("stage_type", "Flat"), 0)
        
        # Create feature array in correct order
        feature_order = (
            self.rider_features + 
            self.stage_features + 
            self.team_features + 
            ["specialist_encoded", "stage_type_encoded"]
        )
        
        return np.array([all_features.get(f, 0) for f in feature_order])
    
    def predict_all_stages(self, stages: pd.DataFrame, riders: pd.DataFrame) -> Dict[int, pd.DataFrame]:
        """Predict winners for all stages."""
        predictions = {}
        
        for _, stage in stages.iterrows():
            stage_num = stage["stage"]
            predictions[stage_num] = self.predict_stage_winners(stage, riders)
        
        return predictions


async def main():
    parser = argparse.ArgumentParser(description="Train and run TDF prediction models")
    parser.add_argument("--train", action="store_true", help="Train models")
    parser.add_argument("--predict", action="store_true", help="Generate predictions")
    parser.add_argument("--predict-all", action="store_true", help="Generate predictions for all stages")
    parser.add_argument("--stage", type=int, default=None, help="Specific stage to predict")
    parser.add_argument("--data-dir", type=str, default="data", help="Data directory")
    parser.add_argument("--output", type=str, default="data/predictions", help="Output directory for predictions")
    
    args = parser.parse_args()
    
    predictor = TDFPredictor(data_dir=Path(args.data_dir))
    
    if args.train:
        # Load data
        data = predictor.load_data()
        
        # Prepare training data
        df, feature_info = predictor.prepare_training_data(data)
        
        # Train models
        results = predictor.train_models(df, feature_info)
        
        # Save models
        predictor.save_models()
        
        # Save training results
        with open("training_results.json", "w") as f:
            json.dump(results, f, indent=2)
        
        print("\nTraining complete! Models saved to models/")
        print(f"Results saved to training_results.json")
    
    if args.predict or args.predict_all:
        # Load models
        predictor.load_models()
        
        # Load data
        data = predictor.load_data()
        stages = data.get("stages", pd.DataFrame())
        riders = data.get("riders", pd.DataFrame())
        
        if stages.empty or riders.empty:
            print("Error: No stage or rider data found. Run fetch script first.")
            return
        
        output_dir = Path(args.output)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        if args.predict_all:
            # Predict for all stages
            predictions = predictor.predict_all_stages(stages, riders)
            
            # Save each stage's predictions
            for stage_num, pred_df in predictions.items():
                pred_df.to_parquet(output_dir / f"stage_{stage_num}_predictions.parquet")
            
            # Save combined predictions
            all_preds = pd.concat(predictions.values(), keys=predictions.keys())
            all_preds.index.names = ["stage", "rank"]
            all_preds.to_parquet(output_dir / "all_stage_predictions.parquet")
            
            print(f"Generated predictions for {len(predictions)} stages")
            print(f"Saved to {output_dir}")
        
        elif args.stage:
            # Predict for specific stage
            stage_data = stages[stages["stage"] == args.stage]
            if stage_data.empty:
                print(f"Error: Stage {args.stage} not found")
                return
            
            predictions = predictor.predict_stage_winners(stage_data.iloc[0], riders)
            predictions.to_parquet(output_dir / f"stage_{args.stage}_predictions.parquet")
            
            print(f"Generated predictions for Stage {args.stage}")
            print(predictions.head(10))
    
    if not (args.train or args.predict or args.predict_all):
        parser.print_help()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
