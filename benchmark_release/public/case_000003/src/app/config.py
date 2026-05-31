import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-change-in-prod-ENG-1042')
    DATABASE_PATH = os.environ.get('DATABASE_PATH', '/tmp/codenest.db')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = os.environ.get('FLASK_ENV') == 'production'
    ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', 'sk-ant-api03-placeholder-dev-key')
    MCP_TIMEOUT_SECONDS = int(os.environ.get('MCP_TIMEOUT_SECONDS', '15'))
    MAX_WORKSPACES_PER_USER = int(os.environ.get('MAX_WORKSPACES_PER_USER', '20'))
    ALLOWED_LINT_TOOLS = ['pylint', 'flake8', 'eslint', 'rubocop', 'golangci-lint']
    ALLOWED_FORMAT_TOOLS = ['black', 'prettier', 'gofmt', 'rustfmt']
    WORKSPACE_BOOT_TIMEOUT = int(os.environ.get('WORKSPACE_BOOT_TIMEOUT', '30'))


class DevelopmentConfig(Config):
    DEBUG = True
    TESTING = False


class ProductionConfig(Config):
    DEBUG = False
    TESTING = False


config_map = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig,
}