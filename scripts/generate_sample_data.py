#!/usr/bin/env python3
"""
Generate sample TDF data for testing the dashboard.

This script creates mock Parquet files that match the expected schema
so the dashboard can be tested without real API access.

Usage:
    python scripts/generate_sample_data.py
"""

import json
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import numpy as np


def generate_historical_results():
    """Generate mock historical results (2020-2025)."""
    data = []
    
    top_riders = [
        "Tadej Pogacar", "Jonas Vingegaard", "Primoz Roglic", "Geraint Thomas", 
        "Adam Yates", "Richard Virenque", "Chris Froome", "Nairo Quintana",
        "Mikel Landa", "Enric Mas", "Wout van Aert", "Mathieu van der Poel",
        "Peter Sagan", "Mark Cavendish", "Jasper Philipsen", "Dylan Groenewegen",
        "Remco Evenepoel", "Tom Pidcock", "Ben O'Connor", "Sepp Kuss"
    ]
    
    teams = [
        "UAE Team Emirates", "Team Visma | Lease a Bike", "Jumbo-Visma",
        "INEOS Grenadiers", "Bora-Hansgrohe", "Soudal Quick-Step",
        "Alpecin-Deceuninck", "Lidl-Trek", "Intermarché-Wanty",
        "Bahrain Victorious", "Movistar Team", "Cofidis"
    ]
    
    nationalities = ["SLO", "DEN", "NED", "GBR", "ESP", "COL", "FRA", "BEL", "AUS", "USA"]
    
    for year in range(2020, 2026):
        for stage in range(1, 22):
            # Determine stage type
            if stage == 1:
                stage_type = "Prologue"
                distance = 8.0
                elevation = 50
            elif stage == 20:
                stage_type = "Individual Time Trial"
                distance = 34.0
                elevation = 200
            elif stage in [5, 10, 15, 17]:
                stage_type = "Mountain"
                distance = 150 + stage * 2
                elevation = 3000 + stage * 100
            elif stage in [2, 4, 7, 12, 18]:
                stage_type = "Hilly"
                distance = 180 + stage * 1.5
                elevation = 1500 + stage * 50
            else:
                stage_type = "Flat"
                distance = 180 + stage * 1.5
                elevation = 500 + stage * 20
            
            # Generate results for this stage
            np.random.seed(year * 100 + stage)
            shuffled_riders = np.random.permutation(top_riders)[:15]
            
            for position, rider in enumerate(shuffled_riders[:10], 1):
                team = np.random.choice(teams)
                nationality = np.random.choice(nationalities)
                
                # Generate realistic time gaps
                if position == 1:
                    time_gap = "0"
                    time = f"{3 + stage * 0.1:.1f}:{stage * 2:02d}:{stage * 3:02d}"
                else:
                    gap_seconds = int(np.random.exponential(30) * position)
                    gap_minutes = gap_seconds // 60
                    gap_seconds_remainder = gap_seconds % 60
                    time_gap = f"+{gap_minutes}:{gap_seconds_remainder:02d}"
                    time = f"{3 + stage * 0.1 + gap_minutes:.1f}:{(stage * 2 + gap_minutes) % 60:02d}:{stage * 3:02d}"
                
                data.append({
                    "year": year,
                    "stage": stage,
                    "position": position,
                    "rider": rider,
                    "team": team,
                    "nationality": nationality,
                    "time": time,
                    "gap": time_gap,
                    "stage_type": stage_type,
                    "distance_km": distance,
                    "elevation_m": elevation,
                })
    
    df = pd.DataFrame(data)
    return df


