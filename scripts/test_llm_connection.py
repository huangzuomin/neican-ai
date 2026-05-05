#!/usr/bin/env python3
"""
Test script for LLM configuration and connection to SiliconFlow API.
Tests both basic chat and structured output (JSON mode) capabilities.
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from dotenv import load_dotenv
    from openai import OpenAI
except ImportError as e:
    print(f"[ERROR] Missing dependency: {e}")
    print("Please run: python3 -m pip install -r requirements.txt")
    sys.exit(1)


def load_env():
    """Load environment variables from .env file."""
    env_path = project_root / ".env"
    if not env_path.exists():
        print(f"[ERROR] .env file not found at {env_path}")
        return False

    load_dotenv(env_path)
    return True


def verify_config():
    """Verify that required environment variables are set."""
    required_vars = ["LLM_API_KEY", "LLM_MODEL", "LLM_BASE_URL"]
    missing_vars = []

    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)

    if missing_vars:
        print(f"[ERROR] Missing environment variables: {', '.join(missing_vars)}")
        return False

    return True


def test_basic_chat(client, model):
    """Test basic chat completion."""
    print("\n[TEST 1] Basic Chat Completion")
    print("-" * 50)

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Say 'Hello from neican.ai!' in exactly this way."}
            ],
            max_tokens=50,
            temperature=0.7,
        )

        content = response.choices[0].message.content
        print(f"✓ Response: {content}")
        print(f"✓ Model: {response.model}")
        print(f"✓ Usage: {response.usage.total_tokens} tokens")
        return True

    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def test_structured_output(client, model):
    """Test structured JSON output."""
    print("\n[TEST 2] Structured JSON Output")
    print("-" * 50)

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a data extraction assistant. Always respond with valid JSON."},
                {"role": "user", "content": "Extract the following information as JSON: 'OpenAI released GPT-5 today with improved reasoning capabilities.'" }
            ],
            response_format={"type": "json_object"},
            max_tokens=200,
            temperature=0.3,
        )

        content = response.choices[0].message.content
        print(f"✓ JSON Response:")
        print(f"  {content}")

        # Verify it's valid JSON
        import json
        parsed = json.loads(content)
        print(f"✓ Valid JSON with keys: {list(parsed.keys())}")
        return True

    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def test_event_modeling_prompt(client, model):
    """Test a realistic event modeling prompt."""
    print("\n[TEST 3] Event Modeling Simulation")
    print("-" * 50)

    try:
        prompt = """You are an AI industry event modeling assistant. Analyze the following news item and extract structured information.

News: "Anthropic today released Claude 4.5 Opus, featuring improved performance on reasoning tasks and multilingual understanding."

Extract and return as JSON:
{
  "event_title": "Clear title",
  "event_type": "one of: model_release, product_update, research_paper, funding, etc.",
  "entities": ["list of mentioned companies/models"],
  "topics": ["list of relevant AI topics"],
  "importance_score": 0-100,
  "confidence": 0.0-1.0,
  "summary": "Brief summary"
}
"""

        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a precise data extraction assistant. Always respond with valid JSON."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            max_tokens=500,
            temperature=0.5,
        )

        content = response.choices[0].message.content
        print(f"✓ Event Modeling Response:")
        print(f"  {content}")

        import json
        parsed = json.loads(content)
        print(f"✓ Extracted fields: {list(parsed.keys())}")
        print(f"✓ Event Type: {parsed.get('event_type', 'N/A')}")
        print(f"✓ Importance Score: {parsed.get('importance_score', 'N/A')}")
        return True

    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def main():
    """Run all tests."""
    print("=" * 50)
    print("LLM Configuration Test for neican.ai")
    print("=" * 50)

    # Load environment
    if not load_env():
        sys.exit(1)

    # Verify configuration
    if not verify_config():
        sys.exit(1)

    print("\n[OK] Environment variables loaded:")
    print(f"  Model: {os.getenv('LLM_MODEL')}")
    print(f"  Base URL: {os.getenv('LLM_BASE_URL')}")
    print(f"  Temperature: {os.getenv('LLM_TEMPERATURE')}")
    print(f"  Max Tokens: {os.getenv('LLM_MAX_TOKENS')}")

    # Initialize client
    api_key = os.getenv("LLM_API_KEY")
    base_url = os.getenv("LLM_BASE_URL")
    model = os.getenv("LLM_MODEL")

    client = OpenAI(
        api_key=api_key,
        base_url=base_url,
    )

    print(f"\n[OK] OpenAI client initialized for SiliconFlow API")

    # Run tests
    results = []
    results.append(("Basic Chat", test_basic_chat(client, model)))
    results.append(("Structured Output", test_structured_output(client, model)))
    results.append(("Event Modeling", test_event_modeling_prompt(client, model)))

    # Summary
    print("\n" + "=" * 50)
    print("Test Summary")
    print("=" * 50)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {test_name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n✓ All tests passed! LLM configuration is ready.")
        return 0
    else:
        print(f"\n✗ {total - passed} test(s) failed. Please check the configuration.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
