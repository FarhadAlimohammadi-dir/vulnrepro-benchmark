import bcrypt
from flask_login import UserMixin
import db


class User(UserMixin):
    def __init__(self, id, username, email, role, created_at, last_login=None):
        self.id = id
        self.username = username
        self.email = email
        self.role = role
        self.created_at = created_at
        self.last_login = last_login

    @classmethod
    def get_by_id(cls, user_id):
        row = db.query_one('SELECT * FROM users WHERE id=?', (user_id,))
        if not row:
            return None
        return cls(row['id'], row['username'], row['email'],
                   row['role'], row['created_at'], row['last_login'])

    @classmethod
    def get_by_username(cls, username):
        row = db.query_one('SELECT * FROM users WHERE username=?', (username,))
        if not row:
            return None
        return cls(row['id'], row['username'], row['email'],
                   row['role'], row['created_at'], row['last_login'])

    @classmethod
    def authenticate(cls, username, password):
        row = db.query_one('SELECT * FROM users WHERE username=?', (username,))
        if not row:
            return None
        if bcrypt.checkpw(password.encode(), row['password_hash'].encode()):
            return cls(row['id'], row['username'], row['email'],
                       row['role'], row['created_at'], row['last_login'])
        return None

    @classmethod
    def create(cls, username, email, password, role='user'):
        from datetime import datetime
        pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        now = datetime.utcnow().isoformat()
        user_id = db.execute(
            'INSERT INTO users (username, email, password_hash, role, created_at) VALUES (?,?,?,?,?)',
            (username, email, pw_hash, role, now)
        )
        return cls(user_id, username, email, role, now)

    def is_admin(self):
        return self.role == 'admin'