def generate_gc_standings():
    """Generate mock GC standings for 2026."""
    data = [
        {"position": 1, "rider_id": "vingegaard_jonas", "rider": "Jonas Vingegaard", 
         "team": "Team Visma | Lease a Bike", "time": "79:16:38", "gap": "0", 
         "age": 27, "nationality": "DEN", "specialist": "Climber"},
        {"position": 2, "rider_id": "pogacar_tadej", "rider": "Tadej Pogacar",
         "team": "UAE Team Emirates", "time": "79:18:26", "gap": "+1:48", 
         "age": 25, "nationality": "SLO", "specialist": "Climber"},
        {"position": 3, "rider_id": "yates_adam", "rider": "Adam Yates",
         "team": "UAE Team Emirates", "time": "79:18:42", "gap": "+2:04", 
         "age": 31, "nationality": "GBR", "specialist": "Climber"},
        {"position": 4, "rider_id": "van_aert_wout", "rider": "Wout van Aert",
         "team": "Team Visma | Lease a Bike", "time": "79:20:15", "gap": "+3:37", 
         "age": 29, "nationality": "BEL", "specialist": "All-Rounder"},
        {"position": 5, "rider_id": "evenepoel_remco", "rider": "Remco Evenepoel",
         "team": "Soudal Quick-Step", "time": "79:21:02", "gap": "+4:24", 
         "age": 24, "nationality": "BEL", "specialist": "Climber"},
        {"position": 6, "rider_id": "van_der_poel_mathieu", "rider": "Mathieu van der Poel",
         "team": "Alpecin-Deceuninck", "time": "79:22:15", "gap": "+5:37", 
         "age": 29, "nationality": "NED", "specialist": "Puncheur"},
        {"position": 7, "rider_id": "girmay_biniam", "rider": "Biniam Girmay",
         "team": "Intermarché-Wanty", "time": "79:25:00", "gap": "+8:22", 
         "age": 24, "nationality": "ERI", "specialist": "Sprinter"},
        {"position": 8, "rider_id": "stuyven_jasper", "rider": "Jasper Stuyven",
         "team": "Lidl-Trek", "time": "79:26:30", "gap": "+9:52", 
         "age": 32, "nationality": "BEL", "specialist": "Sprinter"},
        {"position": 9, "rider_id": "meeus_jordi", "rider": "Jordi Meeus",
         "team": "Bora-Hansgrohe", "time": "79:27:15", "gap": "+10:37", 
         "age": 26, "nationality": "BEL", "specialist": "Sprinter"},
        {"position": 10, "rider_id": "mihkels_madis", "rider": "Madis Mihkels",
         "team": "Intermarché-Wanty", "time": "79:28:00", "gap": "+11:22", 
         "age": 30, "nationality": "EST", "specialist": "Sprinter"},
    ]
    
    return pd.DataFrame(data)


def generate_stage_results():
    """Generate mock stage results for 2026."""
    data = []
    
    top_riders = [
        "Jonas Vingegaard", "Tadej Pogacar", "Adam Yates", "Wout van Aert", 
        "Remco Evenepoel", "Mathieu van der Poel", "Biniam Girmay", 
        "Jasper Stuyven", "Jordi Meeus", "Madis Mihkels",
        "Primoz Roglic", "Geraint Thomas", "Enric Mas", "Tom Pidcock",
        "Ben O'Connor", "Sepp Kuss", "Peter Sagan", "Mark Cavendish"
    ]
    
    teams = [
        "Team Visma | Lease a Bike", "UAE Team Emirates", "Soudal Quick-Step",
        "Alpecin-Deceuninck", "Lidl-Trek", "Intermarché-Wanty",
        "Bora-Hansgrohe", "INEOS Grenadiers"
    ]
    
    for stage in range(1, 22):
        # Determine stage type
        if stage == 1:
            stage_type = "Prologue"
            distance = 8.0
            elevation = 50
        elif stage == 20:
            stage_type = "Individual Time Trial"
            distance = 34.0
            elevation = 200
        elif stage in [5, 10, 15, 17]:
            stage_type = "Mountain"
            distance = 150 + stage * 2
            elevation = 3000 + stage * 100
        elif stage in [2, 4, 7, 12, 18]:
            stage_type = "Hilly"
            distance = 180 + stage * 1.5
            elevation = 1500 + stage * 50
        else:
            stage_type = "Flat"
            distance = 180 + stage * 1.5
            elevation = 500 + stage * 20
        
        date = (datetime(2026, 7, 5) + timedelta(days=stage-1)).strftime("%Y-%m-%d")
        
        # Generate results for this stage
        np.random.seed(stage * 42)
        shuffled_riders = np.random.permutation(top_riders)[:15]
        
        for position, rider in enumerate(shuffled_riders[:10], 1):
            team = np.random.choice(teams)
            
            # Generate realistic time gaps
            if position == 1:
                time_gap = "0"
                time = f"{3 + stage * 0.1:.1f}:{position * 2:02d}:{position * 3:02d}"
            else:
                gap_seconds = int(np.random.exponential(30) * position)
                gap_minutes = gap_seconds // 60
                gap_seconds_remainder = gap_seconds % 60
                time_gap = f"+{gap_minutes}:{gap_seconds_remainder:02d}"
                time = f"{3 + stage * 0.1 + gap_minutes:.1f}:{(position * 2 + gap_minutes) % 60:02d}:{position * 3:02d}"
            
            data.append({
                "stage": stage,
                "position": position,
                "rider": rider,
                "team": team,
                "time": time,
                "gap": time_gap,
                "date": date,
                "stage_type": stage_type,
                "distance_km": distance,
                "elevation_m": elevation,
            })
    
    return pd.DataFrame(data)


