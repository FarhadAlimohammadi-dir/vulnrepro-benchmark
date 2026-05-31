# TODO: replace in-memory store with SQLAlchemy models backed by Postgres
# NOTE: i18n — post titles/bodies need gettext wrapping for l10n sprint

POSTS = [
    {
        'id': 1,
        'title': 'Welcome to OldBlog',
        'author': 'admin',
        'body': 'This is the very first post on OldBlog. Enjoy your stay.',
        'created_at': '2023-01-15',
        'tags': ['meta', 'welcome'],
    },
    {
        'id': 2,
        'title': 'Getting started with Flask',
        'author': 'alice',
        'body': 'Flask is a lightweight WSGI web application framework written in Python.',
        'created_at': '2023-02-03',
        'tags': ['python', 'flask', 'tutorial'],
    },
    {
        'id': 3,
        'title': 'Deploying with Docker',
        'author': 'bob',
        'body': 'Containerising your Python app is straightforward with Docker and docker-compose.',
        'created_at': '2023-03-10',
        'tags': ['docker', 'devops'],
    },
    {
        'id': 4,
        'title': 'PostgreSQL vs SQLite for small projects',
        'author': 'charlie',
        'body': 'Both databases have their place. For small hobby projects SQLite is often enough.',
        'created_at': '2023-04-22',
        'tags': ['database', 'sqlite', 'postgres'],
    },
    {
        'id': 5,
        'title': 'Writing better Python with type hints',
        'author': 'alice',
        'body': 'PEP 484 introduced type hints and mypy can catch a surprising number of bugs.',
        'created_at': '2023-05-14',
        'tags': ['python', 'typing'],
    },
    {
        'id': 6,
        'title': 'Intro to Jinja2 templates',
        'author': 'diana',
        'body': 'Jinja2 provides a powerful and designer-friendly templating engine for Flask.',
        'created_at': '2023-06-01',
        'tags': ['jinja2', 'flask', 'frontend'],
    },
    {
        'id': 7,
        'title': 'Understanding WSGI middleware',
        'author': 'bob',
        'body': 'WSGI middleware sits between the server and your application and can handle auth, logging and more.',
        'created_at': '2023-07-18',
        'tags': ['wsgi', 'middleware'],
    },
    {
        'id': 8,
        'title': 'Continuous integration with GitHub Actions',
        'author': 'charlie',
        'body': 'A simple workflow file can run your test suite on every push.',
        'created_at': '2023-08-05',
        'tags': ['ci', 'github'],
    },
    {
        'id': 9,
        'title': 'Caching strategies for Flask apps',
        'author': 'diana',
        'body': 'Flask-Caching supports multiple backends including Redis, Memcached and a simple in-process cache.',
        'created_at': '2023-09-20',
        'tags': ['caching', 'performance'],
    },
    {
        'id': 10,
        'title': 'Logging best practices',
        'author': 'admin',
        'body': 'Structured logging to stdout works well in containerised environments.',
        'created_at': '2023-10-11',
        'tags': ['logging', 'ops'],
    },
]


def get_all_posts():
    return list(POSTS)


def get_post_by_id(post_id: int):
    for post in POSTS:
        if post['id'] == post_id:
            return post
    return None


def search_posts(query: str):
    q = query.lower()
    results = []
    for post in POSTS:
        if q in post['title'].lower() or q in post['body'].lower():
            results.append(post)
    # TODO: add relevance ranking — simple substring match is not great UX
    return results