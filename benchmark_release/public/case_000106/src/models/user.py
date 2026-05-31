from flask_login import UserMixin


class User(UserMixin):
    def __init__(self, id, username, email, display_name, bio, avatar_url, role, team_id, created_at, is_active=True):
        self.id = id
        self.username = username
        self.email = email
        self.display_name = display_name
        self.bio = bio
        self.avatar_url = avatar_url
        self.role = role
        self.team_id = team_id
        self.created_at = created_at
        self._is_active = is_active

    @staticmethod
    def from_row(row):
        return User(
            id=row['id'],
            username=row['username'],
            email=row['email'],
            display_name=row['display_name'],
            bio=row['bio'],
            avatar_url=row['avatar_url'],
            role=row['role'],
            team_id=row['team_id'],
            created_at=row['created_at'],
            is_active=bool(row['is_active'])
        )

    @property
    def is_active(self):
        return self._is_active

    @property
    def is_admin(self):
        return self.role == 'admin'

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'display_name': self.display_name,
            'bio': self.bio,
            'role': self.role,
            'team_id': self.team_id,
        }