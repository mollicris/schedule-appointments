#!/usr/bin/env python
"""Test the complete tenant onboarding flow.

Run with: uv run test_onboarding_flow.py
"""

import asyncio
import httpx
import json
from datetime import datetime

BASE_URL = "http://localhost:9000"


async def test_onboarding_flow():
    """Test tenant registration and email verification flow."""
    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        print("=" * 60)
        print("TESTING TENANT ONBOARDING FLOW")
        print("=" * 60)

        # Step 1: Register a new tenant
        print("\n1. REGISTERING TENANT...")
        register_payload = {
            "name": "Flow Test Salon",
            "admin_email": f"flow-test-{datetime.now().timestamp()}@salon.io",
            "admin_password": "FlowTestPassword123!",
            "industry": "hair_salon",
        }
        print(f"   Request: POST /api/v1/onboarding/register")
        print(f"   Payload: {json.dumps(register_payload, indent=2)}")

        response = await client.post(
            "/api/v1/onboarding/register",
            json=register_payload,
        )
        print(f"   Status: {response.status_code}")

        if response.status_code != 201:
            print(f"   Error: {response.text}")
            return

        register_data = response.json()
        print(f"   Response: {json.dumps(register_data, indent=2)}")

        tenant_id = register_data["data"]["tenant_id"]
        admin_email = register_data["data"]["verification_sent_to"]

        print(f"\n   ✓ Tenant registered: {tenant_id}")
        print(f"   ✓ Verification sent to: {admin_email}")

        # Step 2: Get verification token from in-memory service
        print("\n2. GETTING VERIFICATION TOKEN...")
        print(f"   Note: Using in-memory token service for testing")

        # We need to get the token from the service
        # This is a bit tricky since tokens are in-memory
        # In a real scenario, the token would be in the email
        # For testing, we'll need to manually get it from the service

        # Since we can't directly access the in-memory service from here,
        # we'll simulate a token generation
        # In production, this would come from the email

        print("   (In production, user would receive token via email)")
        print("   (For testing, token would be retrieved from in-memory service)")

        # Step 3: Try verification with invalid token first
        print("\n3. TESTING VERIFICATION WITH INVALID TOKEN...")
        response = await client.post(
            "/api/v1/onboarding/verify/invalid-token-123",
        )
        print(f"   Status: {response.status_code}")

        if response.status_code == 422:
            error_data = response.json()
            print(f"   ✓ Invalid token correctly rejected")
            print(f"   Error code: {error_data['code']}")
            print(f"   Error message: {error_data['message']}")
        else:
            print(f"   ✗ Unexpected status: {response.status_code}")
            print(f"   Response: {response.text}")

        print("\n" + "=" * 60)
        print("NOTE: Full flow testing requires:")
        print("  1. Access to the in-memory token service")
        print("  2. A way to retrieve the verification token")
        print("  3. Email sending capability in production")
        print("\nFor complete testing, run:")
        print("  pytest tests/test_onboarding.py")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_onboarding_flow())
