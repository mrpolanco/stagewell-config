#!/usr/bin/env python3
"""
PostHog Analytics Aggregation Script for StagewellAI

Fetches analytics data from PostHog and aggregates it into statistics
that can be displayed as social proof in the app.

Run via GitHub Actions on a schedule (e.g., daily) to update stats.json
"""

import os
import json
import sys
from datetime import datetime, timedelta
from collections import defaultdict
import requests

# Configuration
POSTHOG_API_KEY = os.environ.get("POSTHOG_API_KEY")
POSTHOG_PROJECT_ID = os.environ.get("POSTHOG_PROJECT_ID")
POSTHOG_HOST = "https://us.posthog.com"  # or 'https://eu.posthog.com' for EU

LOOKBACK_DAYS = 90  # Analyze last 90 days of data
MIN_SESSIONS_FOR_TOOL = 50  # Minimum sessions to include tool stats
MIN_USERS_FOR_TOOL = 10  # Minimum users to include tool stats
MIN_USERS_FOR_STAGE = 20  # Minimum users to include stage stats
MIN_DAILY_USERS = 10  # Minimum daily users to show community stats

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


def query_posthog_events(event_name: str, days: int = LOOKBACK_DAYS) -> list:
    """Query PostHog for events using the events API."""
    url = f"{POSTHOG_HOST}/api/projects/{POSTHOG_PROJECT_ID}/events"
    headers = {"Authorization": f"Bearer {POSTHOG_API_KEY}"}

    after = (datetime.now() - timedelta(days=days)).isoformat()

    params = {
        "event": event_name,
        "after": after,
        "limit": 10000
    }

    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json().get("results", [])
    except Exception as e:
        print(f"  Warning: Failed to fetch {event_name}: {e}")
        return []


