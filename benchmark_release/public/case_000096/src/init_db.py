import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

DATABASE_PATH = os.environ.get('DATABASE_PATH', '/app/data/pulsecheck.db')

os.makedirs(os.path.dirname(DATABASE_PATH) if os.path.dirname(DATABASE_PATH) else '.', exist_ok=True)

from models import db_init, seed_data

db_init(DATABASE_PATH)
seed_data(DATABASE_PATH)
print('Database initialized and seeded successfully')