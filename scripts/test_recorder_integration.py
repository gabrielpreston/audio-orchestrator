#!/usr/bin/env python3
"""
Test script to verify the test recorder integration with the orchestrator service.

This script tests the test recorder endpoints to ensure they work correctly.
"""

import json
import sys
from pathlib import Path

import requests


def test_recorder_endpoints(base_url: str = "http://localhost:8000") -> bool:
    """Test the test recorder endpoints."""
    print(f"Testing test recorder endpoints at {base_url}")
    
    # Test 1: Check if the web interface is accessible
    print("\n1. Testing web interface accessibility...")
    try:
        response = requests.get(f"{base_url}/test-recorder", timeout=10)
        if response.status_code == 200:
            print("✓ Web interface accessible")
        else:
            print(f"✗ Web interface returned status {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Web interface not accessible: {e}")
        return False
    
    # Test 2: Check if static files are served
    print("\n2. Testing static file serving...")
    try:
        response = requests.get(f"{base_url}/static/css/test-recorder.css", timeout=10)
        if response.status_code == 200:
            print("✓ CSS file accessible")
        else:
            print(f"✗ CSS file returned status {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ CSS file not accessible: {e}")
        return False
    
    try:
        response = requests.get(f"{base_url}/static/js/test-recorder.js", timeout=10)
        if response.status_code == 200:
            print("✓ JavaScript file accessible")
        else:
            print(f"✗ JavaScript file returned status {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ JavaScript file not accessible: {e}")
        return False
    
    # Test 3: Test adding a phrase
    print("\n3. Testing phrase management...")
    try:
        response = requests.post(
            f"{base_url}/test-recorder/phrases",
            json={"text": "Test phrase", "category": "wake"},
            timeout=10
        )
        if response.status_code == 200:
            result = response.json()
            if result.get("success"):
                phrase_id = result["phrase"]["id"]
                print(f"✓ Phrase added successfully (ID: {phrase_id})")
                
                # Test getting the phrase
                response = requests.get(f"{base_url}/test-recorder/phrases/{phrase_id}", timeout=10)
                if response.status_code == 200:
                    result = response.json()
                    if result.get("success"):
                        print("✓ Phrase retrieved successfully")
                    else:
                        print(f"✗ Failed to retrieve phrase: {result.get('error')}")
                        return False
                else:
                    print(f"✗ Failed to retrieve phrase (status: {response.status_code})")
                    return False
            else:
                print(f"✗ Failed to add phrase: {result.get('error')}")
                return False
        else:
            print(f"✗ Add phrase returned status {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Phrase management failed: {e}")
        return False
    
    # Test 4: Test listing phrases
    print("\n4. Testing phrase listing...")
    try:
        response = requests.get(f"{base_url}/test-recorder/phrases", timeout=10)
        if response.status_code == 200:
            result = response.json()
            if result.get("success"):
                phrases = result["phrases"]
                print(f"✓ Listed {len(phrases)} phrases")
            else:
                print(f"✗ Failed to list phrases: {result.get('error')}")
                return False
        else:
            print(f"✗ List phrases returned status {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Phrase listing failed: {e}")
        return False
    
    # Test 5: Test metadata export
    print("\n5. Testing metadata export...")
    try:
        response = requests.get(f"{base_url}/test-recorder/metadata", timeout=10)
        if response.status_code == 200:
            result = response.json()
            if result.get("success"):
                metadata = result["metadata"]
                print(f"✓ Metadata exported successfully ({metadata['total_phrases']} phrases)")
            else:
                print(f"✗ Failed to export metadata: {result.get('error')}")
                return False
        else:
            print(f"✗ Metadata export returned status {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Metadata export failed: {e}")
        return False
    
    # Test 6: Test stats endpoint
    print("\n6. Testing stats endpoint...")
    try:
        response = requests.get(f"{base_url}/test-recorder/stats", timeout=10)
        if response.status_code == 200:
            result = response.json()
            if result.get("success"):
                stats = result["stats"]
                print(f"✓ Stats retrieved successfully ({stats['total_phrases']} phrases)")
            else:
                print(f"✗ Failed to get stats: {result.get('error')}")
                return False
        else:
            print(f"✗ Stats returned status {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Stats retrieval failed: {e}")
        return False
    
    print("\n✓ All tests passed!")
    return True


def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test the test recorder integration")
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="Base URL of the orchestrator service (default: http://localhost:8000)"
    )
    
    args = parser.parse_args()
    
    success = test_recorder_endpoints(args.base_url)
    
    if success:
        print("\n🎉 Test recorder integration is working correctly!")
        print("\nNext steps:")
        print("1. Start the orchestrator service: make run")
        print("2. Open the test recorder: make test-recorder")
        print("3. Record some test phrases")
        print("4. Use the conversion script to convert to WAV format")
        sys.exit(0)
    else:
        print("\n❌ Test recorder integration has issues")
        print("\nTroubleshooting:")
        print("1. Make sure the orchestrator service is running")
        print("2. Check the service logs: make logs SERVICE=orchestrator")
        print("3. Verify the service is accessible at the base URL")
        sys.exit(1)


if __name__ == "__main__":
    main()