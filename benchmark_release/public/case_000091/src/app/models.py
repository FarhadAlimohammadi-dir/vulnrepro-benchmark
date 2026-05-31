from flask_login import UserMixin


class User(UserMixin):
    def __init__(self, user_id, username, email, role):
        self.id = user_id
        self.username = username
        self.email = email
        self.role = role

    def is_admin(self):
        return self.role == "admin"

    def is_editor(self):
        return self.role in ("admin", "editor")

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "role": self.role,
        }