def generate_riders():
    """Generate mock rider information."""
    data = [
        ("Jonas Vingegaard", "Team Visma | Lease a Bike", "DEN", 27, 1.75, 62, "Climber", "GC Contender", 4500, 5, 3),
        ("Tadej Pogacar", "UAE Team Emirates", "SLO", 25, 1.76, 58, "Climber", "GC Contender", 4800, 8, 3),
        ("Adam Yates", "UAE Team Emirates", "GBR", 31, 1.74, 58, "Climber", "GC Contender", 3500, 3, 1),
        ("Wout van Aert", "Team Visma | Lease a Bike", "BEL", 29, 1.87, 78, "All-Rounder", "Classics Specialist", 4200, 10, 0),
        ("Remco Evenepoel", "Soudal Quick-Step", "BEL", 24, 1.72, 60, "Climber", "GC Contender", 4000, 6, 1),
        ("Mathieu van der Poel", "Alpecin-Deceuninck", "NED", 29, 1.81, 73, "Puncheur", "Classics Specialist", 3800, 7, 0),
        ("Jasper Stuyven", "Lidl-Trek", "BEL", 32, 1.84, 70, "Sprinter", "Lead-out", 2500, 2, 0),
        ("Madis Mihkels", "Intermarché-Wanty", "EST", 30, 1.80, 72, "Sprinter", "Lead-out", 2200, 1, 0),
        ("Biniam Girmay", "Intermarché-Wanty", "ERI", 24, 1.78, 65, "Sprinter", "Fast Finisher", 3000, 4, 0),
        ("Jordi Meeus", "Bora-Hansgrohe", "BEL", 26, 1.82, 71, "Sprinter", "Fast Finisher", 2800, 3, 0),
        ("Primoz Roglic", "Bora-Hansgrohe", "SLO", 34, 1.77, 65, "Climber", "GC Contender", 4000, 4, 2),
        ("Geraint Thomas", "INEOS Grenadiers", "GBR", 38, 1.83, 75, "All-Rounder", "GC Contender", 3500, 2, 1),
        ("Enric Mas", "Movistar Team", "ESP", 29, 1.75, 60, "Climber", "GC Contender", 3200, 3, 0),
        ("Tom Pidcock", "INEOS Grenadiers", "GBR", 24, 1.76, 66, "Puncheur", "All-Rounder", 3800, 5, 0),
        ("Ben O'Connor", "Decathlon AG2R La Mondiale", "AUS", 28, 1.78, 62, "Climber", "GC Contender", 2800, 2, 0),
        ("Sepp Kuss", "Team Visma | Lease a Bike", "USA", 29, 1.76, 60, "Climber", "Domestique", 2500, 1, 0),
        ("Peter Sagan", "TotalEnergies", "SVK", 34, 1.84, 73, "Sprinter", "Fast Finisher", 3500, 3, 0),
        ("Mark Cavendish", "Astana Qazaqstan Team", "GBR", 39, 1.75, 69, "Sprinter", "Fast Finisher", 2000, 1, 0),
        ("Dylan Groenewegen", "Jayco AlUla", "NED", 31, 1.80, 72, "Sprinter", "Fast Finisher", 2500, 2, 0),
        ("Jasper Philipsen", "Alpecin-Deceuninck", "BEL", 26, 1.74, 64, "Sprinter", "Fast Finisher", 3200, 5, 0),
    ]
    
    rows = []
    for i, (name, team, nationality, age, height, weight, specialist, role, uci_points, wins, gt_wins) in enumerate(data):
        rows.append({
            "rider_id": name.lower().replace(" ", "_"),
            "name": name,
            "team": team,
            "nationality": nationality,
            "age": age,
            "height_m": height,
            "weight_kg": weight,
            "specialist": specialist,
            "role": role,
            "uci_points": uci_points,
            "2026_wins": wins,
            "grand_tour_wins": gt_wins,
        })
    
    return pd.DataFrame(rows)


