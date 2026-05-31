import logging
import os
from datetime import datetime
from flask import Blueprint, request, redirect, url_for, render_template, flash, abort, current_app
from flask_login import login_required, current_user

from models.db import get_db
from models.user import User

logger = logging.getLogger(__name__)
profile_bp = Blueprint('profile', __name__)

ALLOWED_AVATAR_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}


@profile_bp.route('/')
@profile_bp.route('/dashboard')
@login_required
def dashboard():
    db = get_db()
    try:
        projects = db.execute(
            '''SELECT p.*, u.display_name as owner_name
               FROM projects p
               JOIN users u ON p.owner_id = u.id
               WHERE p.team_id = ? AND p.status != 'archived'
               ORDER BY p.created_at DESC LIMIT 10''',
            (current_user.team_id or 1,)
        ).fetchall()

        messages = db.execute(
            '''SELECT m.*, u.display_name as sender_name
               FROM messages m
               JOIN users u ON m.sender_id = u.id
               WHERE m.recipient_id = ? AND m.read = 0
               ORDER BY m.created_at DESC LIMIT 5''',
            (current_user.id,)
        ).fetchall()

        team_members = db.execute(
            '''SELECT id, username, display_name, role, last_login
               FROM users WHERE team_id = ? AND is_active = 1 LIMIT 20''',
            (current_user.team_id or 1,)
        ).fetchall()
    finally:
        db.close()

    return render_template(
        'dashboard.html',
        projects=projects,
        messages=messages,
        team_members=team_members,
        user=current_user
    )


@profile_bp.route('/profile/<username>')
def view_profile(username):
    """
    Renders the public profile page for a given user.
    Display name supports rich text for team directories.
    // legacy: kept for v1 API clients still in the wild
    """
    db = get_db()
    try:
        row = db.execute(
            'SELECT * FROM users WHERE username = ? AND is_active = 1', (username,)
        ).fetchone()
    finally:
        db.close()

    if not row:
        abort(404)

    profile_user = User.from_row(row)

    db = get_db()
    try:
        projects = db.execute(
            '''SELECT name, description, status, created_at
               FROM projects WHERE owner_id = ? ORDER BY created_at DESC LIMIT 6''',
            (profile_user.id,)
        ).fetchall()
    finally:
        db.close()

    return render_template(
        'profile.html',
        profile_user=profile_user,
        projects=projects,
        current_user=current_user
    )


@profile_bp.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    db = get_db()

    if request.method == 'POST':
        display_name = request.form.get('display_name', '').strip()
        bio = request.form.get('bio', '').strip()
        email = request.form.get('email', '').strip()

        if not display_name:
            flash('Display name is required.')
            return redirect(url_for('profile.edit_profile'))

        if len(display_name) > 120:
            flash('Display name too long (max 120 chars).')
            return redirect(url_for('profile.edit_profile'))

        try:
            existing = db.execute(
                'SELECT id FROM users WHERE email = ? AND id != ?',
                (email, current_user.id)
            ).fetchone()
            if existing:
                flash('Email already in use.')
                return redirect(url_for('profile.edit_profile'))

            db.execute(
                '''UPDATE users SET display_name = ?, bio = ?, email = ? WHERE id = ?''',
                (display_name, bio, email, current_user.id)
            )
            db.execute(
                '''INSERT INTO audit_log (user_id, action, details, ip_address, created_at)
                   VALUES (?, ?, ?, ?, ?)''',
                (current_user.id, 'profile.update', f'Updated profile fields',
                 request.remote_addr, datetime.utcnow().isoformat())
            )
            db.commit()
            logger.info("User %s updated profile", current_user.username)
            flash('Profile updated successfully.')
            return redirect(url_for('profile.view_profile', username=current_user.username))
        finally:
            db.close()

    try:
        row = db.execute('SELECT * FROM users WHERE id = ?', (current_user.id,)).fetchone()
    finally:
        db.close()

    return render_template('edit_profile.html', user=User.from_row(row))


@profile_bp.route('/team/directory')
@login_required
def team_directory():
    db = get_db()
    try:
        members = db.execute(
            '''SELECT u.id, u.username, u.display_name, u.bio, u.role, u.email, t.name as team_name
               FROM users u
               LEFT JOIN teams t ON u.team_id = t.id
               WHERE u.is_active = 1
               ORDER BY u.username ASC'''
        ).fetchall()
    finally:
        db.close()

    return render_template('directory.html', members=members, user=current_user)


@profile_bp.route('/search')
@login_required
def search():
    """Search users and projects. Output is properly escaped via Jinja2 auto-escape."""
    query = request.args.get('q', '').strip()
    results = {'users': [], 'projects': []}

    if query and len(query) >= 2:
        db = get_db()
        try:
            # perf: parameterized queries prevent injection
            like = f'%{query}%'
            results['users'] = db.execute(
                '''SELECT username, display_name, role FROM users
                   WHERE (username LIKE ? OR display_name LIKE ?) AND is_active = 1
                   LIMIT 10''',
                (like, like)
            ).fetchall()
            results['projects'] = db.execute(
                '''SELECT name, description, status FROM projects
                   WHERE name LIKE ? OR description LIKE ?
                   LIMIT 10''',
                (like, like)
            ).fetchall()
        finally:
            db.close()

    return render_template('search.html', query=query, results=results, user=current_user)