"""
Complete E2E Test: Async Discussion Flow with Multiple Users

Tests the full lifecycle of an async discussion:
1. Host creates async discussion
2. Host starts discussion (opens Round 1)
3. Three participants submit responses
4. Host closes Round 1 manually
5. System processes: summarization → clustering → Sankey
6. Host advances to Round 2
7. Repeat for Rounds 2 and 3
8. Generate final Sankey diagram

Topic: Remote Work in 2026
"""

import requests
import json
import time
from typing import Dict, Any

# Configuration
API_BASE = "http://localhost:8000/api/v1"

def load_test_users() -> Dict[str, Any]:
    """Load test users from JSON file."""
    with open('/tmp/test_users.json') as f:
        return json.load(f)

def create_async_discussion(host_token: str) -> str:
    """Create an async discussion as host."""
    payload = {
        'community_id': '00000000-0000-0000-0000-000000000001',
        'mode': 'HOST_DEFINED',
        'total_rounds': 3,
        'questions': [
            'What are the biggest challenges you face with remote work in 2026?',
            'How do you maintain work-life balance when working remotely?',
            'What technologies or practices would improve your remote work experience?'
        ],
        'timing_mode': 'ASYNCHRONOUS',
        'round_duration_hours': 24,
        'min_submissions_for_advance': 3,
        'auto_advance_enabled': False
    }

    headers = {
        'Authorization': f'Bearer {host_token}',
        'Content-Type': 'application/json'
    }

    response = requests.post(f'{API_BASE}/discussions', json=payload, headers=headers)

    if response.status_code != 201:
        print(f'❌ Failed to create discussion: {response.status_code}')
        print(response.text)
        return None

    data = response.json()
    discussion_id = data['discussion_id']

    print(f'✅ Created async discussion: {discussion_id}')
    print(f'   Timing mode: {data.get("timing_mode", "NOT SET")}')
    print(f'   Round duration: {data.get("round_duration_hours", "NOT SET")} hours')
    print(f'   Min submissions: {data.get("min_submissions_for_advance", "NOT SET")}')
    print()

    return discussion_id

def start_discussion(discussion_id: str, host_token: str) -> bool:
    """Start the discussion (opens Round 1)."""
    headers = {'Authorization': f'Bearer {host_token}'}

    response = requests.post(
        f'{API_BASE}/discussions/{discussion_id}/start',
        headers=headers
    )

    if response.status_code != 200:
        print(f'❌ Failed to start discussion: {response.status_code}')
        print(response.text)
        return False

    data = response.json()
    print(f'✅ Started discussion - Round {data["current_round_num"]} is now {data["status"]}')
    print()
    return True

def get_discussion_status(discussion_id: str, token: str) -> Dict[str, Any]:
    """Get current discussion status."""
    headers = {'Authorization': f'Bearer {token}'}
    response = requests.get(f'{API_BASE}/discussions/{discussion_id}', headers=headers)
    return response.json() if response.status_code == 200 else None

def submit_text(round_id: str, participant_id: str, participant_token: str, text: str, username: str) -> bool:
    """Submit text response as participant."""
    payload = {
        'participant_id': participant_id,
        'round_id': round_id,
        'submission_text': text,
        'modality': 'text'
    }
    headers = {
        'Authorization': f'Bearer {participant_token}',
        'Content-Type': 'application/json'
    }

    response = requests.post(
        f'{API_BASE}/submissions',
        json=payload,
        headers=headers
    )

    if response.status_code not in (200, 201):
        print(f'❌ {username} submission failed: {response.status_code}')
        print(response.text)
        return False

    print(f'✅ {username} submitted response')
    return True

def close_round(round_id: str, host_token: str) -> bool:
    """Host manually closes async round."""
    headers = {'Authorization': f'Bearer {host_token}'}

    response = requests.post(
        f'{API_BASE}/rounds/{round_id}/close',
        headers=headers
    )

    if response.status_code != 200:
        print(f'❌ Failed to close round: {response.status_code}')
        print(response.text)
        return False

    print(f'✅ Host closed round {round_id}')
    print()
    return True

def advance_discussion(discussion_id: str, host_token: str) -> bool:
    """Advance to next round."""
    headers = {'Authorization': f'Bearer {host_token}'}

    response = requests.post(
        f'{API_BASE}/discussions/{discussion_id}/advance',
        headers=headers
    )

    if response.status_code != 200:
        print(f'❌ Failed to advance: {response.status_code}')
        print(response.text)
        return False

    data = response.json()
    print(f'✅ Advanced to Round {data.get("current_round_num", "?")}')
    print()
    return True

def get_sankey_diagram(discussion_id: str, token: str) -> Dict[str, Any]:
    """Get Sankey diagram for discussion."""
    headers = {'Authorization': f'Bearer {token}'}
    response = requests.get(
        f'{API_BASE}/discussions/{discussion_id}/sankey',
        headers=headers
    )
    return response.json() if response.status_code == 200 else None