def generate_teams():
    """Generate mock team information."""
    data = [
        {"team_id": "visma", "name": "Team Visma | Lease a Bike", "country": "NED", 
         "sponsor": "Visma", "budget_million": 45, "riders": 8},
        {"team_id": "uae", "name": "UAE Team Emirates", "country": "UAE",
         "sponsor": "Emirates", "budget_million": 50, "riders": 8},
        {"team_id": "soudal", "name": "Soudal Quick-Step", "country": "BEL",
         "sponsor": "Soudal", "budget_million": 40, "riders": 8},
        {"team_id": "alpecin", "name": "Alpecin-Deceuninck", "country": "BEL",
         "sponsor": "Alpecin", "budget_million": 25, "riders": 8},
        {"team_id": "lidl", "name": "Lidl-Trek", "country": "USA",
         "sponsor": "Lidl", "budget_million": 35, "riders": 8},
        {"team_id": "intermarche", "name": "Intermarché-Wanty", "country": "FRA",
         "sponsor": "Intermarché", "budget_million": 20, "riders": 8},
        {"team_id": "bora", "name": "Bora-Hansgrohe", "country": "GER",
         "sponsor": "Bora", "budget_million": 30, "riders": 8},
        {"team_id": "ineos", "name": "INEOS Grenadiers", "country": "GBR",
         "sponsor": "INEOS", "budget_million": 45, "riders": 8},
    ]
    
    return pd.DataFrame(data)


