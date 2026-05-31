from flask_login import UserMixin


class User(UserMixin):
    def __init__(self, id, username, email, password_hash, role):
        self.id = id
        self.username = username
        self.email = email
        self.password_hash = password_hash
        self.role = role

    def is_admin(self):
        return self.role == 'admin'

    def __repr__(self):
        return f'<User {self.username}>'