def main():
    """Run complete async discussion flow test."""
    print('=' * 80)
    print('ASYNC DISCUSSION FLOW TEST - REMOTE WORK 2026')
    print('=' * 80)
    print()

    # Load test users
    users = load_test_users()
    host_token = users['host']['token']

    participants = [
        {'name': 'Bob', 'token': users['participant1']['token'], 'id': users['participant1']['user_id']},
        {'name': 'Charlie', 'token': users['participant2']['token'], 'id': users['participant2']['user_id']},
        {'name': 'Diana', 'token': users['participant3']['token'], 'id': users['participant3']['user_id']},
    ]

    # Round-specific responses
    round_responses = {
        1: {  # Challenges
            'Bob': "The lack of face-to-face interaction makes it harder to build team cohesion. I also struggle with the blurred boundaries between work and personal life.",
            'Charlie': "Time zone differences are killer. Half my team is in Asia, so I end up working odd hours to sync up. Also missing the spontaneous hallway conversations.",
            'Diana': "Home distractions are real - kids, pets, deliveries. Plus, video call fatigue is getting worse. Sometimes I just want to talk without being on camera."
        },
        2: {  # Work-life balance
            'Bob': "I set strict hours: 9-5, no exceptions. I have a dedicated office space and close the door when work ends. Weekly exercise routine helps too.",
            'Charlie': "I use time-blocking aggressively and schedule breaks. Lunch walks are non-negotiable. Also started a 'no meetings Friday' policy with my team.",
            'Diana': "Boundaries are key. I changed my Slack status to away outside hours and put my laptop in a drawer. Morning meditation helps me transition."
        },
        3: {  # Technologies/practices
            'Bob': "AI-powered meeting summaries have been a game-changer. Also using async video messages instead of live calls when possible.",
            'Charlie': "Better virtual whiteboarding tools would help. Current ones feel clunky. Also want smarter calendar AI that protects focus time.",
            'Diana': "VR meeting spaces could make collaboration feel more natural. Also need better tools for spontaneous 'water cooler' conversations."
        }
    }

    # Step 1: Create discussion
    print('STEP 1: Creating async discussion...')
    discussion_id = create_async_discussion(host_token)
    if not discussion_id:
        return

    # Save for reference
    with open('/tmp/test_discussion_id.txt', 'w') as f:
        f.write(discussion_id)

    # Step 2: Start discussion
    print('STEP 2: Starting discussion (opens Round 1)...')
    if not start_discussion(discussion_id, host_token):
        return

    # Get current round info
    status = get_discussion_status(discussion_id, host_token)
    if not status or not status['rounds']:
        print('❌ Could not get round information')
        return

    # Process each round
    for round_num in range(1, 4):
        print(f'=' * 80)
        print(f'ROUND {round_num}: {status["rounds"][round_num-1].get("question_text", "Question not set")}')
        print(f'=' * 80)
        print()

        round_id = status['rounds'][round_num-1]['round_id']

        # Step 3: Participants submit responses
        print(f'STEP 3.{round_num}: Collecting participant responses...')
        for participant in participants:
            text = round_responses[round_num][participant['name']]
            success = submit_text(
                round_id,
                participant['id'],
                participant['token'],
                text,
                participant['name']
            )
            if not success:
                print(f'⚠️  Skipping {participant["name"]}\'s submission')
            time.sleep(0.5)  # Small delay between submissions

        print()

        # Step 4: Host closes round
        print(f'STEP 4.{round_num}: Host closing round...')
        if not close_round(round_id, host_token):
            print('⚠️  Could not close round')

        # Wait for processing
        print('⏳ Waiting for summarization and clustering...')
        time.sleep(3)

        # Check status
        status = get_discussion_status(discussion_id, host_token)
        if status:
            print(f'📊 Discussion status: {status["status"]}')
            print(f'   Current round: {status["current_round_num"]}')

        # Advance to next round (unless it's the last one)
        if round_num < 3:
            print(f'STEP 5.{round_num}: Advancing to next round...')
            if not advance_discussion(discussion_id, host_token):
                print('⚠️  Could not advance')
                break

            # Refresh status for next iteration
            status = get_discussion_status(discussion_id, host_token)
            print()
        else:
            print('✅ All rounds completed!')
            print()

    # Step 6: Generate Sankey diagram
    print('=' * 80)
    print('FINAL STEP: Generating Sankey Diagram...')
    print('=' * 80)
    print()

    sankey = get_sankey_diagram(discussion_id, host_token)
    if sankey:
        print('✅ Sankey diagram generated!')
        print(f'   Nodes: {len(sankey.get("nodes", []))}')
        print(f'   Edges: {len(sankey.get("edges", []))}')
        print(f'   URL: http://localhost:3000/discussions/{discussion_id}/sankey')
    else:
        print('⚠️  Sankey diagram not available yet')

    print()
    print('=' * 80)
    print('TEST COMPLETE!')
    print('=' * 80)
    print()
    print(f'Discussion ID: {discussion_id}')
    print(f'Live View: http://localhost:3000/discussions/{discussion_id}/live')
    print(f'Sankey View: http://localhost:3000/discussions/{discussion_id}/sankey')
    print(f'Report View: http://localhost:3000/discussions/{discussion_id}/report')

if __name__ == '__main__':
    main()