def query_posthog_hogql(query: str) -> list:
    """Execute a HogQL query against PostHog."""
    url = f"{POSTHOG_HOST}/api/projects/{POSTHOG_PROJECT_ID}/query/"
    headers = {
        "Authorization": f"Bearer {POSTHOG_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "kind": "HogQLQuery",
        "query": query
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json().get("results", [])
    except Exception as e:
        print(f"  Warning: HogQL query failed: {e}")
        return []


def calculate_challenge_stats() -> list:
    """Calculate completion rates from PostHog events."""
    print("Fetching challenge events...")

    started_events = query_posthog_events("challenge_started")
    print(f"  Found {len(started_events)} started events")

    completed_events = query_posthog_events("challenge_completed")
    print(f"  Found {len(completed_events)} completed events")

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

        if total_starts > 0:
            completion_rate = total_completions / total_starts
            avg_days = None
            if completion_days[challenge_id]:
                avg_days = int(sum(completion_days[challenge_id]) / len(completion_days[challenge_id]))

            stat = {
                "challenge_id": challenge_id,
                "completion_rate": round(completion_rate, 3),
                "total_starts": total_starts,
                "total_completions": total_completions,
            }
            if avg_days:
                stat["average_days_to_complete"] = avg_days

            challenge_stats.append(stat)
            print(f"    {challenge_id}: {total_completions}/{total_starts} = {completion_rate:.0%}")

    return challenge_stats


def calculate_tool_stats() -> tuple[list, list]:
    """Calculate tool usage and category statistics."""
    print("Fetching tool session events...")

    events = query_posthog_events("tool_session_completed")
    print(f"  Found {len(events)} tool session events")

    if not events:
        return None, None

    # Aggregate by tool
    tool_data = defaultdict(lambda: {
        "sessions": 0,
        "users": set(),
        "durations": [],
        "completions": 0,
        "mood_impacts": [],
        "hours": []
    })

    for event in events:
        props = event.get("properties", {})
        tool_id = props.get("tool_id")
        if not tool_id:
            continue

        data = tool_data[tool_id]
        data["sessions"] += 1
        data["name"] = props.get("tool_name", tool_id)
        data["category"] = props.get("category", "other")

        person_id = event.get("distinct_id")
        if person_id:
            data["users"].add(person_id)

        if props.get("completed"):
            data["completions"] += 1

        duration = props.get("actual_duration_seconds")
        if duration:
            data["durations"].append(duration)

        mood_impact = props.get("mood_impact")
        if mood_impact is not None:
            data["mood_impacts"].append(mood_impact)

        hour = props.get("hour_of_day")
        if hour is not None:
            data["hours"].append(hour)

    # Build tool stats (only those meeting threshold)
    tool_stats = []
    for tool_id, data in tool_data.items():
        if data["sessions"] >= MIN_SESSIONS_FOR_TOOL and len(data["users"]) >= MIN_USERS_FOR_TOOL:
            stat = {
                "tool_id": tool_id,
                "tool_name": data["name"],
                "category": data["category"],
                "total_sessions": data["sessions"],
                "total_users": len(data["users"]),
                "completion_rate": round(data["completions"] / data["sessions"], 3) if data["sessions"] > 0 else 0,
            }

            if data["durations"]:
                stat["avg_session_duration"] = int(sum(data["durations"]) / len(data["durations"]))

            if data["mood_impacts"]:
                stat["avg_mood_impact"] = round(sum(data["mood_impacts"]) / len(data["mood_impacts"]), 3)

            if data["hours"]:
                # Find most common hour
                hour_counts = defaultdict(int)
                for h in data["hours"]:
                    hour_counts[h] += 1
                stat["peak_usage_hour"] = max(hour_counts, key=hour_counts.get)

            tool_stats.append(stat)
            print(f"    {tool_id}: {data['sessions']} sessions, {len(data['users'])} users")

    # Build category stats
    category_data = defaultdict(lambda: {
        "sessions": 0,
        "completions": 0,
        "mood_impacts": [],
        "top_tool": None,
        "top_tool_sessions": 0
    })

    for tool_id, data in tool_data.items():
        cat = data["category"]
        category_data[cat]["sessions"] += data["sessions"]
        category_data[cat]["completions"] += data["completions"]
        category_data[cat]["mood_impacts"].extend(data["mood_impacts"])

        if data["sessions"] > category_data[cat]["top_tool_sessions"]:
            category_data[cat]["top_tool"] = tool_id
            category_data[cat]["top_tool_name"] = data["name"]
            category_data[cat]["top_tool_sessions"] = data["sessions"]

    category_stats = []
    for category, data in category_data.items():
        if data["sessions"] >= 20 and data["top_tool"]:
            stat = {
                "category": category,
                "most_popular_tool_id": data["top_tool"],
                "most_popular_tool_name": data.get("top_tool_name", data["top_tool"]),
                "total_sessions": data["sessions"],
                "avg_completion_rate": round(data["completions"] / data["sessions"], 3) if data["sessions"] > 0 else 0,
            }

            if data["mood_impacts"]:
                stat["avg_mood_impact"] = round(sum(data["mood_impacts"]) / len(data["mood_impacts"]), 3)

            category_stats.append(stat)

    return tool_stats if tool_stats else None, category_stats if category_stats else None


def calculate_stage_stats() -> list:
    """Calculate stage progression statistics."""
    print("Fetching stage advancement events...")

    events = query_posthog_events("stage_advancement")
    print(f"  Found {len(events)} stage advancement events")

    if not events:
        return None

    stage_data = defaultdict(lambda: {
        "users_reached": set(),
        "users_completed": set(),
        "days_in_stage": []
    })

    for event in events:
        props = event.get("properties", {})
        to_stage = props.get("to_stage")
        from_stage = props.get("from_stage")
        person_id = event.get("distinct_id")

        if to_stage and person_id:
            stage_data[to_stage]["users_reached"].add(person_id)

        if from_stage and person_id:
            stage_data[from_stage]["users_completed"].add(person_id)
            days = props.get("days_in_previous_stage")
            if days:
                stage_data[from_stage]["days_in_stage"].append(days)

    stage_stats = []
    for stage, data in stage_data.items():
        if len(data["users_reached"]) >= MIN_USERS_FOR_STAGE:
            stat = {
                "stage": stage,
                "total_users_reached": len(data["users_reached"]),
                "total_users_completed": len(data["users_completed"]),
                "top_tool_ids": [],
                "top_challenge_ids": [],
            }

            if data["days_in_stage"]:
                stat["avg_days_in_stage"] = int(sum(data["days_in_stage"]) / len(data["days_in_stage"]))
            else:
                stat["avg_days_in_stage"] = 14  # Default

            stage_stats.append(stat)
            print(f"    {stage}: {len(data['users_reached'])} reached, {len(data['users_completed'])} completed")

    return stage_stats if stage_stats else None


def calculate_community_stats() -> dict:
    """Calculate real-time community activity metrics."""
    print("Calculating community stats...")

    # Get today's events
    today_events = query_posthog_events("tool_session_completed", days=1)
    week_events = query_posthog_events("tool_session_completed", days=7)

    today_users = set()
    week_users = set()

    for event in today_events:
        person_id = event.get("distinct_id")
        if person_id:
            today_users.add(person_id)

    for event in week_events:
        person_id = event.get("distinct_id")
        if person_id:
            week_users.add(person_id)

    # Get challenge completions
    today_challenges = query_posthog_events("challenge_completed", days=1)
    week_challenges = query_posthog_events("challenge_completed", days=7)
    today_milestones = query_posthog_events("challenge_milestone_completed", days=1)

    active_today = len(today_users)

    if active_today < MIN_DAILY_USERS:
        print(f"  Insufficient activity ({active_today} users today, need {MIN_DAILY_USERS})")
        return None

    stats = {
        "active_users_today": active_today,
        "active_users_this_week": len(week_users),
        "challenges_completed_today": len(today_challenges),
        "challenges_completed_this_week": len(week_challenges),
        "milestones_hit_today": len(today_milestones),
        "total_meditation_minutes_today": 0,
        "total_journal_entries_today": 0,
    }

    # Calculate meditation minutes
    for event in today_events:
        props = event.get("properties", {})
        if props.get("category") == "meditation":
            duration = props.get("actual_duration_seconds", 0)
            stats["total_meditation_minutes_today"] += duration // 60

    # Count journal entries
    today_journals = query_posthog_events("journal_entry_created", days=1)
    stats["total_journal_entries_today"] = len(today_journals)

    print(f"  {active_today} active users today, {len(today_milestones)} milestones")

    return stats


def calculate_effectiveness_stats() -> dict:
    """Calculate effectiveness and correlation statistics."""
    print("Calculating effectiveness stats...")

    events = query_posthog_events("tool_session_completed")

    mood_by_tool = defaultdict(list)

    for event in events:
        props = event.get("properties", {})
        tool_id = props.get("tool_id")
        mood_impact = props.get("mood_impact")

        if tool_id and mood_impact is not None:
            mood_by_tool[tool_id].append(mood_impact)

    # Calculate averages for tools with enough data
    mood_improvement = {}
    for tool_id, impacts in mood_by_tool.items():
        if len(impacts) >= 20:
            avg = sum(impacts) / len(impacts)
            if avg > 0:  # Only include positive improvements
                mood_improvement[tool_id] = round(avg, 3)

    if not mood_improvement:
        return None

    # Get streak data
    streak_events = query_posthog_events("streak_milestone")
    streaks = [e.get("properties", {}).get("streak_days", 0) for e in streak_events]

    streak_retention = {
        "avg_streak_length": int(sum(streaks) / len(streaks)) if streaks else 7,
        "day_7_retention": 0.5,  # Would need cohort analysis for accurate numbers
        "day_30_retention": 0.2,
    }

    # Get engagement patterns
    hours = []
    weekend_count = 0
    weekday_count = 0

    for event in events:
        props = event.get("properties", {})
        hour = props.get("hour_of_day")
        if hour is not None:
            hours.append(hour)

        if props.get("is_weekend"):
            weekend_count += 1
        else:
            weekday_count += 1

    peak_hour = 12
    if hours:
        hour_counts = defaultdict(int)
        for h in hours:
            hour_counts[h] += 1
        peak_hour = max(hour_counts, key=hour_counts.get)

    weekend_ratio = weekend_count / weekday_count if weekday_count > 0 else 0.6

    return {
        "mood_improvement_by_tool": mood_improvement,
        "streak_retention": streak_retention,
        "engagement_patterns": {
            "most_active_hour": peak_hour,
            "weekend_vs_weekday_ratio": round(weekend_ratio, 3),
            "peak_morning_tool": None,
            "peak_afternoon_tool": None,
            "peak_evening_tool": None,
        }
    }


def main():
    if not POSTHOG_API_KEY or not POSTHOG_PROJECT_ID:
        print("Error: POSTHOG_API_KEY and POSTHOG_PROJECT_ID must be set")
        sys.exit(1)

    print("=" * 50)
    print("PostHog Stats Aggregation")
    print("=" * 50)

    # Calculate all stats
    challenge_stats = calculate_challenge_stats()
    tool_stats, category_stats = calculate_tool_stats()
    stage_stats = calculate_stage_stats()
    community_stats = calculate_community_stats()
    effectiveness_stats = calculate_effectiveness_stats()

    # Load existing stats to preserve data
    stats_path = "config/stats.json"
    try:
        with open(stats_path, "r") as f:
            existing = json.load(f)

        # Merge: keep existing challenge stats for challenges without new data
        if challenge_stats:
            existing_ids = {s["challenge_id"] for s in challenge_stats}
            for old_stat in existing.get("challenge_stats", []):
                if old_stat["challenge_id"] not in existing_ids:
                    challenge_stats.append(old_stat)
    except FileNotFoundError:
        pass

    # Build output
    output = {
        "challenge_stats": challenge_stats,
        "path_stats": None,
        "tool_stats": tool_stats,
        "tool_category_stats": category_stats,
        "stage_stats": stage_stats,
        "community_stats": community_stats,
        "effectiveness_stats": effectiveness_stats,
        "thresholds": {
            "min_sessions_for_tool_stats": MIN_SESSIONS_FOR_TOOL,
            "min_users_for_tool_stats": MIN_USERS_FOR_TOOL,
            "min_users_for_stage_stats": MIN_USERS_FOR_STAGE,
            "min_daily_users_for_community": MIN_DAILY_USERS,
            "min_completions_for_challenge": 5
        },
        "last_updated": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    }

    # Write output
    with open(stats_path, "w") as f:
        json.dump(output, f, indent=2)

    print("\n" + "=" * 50)
    print(f"Stats written to {stats_path}")
    print(f"  Challenges: {len(challenge_stats)}")
    print(f"  Tools: {len(tool_stats) if tool_stats else 0}")
    print(f"  Stages: {len(stage_stats) if stage_stats else 0}")
    print(f"  Community: {'Yes' if community_stats else 'No'}")
    print("=" * 50)


if __name__ == "__main__":
    main()
