from flask_login import UserMixin


class User(UserMixin):
    def __init__(self, id, username, email, password_hash):
        self.id = id
        self.username = username
        self.email = email
        self.password_hash = password_hash

    def get_id(self):
        return str(self.id)


class Document:
    def __init__(self, id, owner_id, title, content, content_type, visibility, created_at):
        self.id = id
        self.owner_id = owner_id
        self.title = title
        self.content = content
        self.content_type = content_type
        self.visibility = visibility
        self.created_at = created_at