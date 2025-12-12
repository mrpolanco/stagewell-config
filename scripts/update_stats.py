#!/usr/bin/env python3

"""
Fetches challenge analytics from PostHog and updates stats.json
"""

import os
import json
import requests
from datetime import datetime, timedelta
from collections import defaultdict

POSTHOG_API_KEY = os.environ.get("POSTHOG_API_KEY")
POSTHOG_PROJECT_ID = os.environ.get("POSTHOG_PROJECT_ID")
POSTHOG_HOST = "https://us.posthog.com"  # or 'https://eu.posthog.com' for EU

# Challenge IDs from ChallengeLibrary.swift
CHALLENGE_IDS = [
    "movement_7day",
    "morning_walks_30",
    "strength_training_8week",
    "stretching_14day",
    "steps_10k_21day",
    "sleep_schedule_14day",
    "evening_winddown_21",
    "power_naps_7day",
    "hydration_30day",
    "meal_prep_4week",
    "no_sugar_14day",
    "breathing_7day",
    "meditation_21day",
    "mindful_eating_14",
    "gratitude_30day",
    "gratitude_letters_7",
    "journal_streak_30",
    "morning_pages_14",
    "evening_reflection_21",
    "morning_routine_21",
    "evening_routine_14",
    "digital_detox_weekend",
]


def query_posthog(event_name: str) -> list:
    """Query PostHog for events"""
    url = f"{POSTHOG_HOST}/api/projects/{POSTHOG_PROJECT_ID}/events"
    headers = {"Authorization": f"Bearer {POSTHOG_API_KEY}"}

    # Get last 90 days of data
    after = (datetime.now() - timedelta(days=90)).isoformat()

    params = {"event": event_name, "after": after, "limit": 10000}

    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    return response.json().get("results", [])


def calculate_stats() -> dict:
    """Calculate completion rates from PostHog events"""

    # Fetch events
    print("Fetching challenge_started events...")
    started_events = query_posthog("challenge_started")
    print(f"  Found {len(started_events)} events")

    print("Fetching challenge_completed events...")
    completed_events = query_posthog("challenge_completed")
    print(f"  Found {len(completed_events)} events")

    # Aggregate by challenge_id
    starts = defaultdict(int)
    completions = defaultdict(int)
    completion_days = defaultdict(list)

    for event in started_events:
        challenge_id = event.get("properties", {}).get("challenge_id")
        if challenge_id:
            starts[challenge_id] += 1

    for event in completed_events:
        props = event.get("properties", {})
        challenge_id = props.get("challenge_id")
        if challenge_id:
            completions[challenge_id] += 1
            days = props.get("days_to_complete")
            if days:
                completion_days[challenge_id].append(days)

    # Build stats
    challenge_stats = []
    for challenge_id in CHALLENGE_IDS:
        total_starts = starts.get(challenge_id, 0)
        total_completions = completions.get(challenge_id, 0)

        # Only include if we have data, otherwise use defaults
        if total_starts > 0:
            completion_rate = total_completions / total_starts
            avg_days = None
            if completion_days[challenge_id]:
                avg_days = int(
                    sum(completion_days[challenge_id])
                    / len(completion_days[challenge_id])
                )

            stat = {
                "challenge_id": challenge_id,
                "completion_rate": round(completion_rate, 2),
                "total_starts": total_starts,
                "total_completions": total_completions,
            }
            if avg_days:
                stat["average_days_to_complete"] = avg_days

            challenge_stats.append(stat)
            print(
                f"  {challenge_id}: {total_completions}/{total_starts} = {completion_rate:.0%}"
            )

    return {
        "challenge_stats": challenge_stats,
        "path_stats": [],  # Add path stats similarly if needed
        "last_updated": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def main():
    if not POSTHOG_API_KEY or not POSTHOG_PROJECT_ID:
        print("Error: POSTHOG_API_KEY and POSTHOG_PROJECT_ID must be set")
        return


print("Calculating challenge stats from PostHog...")
stats = calculate_stats()

# Load existing stats to preserve challenges without new data
stats_path = "config/stats.json"
try:
    with open(stats_path, "r") as f:
        existing = json.load(f)

    # Merge: keep existing stats for challenges without new data
    existing_ids = {s["challenge_id"] for s in stats["challenge_stats"]}
    for old_stat in existing.get("challenge_stats", []):
        if old_stat["challenge_id"] not in existing_ids:
            stats["challenge_stats"].append(old_stat)

except FileNotFoundError:
    pass

# Write updated stats
with open(stats_path, "w") as f:
    json.dump(stats, f, indent=2)

print(f"\nUpdated {stats_path} with {len(stats['challenge_stats'])} challenges")

if __name__ == "__main__":
    main()
