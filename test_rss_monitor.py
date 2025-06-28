import unittest
import sqlite3
import tempfile
import os
import sys
from unittest.mock import patch, Mock, MagicMock
from flask import Flask

# Add path to main module
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rss_monitor import RSSMonitor, app

class TestExceptionHandling(unittest.TestCase):
    """Tests for exception handling"""
    
    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        self.monitor = RSSMonitor(self.temp_db.name)
    
    def tearDown(self):
        if os.path.exists(self.temp_db.name):
            os.unlink(self.temp_db.name)
    
    def test_init_db_with_invalid_path(self):
        """Test database initialization with invalid path"""
        invalid_path = "/root/restricted/invalid.db"
        with self.assertRaises((sqlite3.OperationalError, PermissionError)):
            monitor = RSSMonitor(invalid_path)
    
    def test_init_db_with_readonly_path(self):
        """Test database initialization with readonly file"""
        readonly_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        readonly_db.close()
        os.chmod(readonly_db.name, 0o444)  # Read-only
        
        try:
            with self.assertRaises(sqlite3.OperationalError):
                monitor = RSSMonitor(readonly_db.name)
                monitor.init_db()
        finally:
            os.chmod(readonly_db.name, 0o644)
            os.unlink(readonly_db.name)
    
    @patch('sqlite3.connect')
    def test_get_active_feeds_db_connection_error(self, mock_connect):
        """Test database connection error handling"""
        mock_connect.side_effect = sqlite3.Error("Database connection failed")
        
        with self.assertRaises(sqlite3.Error):
            self.monitor.get_active_feeds()
    
    @patch('sqlite3.connect')
    def test_get_active_keywords_cursor_error(self, mock_connect):
        """Test cursor execution error handling"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.execute.side_effect = sqlite3.Error("Query execution failed")
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn
        
        with self.assertRaises(sqlite3.Error):
            self.monitor.get_active_keywords()
    
    @patch('feedparser.parse')
    def test_parse_feed_network_error(self, mock_parse):
        """Test network error handling in feed parsing"""
        mock_parse.side_effect = Exception("Network timeout")
        
        try:
            self.monitor.parse_feed("Test Feed", "http://invalid.url", ["test"])
        except Exception as e:
            self.fail(f"parse_feed should handle network errors, but failed with: {e}")
    
    @patch('feedparser.parse')
    def test_parse_feed_malformed_xml(self, mock_parse):
        """Test malformed XML handling"""
        mock_feed = Mock()
        mock_feed.bozo = True
        mock_feed.bozo_exception = Exception("XML parsing error")
        mock_feed.entries = []
        mock_parse.return_value = mock_feed
        
        # Should handle without crashing
        self.monitor.parse_feed("Test Feed", "http://test.url", ["keyword"])
        self.assertTrue(True)
    
    def test_clean_html_with_none_input(self):
        """Test HTML cleaning with None input"""
        result = self.monitor.clean_html(None)
        self.assertEqual(result, "")
    
    def test_clean_html_with_empty_string(self):
        """Test HTML cleaning with empty string"""
        result = self.monitor.clean_html("")
        self.assertEqual(result, "")


class TestInputValidation(unittest.TestCase):
    """Tests for input validation"""
    
    def setUp(self):
        self.app = app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
    
    def tearDown(self):
        if os.path.exists(self.temp_db.name):
            os.unlink(self.temp_db.name)
    
    def test_add_feed_with_empty_name(self):
        """Test adding feed with empty name"""
        response = self.client.post('/add_feed', data={
            'name': '',
            'url': 'https://example.com/feed.xml'
        })
        self.assertEqual(response.status_code, 302)  # Redirect
    
    def test_add_feed_with_none_name(self):
        """Test adding feed with missing name"""
        response = self.client.post('/add_feed', data={
            'url': 'https://example.com/feed.xml'
        })
        self.assertEqual(response.status_code, 302)
    
    def test_add_feed_with_invalid_url_format(self):
        """Test adding feed with invalid URL format"""
        response = self.client.post('/add_feed', data={
            'name': 'Test Feed',
            'url': 'not-a-valid-url'
        })
        self.assertIn(response.status_code, [200, 302, 400])
    
    def test_add_feed_with_extremely_long_name(self):
        """Test adding feed with extremely long name"""
        long_name = 'A' * 10000
        response = self.client.post('/add_feed', data={
            'name': long_name,
            'url': 'https://example.com/feed.xml'
        })
        self.assertEqual(response.status_code, 302)
    
    def test_add_keyword_with_empty_value(self):
        """Test adding empty keyword"""
        response = self.client.post('/add_keyword', data={
            'keyword': ''
        })
        self.assertEqual(response.status_code, 302)
    
    def test_add_keyword_with_special_characters(self):
        """Test adding keyword with special characters"""
        special_keyword = '"><script>alert("xss")</script>'
        response = self.client.post('/add_keyword', data={
            'keyword': special_keyword
        })
        self.assertEqual(response.status_code, 302)
    
    def test_add_keyword_with_unicode_characters(self):
        """Test adding keyword with Unicode characters"""
        unicode_keyword = 'тест 测试 🔍'
        response = self.client.post('/add_keyword', data={
            'keyword': unicode_keyword
        })
        self.assertEqual(response.status_code, 302)
    
    def test_check_keywords_in_text_with_none_input(self):
        """Test keyword checking with None input"""
        monitor = RSSMonitor(self.temp_db.name)
        result = monitor.check_keywords_in_text(None, ['test'])
        self.assertEqual(result, [])


if __name__ == '__main__':
    unittest.main(verbosity=2)