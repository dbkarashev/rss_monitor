#!/usr/bin/env python3
import feedparser
import sqlite3
import time
from datetime import datetime

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
        print(f"Saved: {article['title'][:50]}...")
    except sqlite3.IntegrityError:
        pass
    
    conn.close()

def get_all_news():
    conn = sqlite3.connect('news.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM found_news ORDER BY found_at DESC')
    news = cursor.fetchall()
    conn.close()
    return news

def parse_rss_feed(url):
    feed = feedparser.parse(url)
    articles = []
    
    for entry in feed.entries[:10]:
        article = {
            'title': entry.title,
            'link': entry.link,
            'description': getattr(entry, 'description', '')
        }
        articles.append(article)
    
    return articles

def check_keywords(text, keywords):
    found = []
    text_lower = text.lower()
    for keyword in keywords:
        if keyword.lower() in text_lower:
            found.append(keyword)
    return found

def main():
    init_database()
    
    rss_urls = [
        'http://feeds.bbci.co.uk/news/rss.xml',
        'http://rss.cnn.com/rss/edition.rss',
        'https://rssexport.rbc.ru/rbcnews/news/20/full.rss'
    ]
    
    keywords = ['technology', 'AI', 'Python', 'programming', 'tech', 'искусственный']
    
    print("RSS Monitor with Database")
    print("=" * 30)
    
    for url in rss_urls:
        print(f"\nProcessing: {url}")
        articles = parse_rss_feed(url)
        
        for article in articles:
            text_to_check = f"{article['title']} {article['description']}"
            matched_keywords = check_keywords(text_to_check, keywords)
            
            if matched_keywords:
                save_article(article, matched_keywords)
        
        time.sleep(2)
    
    print(f"\nTotal saved articles: {len(get_all_news())}")

if __name__ == '__main__':
    main()