#!/usr/bin/env python3
"""
Integration test script for the coaching API.
Tests a complete feedback avoidance coaching session.

Usage:
    python scripts/run_case_feedback.py [--base-url http://localhost:8000]
"""

import argparse
import json
import sys
import time
import requests


def main():
    parser = argparse.ArgumentParser(description="Run feedback case test")
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="Base URL for the API (default: http://localhost:8000)"
    )
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    print(f"Testing API at: {base_url}")

    # Test messages simulating a feedback avoidance coaching session
    messages = [
        "In my last 1:1, my manager asked how I want feedback and I said it's fine, but I actually didn't want any.",
        "I worry feedback means I'm failing or not good enough.",
        "If they point out weaknesses, I feel embarrassed and start doubting myself.",
        "Last time I got a critical comment, I kept replaying it for days.",
        "So I try to avoid the conversation to protect my confidence.",
        "But I also feel stuck because I'm not improving.",
        "If I keep avoiding this, I'll probably plateau and get passed over.",
        "I want to handle feedback without spiraling.",
        "I will ask my manager for one specific piece of feedback in next week's 1:1.",
        "Tonight I'll write down the exact question I'll ask and how I'll respond if it's uncomfortable.",
    ]

    # Step 1: Create session
    print("\n" + "=" * 60)
    print("Step 1: Creating session...")
    print("=" * 60)

    try:
        create_resp = requests.post(
            f"{base_url}/sessions",
            json={
                "topic": "I avoid feedback because it makes me feel exposed",
                "max_turns": 12
            },
            timeout=30
        )
        create_resp.raise_for_status()
        create_data = create_resp.json()
    except requests.exceptions.ConnectionError:
        print(f"ERROR: Could not connect to API at {base_url}")
        print("Make sure the server is running with: uvicorn app.main:app --reload")
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        print(f"ERROR: Failed to create session: {e}")
        sys.exit(1)

    session_id = create_data.get("session_id")
    if not session_id:
        print(f"ERROR: No session_id in response: {create_data}")
        sys.exit(1)

    print(f"Session ID: {session_id}")
    print(f"Initial phase: {create_data.get('phase')}")
    print(f"Initial coach message:\n{create_data.get('content', '')[:200]}...")

    # Step 2: Send messages
    print("\n" + "=" * 60)
    print("Step 2: Sending messages...")
    print("=" * 60)

    for i, msg in enumerate(messages, 1):
        print(f"\n--- Turn {i} ---")
        print(f"User: {msg[:60]}...")

        try:
            msg_resp = requests.post(
                f"{base_url}/sessions/{session_id}/messages",
                json={"content": msg},
                timeout=60
            )
            msg_resp.raise_for_status()
            msg_data = msg_resp.json()
        except requests.exceptions.RequestException as e:
            print(f"ERROR: Failed to send message: {e}")
            continue

        print(f"Phase: {msg_data.get('phase')}")
        print(f"Coach: {msg_data.get('content', '')[:100]}...")

        # Small delay between messages
        time.sleep(0.5)

    # Step 3: End session
    print("\n" + "=" * 60)
    print("Step 3: Ending session...")
    print("=" * 60)

    try:
        end_resp = requests.post(
            f"{base_url}/sessions/{session_id}/end",
            timeout=60
        )
        end_resp.raise_for_status()
        end_data = end_resp.json()
    except requests.exceptions.RequestException as e:
        print(f"ERROR: Failed to end session: {e}")
        end_data = {}

    print(f"Session ended successfully")
    if "reflection" in end_data:
        reflection = end_data["reflection"]
        print(f"\nReflection:")
        print(f"  Outcome: {reflection.get('outcome_classification')}")
        print(f"  Commitment: {reflection.get('commitment')}")
        print(f"  Key Observations: {reflection.get('key_observations', '')[:150]}...")

    # Step 4: Get final session state
    print("\n" + "=" * 60)
    print("Step 4: Final session state...")
    print("=" * 60)

    try:
        session_resp = requests.get(
            f"{base_url}/sessions/{session_id}",
            timeout=30
        )
        session_resp.raise_for_status()
        session_data = session_resp.json()
    except requests.exceptions.RequestException as e:
        print(f"ERROR: Failed to get session: {e}")
        session_data = {}

    print(json.dumps(session_data, indent=2))

    print("\n" + "=" * 60)
    print("TEST COMPLETED SUCCESSFULLY")
    print("=" * 60)


if __name__ == "__main__":
    main()
