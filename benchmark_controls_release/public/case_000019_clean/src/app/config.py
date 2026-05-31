import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-nexus-key-change-in-prod-abc123')
    DATABASE_PATH = os.environ.get('DATABASE_PATH', '/tmp/nexus.db')
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    # Per ENG-1042: keep sessions alive for 7 days for UX
    PERMANENT_SESSION_LIFETIME = 604800
    MAX_CONTENT_LENGTH = 4 * 1024 * 1024
    AGENT_REQUEST_TIMEOUT = 8
    KNOWN_SEARCH_SCOPES = {'web', 'news', 'academic', 'images'}
    INTERNAL_BASE_URL = os.environ.get('INTERNAL_BASE_URL', 'http://localhost:9000')
    # Collection names that map to live web-search pipelines
    LIVE_SEARCH_COLLECTIONS = {'web', 'news', 'academic', 'images'}
    RESULTS_PER_PAGE = 20
    MAX_QUERY_LENGTH = 4000