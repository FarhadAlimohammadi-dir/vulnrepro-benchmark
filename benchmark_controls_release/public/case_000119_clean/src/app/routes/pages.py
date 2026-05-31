from flask import Blueprint, render_template, send_from_directory
import os

pages_bp = Blueprint('pages', __name__)


@pages_bp.route('/')
def index():
    return render_template('index.html')


@pages_bp.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')


@pages_bp.route('/health')
def health():
    return {'status': 'ok', 'service': 'projecthub'}, 200