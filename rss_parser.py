#!/usr/bin/env python3
import feedparser
import sqlite3
import time
from datetime import datetime
from flask import Flask, render_template_string

app = Flask(__name__)

def init_database():
    conn = sqlite3.connect('news.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS found_news (
            id INTEGER PRIMARY KEY,
            title TEXT,
            description TEXT,
            link TEXT UNIQUE,
            keywords TEXT,
            found_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

def save_article(article, keywords):
    conn = sqlite3.connect('news.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT INTO found_news (title, description, link, keywords)
            VALUES (?, ?, ?, ?)
        ''', (
            article['title'],
            article['description'][:300],
            article['link'],
            ', '.join(keywords)
        ))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def get_all_news():
    conn = sqlite3.connect('news.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM found_news ORDER BY found_at DESC LIMIT 20')
    news = cursor.fetchall()
    conn.close()
    return news

def parse_and_save():
    rss_urls = [
        'http://feeds.bbci.co.uk/news/rss.xml',
        'http://rss.cnn.com/rss/edition.rss'
    ]
    
    keywords = ['technology', 'AI', 'Python', 'programming', 'tech']
    
    for url in rss_urls:
        feed = feedparser.parse(url)
        
        for entry in feed.entries[:5]:
            article = {
                'title': entry.title,
                'link': entry.link,
                'description': getattr(entry, 'description', '')
            }
            
            text_to_check = f"{article['title']} {article['description']}"
            matched_keywords = []
            
            for keyword in keywords:
                if keyword.lower() in text_to_check.lower():
                    matched_keywords.append(keyword)
            
            if matched_keywords:
                save_article(article, matched_keywords)

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>RSS Monitor</title>
    <style>
        body { font-family: Arial; margin: 20px; }
        .article { border: 1px solid #ccc; padding: 15px; margin: 10px 0; }
        .title { font-weight: bold; color: #0066cc; }
        .meta { color: #666; font-size: 0.9em; }
        .keywords { background: #ffeb3b; padding: 2px 4px; }
    </style>
</head>
<body>
    <h1>RSS News Monitor</h1>
    <p><a href="/scan">Scan RSS Feeds</a> | <a href="/">Refresh</a></p>
    
    <h2>Found Articles ({{ articles|length }})</h2>
    
    {% for article in articles %}
    <div class="article">
        <div class="title">{{ article[1] }}</div>
        <div class="meta">
            Keywords: <span class="keywords">{{ article[4] }}</span> | 
            Found: {{ article[5] }}
        </div>
        <div>{{ article[2] }}</div>
        <div><a href="{{ article[3] }}" target="_blank">Read more</a></div>
    </div>
    {% endfor %}
</body>
</html>
'''

@app.route('/')
def index():
    articles = get_all_news()
    return render_template_string(HTML_TEMPLATE, articles=articles)

@app.route('/scan')
def scan():
    parse_and_save()
    return '<h2>Scan completed!</h2><a href="/">Back to articles</a>'

if __name__ == '__main__':
    init_database()
    print("Web interface: http://localhost:5000")
    app.run(debug=True, port=5000)