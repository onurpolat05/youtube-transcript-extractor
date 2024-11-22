import unittest
import re
from app import validate_youtube_url, extract_video_id

class TestYouTubeURLs(unittest.TestCase):
    """
    A collection of tests to make sure our YouTube URL handling works correctly.
    
    This test suite checks two main things:
    1. That we can correctly identify valid YouTube URLs
    2. That we can extract video IDs from these URLs
    
    The tests include checks for:
    - Regular watch URLs (youtube.com/watch?v=...)
    - Short URLs (youtu.be/...)
    - Live stream URLs
    - YouTube Shorts
    - Embed URLs
    - URLs with extra parameters
    - Invalid URLs
    
    How to use:
    1. Run the entire test suite:
       python -m unittest test_youtube_urls.py
    
    2. Run a specific test:
       python -m unittest test_youtube_urls.TestYouTubeURLs.test_valid_urls
    
    Example:
        >>> # This will run all tests in the class
        >>> unittest.main()
    """

    def setUp(self):
        """
        Set up test cases with valid and invalid YouTube URLs.
        
        Initializes dictionaries of valid YouTube URLs with their expected video IDs and a list of invalid URLs to test the robustness of the validation functions.
        """
        # Test URLs with known video IDs
        self.valid_urls = {
            # Standard watch URLs
            'https://www.youtube.com/watch?v=dQw4w9WgXcQ': 'dQw4w9WgXcQ',
            'https://youtube.com/watch?v=dQw4w9WgXcQ': 'dQw4w9WgXcQ',
            'https://m.youtube.com/watch?v=dQw4w9WgXcQ': 'dQw4w9WgXcQ',
            
            # Short URLs
            'https://youtu.be/dQw4w9WgXcQ': 'dQw4w9WgXcQ',
            'http://youtu.be/dQw4w9WgXcQ': 'dQw4w9WgXcQ',
            
            # With timestamp
            'https://youtu.be/dQw4w9WgXcQ?t=1': 'dQw4w9WgXcQ',
            'https://youtube.com/watch?v=dQw4w9WgXcQ&t=1s': 'dQw4w9WgXcQ',
            
            # With playlist
            'https://youtube.com/watch?v=dQw4w9WgXcQ&list=PLGup6kBfcU7Le5laEaCLgTKtlDcxMqGxZ': 'dQw4w9WgXcQ',
            
            # Embed URLs
            'https://www.youtube.com/embed/dQw4w9WgXcQ': 'dQw4w9WgXcQ',
            'https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ': 'dQw4w9WgXcQ',
            
            # Live streams
            'https://www.youtube.com/live/8hBmepWUJoc': '8hBmepWUJoc',
            'https://youtube.com/live/8hBmepWUJoc?feature=share': '8hBmepWUJoc',
            
            # Shorts
            'https://www.youtube.com/shorts/j9rZxAF3C0I': 'j9rZxAF3C0I',
            'https://youtube.com/shorts/j9rZxAF3C0I': 'j9rZxAF3C0I'
        }
        
        self.invalid_urls = [
            'https://youtube.com',
            'https://youtube.com/watch',
            'https://youtube.com/watch?v=',
            'https://youtube.com/watch?v=invalid_id',
            'https://youtu.be/',
            'https://youtube.com/live/',
            'https://youtube.com/shorts/',
            'https://notyoutube.com/watch?v=dQw4w9WgXcQ',
            'https://youtube.com/watch?id=dQw4w9WgXcQ',  # Wrong parameter name
            'randomtext'
        ]

    def test_valid_urls(self):
        """
        Test that valid YouTube URLs are correctly validated and video IDs are extracted.
        
        Iterates over a set of known valid YouTube URLs, asserts that they pass validation, and verifies that the extracted video IDs match the expected values.
        """
        for url, expected_id in self.valid_urls.items():
            with self.subTest(url=url):
                self.assertTrue(validate_youtube_url(url), f"URL should be valid: {url}")
                extracted_id = extract_video_id(url)
                self.assertEqual(extracted_id, expected_id, 
                    f"Extracted ID {extracted_id} doesn't match expected {expected_id} for URL: {url}")

    def test_invalid_urls(self):
        """
        Test that invalid YouTube URLs are correctly rejected and no video IDs are extracted.
        
        Iterates over a set of invalid YouTube URLs, asserts that they fail validation, and ensures that no video ID is extracted from them.
        """
        for url in self.invalid_urls:
            with self.subTest(url=url):
                self.assertFalse(validate_youtube_url(url), f"URL should be invalid: {url}")
                self.assertIsNone(extract_video_id(url), f"Should not extract ID from invalid URL: {url}")

if __name__ == '__main__':
    """
    Entry point for running the unit tests.
    
    Executes the test cases defined in the 'TestYouTubeURLs' class when the script is run directly.
    """
    unittest.main()