def generate_stages():
    """Generate mock stage information for 2026."""
    data = []
    
    start_locations = [
        "Florence", "Bologna", "Turin", "Milan", "Saint-Vulbas", 
        "Dijon", "Nuits-Saint-Georges", "Gevingey", "Troyes", "Orléans",
        "Saint-Paul-Trois-Châteaux", "Martigues", "Carcassonne", "Saint-Girons", 
        "Saint-Lary-Soulan", "Pau", "Saint-Gaudens", "Bagnères-de-Luchon",
        "Lac de Payolle", "Nice", "Paris"
    ]
    
    end_locations = [
        "Florence", "Bologna", "Turin", "Milan", "Saint-Vulbas",
        "Dijon", "Nuits-Saint-Georges", "Gevingey", "Troyes", "Orléans",
        "Saint-Paul-Trois-Châteaux", "Martigues", "Carcassonne", "Saint-Girons",
        "Saint-Lary-Soulan Plates", "Pau", "Saint-Gaudens", "Bagnères-de-Luchon",
        "Hautacam", "Nice", "Paris (Champs-Élysées)"
    ]
    
    climbs_data = {
        5: [
            {"name": "Col de la Croix de Fer", "category": "HC", "km": 80, "length_km": 22.4, "avg_gradient": 6.9},
            {"name": "Col du Glandon", "category": "HC", "km": 120, "length_km": 21.7, "avg_gradient": 7.1}
        ],
        10: [
            {"name": "Mont Ventoux", "category": "HC", "km": 150, "length_km": 21.8, "avg_gradient": 7.4}
        ],
        15: [
            {"name": "Col du Tourmalet", "category": "HC", "km": 100, "length_km": 17.1, "avg_gradient": 7.3},
            {"name": "Aubisque", "category": "HC", "km": 130, "length_km": 16.6, "avg_gradient": 7.1}
        ],
        17: [
            {"name": "Col d'Aubisque", "category": "HC", "km": 80, "length_km": 16.6, "avg_gradient": 7.1},
            {"name": "Col du Soulor", "category": "1", "km": 120, "length_km": 14.7, "avg_gradient": 7.2}
        ],
    }
    
    for stage in range(1, 22):
        # Determine stage type
        if stage == 1:
            stage_type = "Prologue"
            distance = 8.0
            elevation = 50
        elif stage == 20:
            stage_type = "Individual Time Trial"
            distance = 34.0
            elevation = 200
        elif stage in [5, 10, 15, 17]:
            stage_type = "Mountain"
            distance = 150 + stage * 2
            elevation = 3000 + stage * 100
        elif stage in [2, 4, 7, 12, 18]:
            stage_type = "Hilly"
            distance = 180 + stage * 1.5
            elevation = 1500 + stage * 50
        else:
            stage_type = "Flat"
            distance = 180 + stage * 1.5
            elevation = 500 + stage * 20
        
        date = (datetime(2026, 7, 5) + timedelta(days=stage-1)).strftime("%Y-%m-%d")
        
        # Count climbs by category
        num_climbs_hc = len([c for c in climbs_data.get(stage, []) if c["category"] == "HC"])
        num_climbs_cat1 = len([c for c in climbs_data.get(stage, []) if c["category"] == "1"])
        num_climbs_cat2 = len([c for c in climbs_data.get(stage, []) if c["category"] == "2"])
        
        # Generate elevation profile (simplified)
        km_points = list(range(0, int(distance) + 1, 5))
        elevation_profile = []
        current_elev = 0
        for km in km_points:
            # Simple profile: climb in middle, descend at end for mountain stages
            if stage_type == "Mountain":
                if km < distance / 3:
                    current_elev += 20
                elif km < 2 * distance / 3:
                    current_elev += 40
                else:
                    current_elev -= 30
            elif stage_type == "Hilly":
                if km < distance / 2:
                    current_elev += 15
                else:
                    current_elev -= 10
            else:
                current_elev += 5
            elevation_profile.append(max(0, current_elev))
        
        data.append({
            "stage": stage,
            "date": date,
            "start_location": start_locations[stage - 1] if stage <= len(start_locations) else "Unknown",
            "end_location": end_locations[stage - 1] if stage <= len(end_locations) else "Unknown",
            "distance_km": distance,
            "elevation_m": elevation,
            "stage_type": stage_type,
            "climbs": climbs_data.get(stage, []),
            "sprint_points": [40, 80, 120] if distance > 120 else [40, 80],
            "is_mountain_stage": stage_type == "Mountain",
            "is_tt": stage_type in ["Prologue", "Individual Time Trial"],
            "num_climbs_hc": num_climbs_hc,
            "num_climbs_cat1": num_climbs_cat1,
            "num_climbs_cat2": num_climbs_cat2,
            "km": km_points,
            "elevation": elevation_profile[:len(km_points)],
        })
    
    return pd.DataFrame(data)


