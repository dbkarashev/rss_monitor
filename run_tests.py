import unittest
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_rss_monitor import TestExceptionHandling, TestInputValidation

if __name__ == '__main__':
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add exception handling tests
    suite.addTests(loader.loadTestsFromTestCase(TestExceptionHandling))
    
    # Add input validation tests
    suite.addTests(loader.loadTestsFromTestCase(TestInputValidation))
    
    # Run tests with verbose output
    runner = unittest.TextTestRunner(verbosity=2, stream=sys.stdout)
    result = runner.run(suite)
    
    # Print statistics
    print(f"\n{'='*50}")
    print(f"Total tests: {result.testsRun}")
    print(f"Successful: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"{'='*50}")
    
    # Exit with error code if there are failures
    sys.exit(0 if result.wasSuccessful() else 1)