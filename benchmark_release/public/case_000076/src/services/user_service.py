# NOTE: passwords are NOT stored here — this is a read-only profile service

USERS = [
    {'username': 'admin',   'display_name': 'Administrator', 'email': 'admin@oldblog.local',   'role': 'admin',  'joined': '2022-11-01'},
    {'username': 'alice',   'display_name': 'Alice Chen',    'email': 'alice@oldblog.local',   'role': 'editor', 'joined': '2022-11-15'},
    {'username': 'bob',     'display_name': 'Bob Smith',     'email': 'bob@oldblog.local',     'role': 'author', 'joined': '2022-12-01'},
    {'username': 'charlie', 'display_name': 'Charlie Davis', 'email': 'charlie@oldblog.local', 'role': 'author', 'joined': '2023-01-10'},
    {'username': 'diana',   'display_name': 'Diana Evans',   'email': 'diana@oldblog.local',   'role': 'editor', 'joined': '2023-02-20'},
    {'username': 'eve',     'display_name': 'Eve Franklin',  'email': 'eve@oldblog.local',     'role': 'viewer', 'joined': '2023-03-05'},
    {'username': 'frank',   'display_name': 'Frank Green',   'email': 'frank@oldblog.local',   'role': 'author', 'joined': '2023-04-14'},
    {'username': 'grace',   'display_name': 'Grace Hall',    'email': 'grace@oldblog.local',   'role': 'viewer', 'joined': '2023-05-22'},
]


def list_users():
    # TODO: paginate this — will grow once SSO is enabled
    return [
        {k: v for k, v in u.items() if k != 'email'}
        for u in USERS
    ]


def get_user_profile(username: str):
    for user in USERS:
        if user['username'] == username:
            # Don't expose email to unauthenticated callers
            return {k: v for k, v in user.items() if k != 'email'}
    return None