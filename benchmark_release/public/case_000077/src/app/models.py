from flask_login import UserMixin


class User(UserMixin):
    def __init__(self, user_id, username, email, role, password_hash):
        self.id = user_id
        self.username = username
        self.email = email
        self.role = role
        self.password_hash = password_hash

    def is_admin(self):
        return self.role == 'admin'

    def to_dict(self, include_sensitive=False):
        data = {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'role': self.role,
        }
        return data


class Project:
    def __init__(self, project_id, name, description, owner_id, status, created_at):
        self.id = project_id
        self.name = name
        self.description = description
        self.owner_id = owner_id
        self.status = status
        self.created_at = created_at

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'owner_id': self.owner_id,
            'status': self.status,
            'created_at': self.created_at,
        }


class Task:
    def __init__(self, task_id, title, description, project_id, assignee_id, status, priority, due_date):
        self.id = task_id
        self.title = title
        self.description = description
        self.project_id = project_id
        self.assignee_id = assignee_id
        self.status = status
        self.priority = priority
        self.due_date = due_date

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'project_id': self.project_id,
            'assignee_id': self.assignee_id,
            'status': self.status,
            'priority': self.priority,
            'due_date': self.due_date,
        }