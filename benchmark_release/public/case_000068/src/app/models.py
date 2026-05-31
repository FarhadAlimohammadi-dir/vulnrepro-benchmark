from flask_login import UserMixin


class User(UserMixin):
    def __init__(self, user_id, username, email, role='editor'):
        self.id = user_id
        self.username = username
        self.email = email
        self.role = role

    def is_admin(self):
        return self.role == 'admin'

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'role': self.role
        }


class Post:
    def __init__(self, row):
        self.id = row['id']
        self.title = row['title']
        self.content = row['content']
        self.author_id = row['author_id']
        self.category = row['category']
        self.status = row['status']
        self.created_at = row['created_at']
        self.updated_at = row['updated_at']

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'content': self.content,
            'author_id': self.author_id,
            'category': self.category,
            'status': self.status,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }