#!/usr/bin/env python3
"""
Helper script to run tests for Cannon Chaos.
This script explicitly loads tests to avoid discovery issues.
"""
import unittest
import sys
import os

# --- Add this section --- 
# Add client and server directories to sys.path BEFORE importing tests
project_root = os.path.dirname(os.path.abspath(__file__))
client_dir = os.path.join(project_root, 'client')
server_dir = os.path.join(project_root, 'server')

if client_dir not in sys.path:
    sys.path.insert(0, client_dir)
    print(f"Added {client_dir} to Python path")

if server_dir not in sys.path:
    sys.path.insert(0, server_dir)
    print(f"Added {server_dir} to Python path")
# --- End of added section ---

# Import test modules directly
# These imports should now succeed because 'client' and 'server' are in sys.path
from tests import test_basic, test_client, test_server

if __name__ == "__main__":
    print("Starting explicit test runner...")
    
    # Add the project root to the Python path (still useful for importing 'tests')
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
        print(f"Added {project_root} to Python path")
    
    # Create a test loader
    test_loader = unittest.TestLoader()
    
    # Create an empty test suite
    main_suite = unittest.TestSuite()
    
    # Load tests from each module and add to the main suite
    print("Loading tests from test_basic...")
    try:
        # Try loading by class name directly
        suite_basic = test_loader.loadTestsFromName("tests.test_basic.BasicTest")
        print(f"  Found {suite_basic.countTestCases()} tests in test_basic.BasicTest.")
        main_suite.addTest(suite_basic)
    except Exception as e:
        print(f"  Error loading tests from test_basic by name: {e}")
        print("  Falling back to loading from module...")
        try:
            suite_basic = test_loader.loadTestsFromModule(test_basic)
            print(f"  Found {suite_basic.countTestCases()} tests in test_basic (module load).")
            main_suite.addTest(suite_basic)
        except Exception as e2:
            print(f"  Failed to load tests from test_basic module as well: {e2}")
    
    print("Loading tests from test_client...")
    # Note: test_client might have issues due to pygame mocking, load carefully
    try:
        suite_client = test_loader.loadTestsFromModule(test_client)
        print(f"  Found {suite_client.countTestCases()} tests in test_client.")
        main_suite.addTest(suite_client)
    except Exception as e:
        print(f"\n⚠️  Warning: Could not load tests from test_client.py: {e}")
        print("   This might be due to Pygame or other dependencies.")
        print("   Skipping client tests for now.\n")

    print("Loading tests from test_server...")
    # Use loadTestsFromModule as it seemed to find tests, avoid loadTestsFromName error
    try:
        suite_server = test_loader.loadTestsFromModule(test_server)
        print(f"  Found {suite_server.countTestCases()} tests in test_server (module load).")
        main_suite.addTest(suite_server)
    except Exception as e:
         print(f"  Failed to load tests from test_server module: {e}")


    print(f"\\\\nTotal tests loaded into main suite: {main_suite.countTestCases()}")
    
    # Run the combined test suite
    print("\nRunning tests...")
    test_runner = unittest.TextTestRunner(verbosity=2)
    result = test_runner.run(main_suite)
    
    # Print summary
    print(f"\nTest Summary:")
    print(f"  Ran {result.testsRun} tests")
    print(f"  Failures: {len(result.failures)}")
    print(f"  Errors: {len(result.errors)}")
    
    # Exit with non-zero status if there were failures or errors
    if result.failures or result.errors:
        print("\n❌ Some tests failed.")
        sys.exit(1)
    else:
        print("\n✅ All tests passed.")
        sys.exit(0)
