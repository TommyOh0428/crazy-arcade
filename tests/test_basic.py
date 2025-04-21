"""
Ultra-basic test file to verify unittest discovery is working correctly.
"""
print("--- test_basic.py: Module level execution ---")

import unittest

print("--- test_basic.py: Imported unittest ---")

class BasicTest(unittest.TestCase):
    print("--- test_basic.py: Inside BasicTest class definition ---")

    def test_simple_assertion(self):
        """A simple test to verify test discovery works"""
        print("--- test_basic.py: Running test_simple_assertion ---")
        self.assertEqual(1 + 1, 2)
        
    def test_string_equality(self):
        """Test string comparison works"""
        print("--- test_basic.py: Running test_string_equality ---")
        self.assertEqual("hello", "hello")
        
    def test_boolean_assertion(self):
        """Test boolean assertion works"""
        print("--- test_basic.py: Running test_boolean_assertion ---")
        self.assertTrue(True)
        self.assertFalse(False)

print("--- test_basic.py: End of module execution ---")