def generate_predictions(stages_df, riders_df):
    """Generate mock ML predictions."""
    all_predictions = []
    
    for _, stage in stages_df.iterrows():
        stage_num = stage["stage"]
        stage_type = stage["stage_type"]
        
        # Generate predictions for each rider
        for _, rider in riders_df.iterrows():
            # Base probability based on specialist type matching stage type
            specialist = rider["specialist"]
            
            # Calculate base probability
            if stage_type == "Mountain":
                if specialist == "Climber":
                    base_prob = 0.8
                elif specialist == "All-Rounder":
                    base_prob = 0.6
                elif specialist == "Puncheur":
                    base_prob = 0.5
                else:
                    base_prob = 0.1
            elif stage_type == "Flat":
                if specialist == "Sprinter":
                    base_prob = 0.8
                elif specialist == "Fast Finisher":
                    base_prob = 0.7
                elif specialist == "All-Rounder":
                    base_prob = 0.5
                else:
                    base_prob = 0.1
            elif stage_type in ["Prologue", "Individual Time Trial"]:
                if specialist == "All-Rounder":
                    base_prob = 0.7
                elif specialist == "Climber":
                    base_prob = 0.6
                else:
                    base_prob = 0.2
            else:  # Hilly
                if specialist == "Puncheur":
                    base_prob = 0.7
                elif specialist == "All-Rounder":
                    base_prob = 0.6
                elif specialist == "Climber":
                    base_prob = 0.5
                else:
                    base_prob = 0.2
            
            # Adjust based on rider quality (UCI points)
            uci_factor = min(1.0, rider["uci_points"] / 5000)
            
            # Adjust based on team budget
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
            team_budget = team_budgets.get(rider["team"], 30)
            budget_factor = team_budget / 50
            
            # Final probability
            win_prob = base_prob * uci_factor * budget_factor
            
            # Add some randomness
            np.random.seed(stage_num * 100 + hash(rider["rider_id"]) % 100)
            win_prob = win_prob * (0.8 + 0.4 * np.random.random())
            win_prob = min(0.95, max(0.01, win_prob))
            
            # Predicted GC position (lower is better)
            if rider["specialist"] == "Climber":
                gc_pos = max(1, 10 - rider["uci_points"] // 500)
            else:
                gc_pos = max(5, 20 - rider["uci_points"] // 300)
            
            # Predicted time gap
            if win_prob > 0.5:
                time_gap = np.random.exponential(30)
            else:
                time_gap = np.random.exponential(120)
            
            # Jersey contenders
            is_points = 1 if specialist in ["Sprinter", "Fast Finisher"] else 0
            is_mountains = 1 if specialist == "Climber" else 0
            
            all_predictions.append({
                "stage": stage_num,
                "rider_id": rider["rider_id"],
                "rider": rider["name"],
                "team": rider["team"],
                "nationality": rider["nationality"],
                "specialist": rider["specialist"],
                "win_probability": float(win_prob),
                "predicted_gc_position": int(gc_pos),
                "predicted_time_gap_seconds": float(time_gap),
                "is_points_contender": int(is_points),
                "is_mountains_contender": int(is_mountains),
                "stage_type": stage_type,
                "distance_km": stage["distance_km"],
                "elevation_m": stage["elevation_m"],
            })
    
    return pd.DataFrame(all_predictions)


def generate_model_performance():
    """Generate mock model performance metrics."""
    data = [
        {"model_name": "stage_winner", "model_type": "Classification", "target_variable": "won_stage", 
         "algorithm": "RandomForestClassifier", "accuracy": 0.85, "precision": 0.82, 
         "recall": 0.84, "f1_score": 0.83, "mae": None, "rmse": None, "r2_score": None},
        {"model_name": "gc_position", "model_type": "Regression", "target_variable": "gc_position",
         "algorithm": "GradientBoostingRegressor", "accuracy": None, "precision": None,
         "recall": None, "f1_score": None, "mae": 1.5, "rmse": 2.1, "r2_score": 0.88},
        {"model_name": "time_gap", "model_type": "Regression", "target_variable": "time_gap_seconds",
         "algorithm": "RandomForestRegressor", "accuracy": None, "precision": None,
         "recall": None, "f1_score": None, "mae": 30.5, "rmse": 45.2, "r2_score": 0.85},
        {"model_name": "points_jersey", "model_type": "Classification", "target_variable": "is_points_contender",
         "algorithm": "RandomForestClassifier", "accuracy": 0.88, "precision": 0.87,
         "recall": 0.89, "f1_score": 0.88, "mae": None, "rmse": None, "r2_score": None},
        {"model_name": "mountains_jersey", "model_type": "Classification", "target_variable": "is_mountains_contender",
         "algorithm": "RandomForestClassifier", "accuracy": 0.90, "precision": 0.89,
         "recall": 0.91, "f1_score": 0.90, "mae": None, "rmse": None, "r2_score": None},
    ]
    return pd.DataFrame(data)


def generate_feature_importance():
    """Generate mock feature importance data."""
    data = []
    features = [
        ("uci_points", 0.18),
        ("specialist_encoded", 0.15),
        ("age", 0.12),
        ("stage_type_encoded", 0.10),
        ("elevation_m", 0.08),
        ("distance_km", 0.07),
        ("team_budget_million", 0.06),
        ("2026_wins", 0.05),
        ("grand_tour_wins", 0.05),
        ("bmi", 0.04),
        ("height_m", 0.03),
        ("weight_kg", 0.03),
        ("is_mountain_stage", 0.02),
        ("is_tt", 0.01),
        ("num_climbs_hc", 0.01),
    ]
    
    for rank, (feature, importance) in enumerate(features, 1):
        data.append({
            "model_name": "stage_winner",
            "feature": feature,
            "importance": importance,
            "rank": rank,
        })
    
    return pd.DataFrame(data)


def generate_metadata():
    """Generate metadata file."""
    return {
        "last_refreshed": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "data_sources": ["ProCyclingStats", "Cycling Archives"],
        "refresh_interval": "daily",
        "next_refresh": (datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%dT08:00:00Z"),
        "note": "Sample data for testing - replace with real API calls"
    }


def main():
    """Generate all sample data files."""
    print("Generating sample data files...")
    
    # Create directories
    Path("data/historical").mkdir(parents=True, exist_ok=True)
    Path("data/live").mkdir(parents=True, exist_ok=True)
    Path("data/predictions").mkdir(parents=True, exist_ok=True)
    
    # Generate data
    print("  Generating historical results...")
    historical = generate_historical_results()
    historical.to_parquet("data/historical/results.parquet")
    
    print("  Generating GC standings...")
    gc_standings = generate_gc_standings()
    gc_standings.to_parquet("data/live/gc_standings.parquet")
    
    print("  Generating stage results...")
    stage_results = generate_stage_results()
    stage_results.to_parquet("data/live/stage_results.parquet")
    
    print("  Generating riders...")
    riders = generate_riders()
    riders.to_parquet("data/live/riders.parquet")
    
    print("  Generating teams...")
    teams = generate_teams()
    teams.to_parquet("data/live/teams.parquet")
    
    print("  Generating stages...")
    stages = generate_stages()
    stages.to_parquet("data/live/stages.parquet")
    
    print("  Generating predictions...")
    predictions = generate_predictions(stages, riders)
    predictions.to_parquet("data/predictions/all_stage_predictions.parquet")
    
    # Generate per-stage predictions
    for stage_num in range(1, 22):
        stage_preds = predictions[predictions["stage"] == stage_num].copy()
        stage_preds = stage_preds.sort_values("win_probability", ascending=False)
        stage_preds.to_parquet(f"data/predictions/stage_{stage_num}_predictions.parquet")
    
    print("  Generating model performance...")
    model_perf = generate_model_performance()
    model_perf.to_parquet("data/model_performance.parquet")
    
    print("  Generating feature importance...")
    feature_imp = generate_feature_importance()
    feature_imp.to_parquet("data/feature_importance.parquet")
    
    print("  Generating metadata...")
    metadata = generate_metadata()
    with open("data/metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)
    
    # Generate race overview
    race_overview = pd.DataFrame([{
        "total_distance_km": stages["distance_km"].sum(),
        "total_elevation_m": stages["elevation_m"].sum(),
        "num_stages": len(stages),
        "num_riders": len(riders),
    }])
    race_overview.to_parquet("data/race_overview.parquet")
    
    print("\n✓ All sample data files generated!")
    print(f"\nGenerated files:")
    print(f"  - data/historical/results.parquet ({len(historical)} rows)")
    print(f"  - data/live/gc_standings.parquet ({len(gc_standings)} rows)")
    print(f"  - data/live/stage_results.parquet ({len(stage_results)} rows)")
    print(f"  - data/live/riders.parquet ({len(riders)} rows)")
    print(f"  - data/live/teams.parquet ({len(teams)} rows)")
    print(f"  - data/live/stages.parquet ({len(stages)} rows)")
    print(f"  - data/predictions/all_stage_predictions.parquet ({len(predictions)} rows)")
    print(f"  - data/predictions/stage_*_predictions.parquet (21 files)")
    print(f"  - data/model_performance.parquet ({len(model_perf)} rows)")
    print(f"  - data/feature_importance.parquet ({len(feature_imp)} rows)")
    print(f"  - data/metadata.json")
    print(f"  - data/race_overview.parquet (1 row)")


if __name__ == "__main__":
    main()
