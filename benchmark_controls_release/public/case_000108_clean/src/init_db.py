import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from app.models import db_init, create_user, create_project, get_user_by_username

def seed():
    db_init()

    users = [
        ('alice', 'AlicePass123!', 'Alice Mercer', 'user'),
        ('bob', 'BobPass123!', 'Bob Keller', 'user'),
        ('charlie', 'CharliePass123!', 'Charlie Voss', 'user'),
        ('diana', 'DianaPass456!', 'Diana Okonkwo', 'user'),
        ('evan', 'EvanPass789!', 'Evan Strand', 'admin'),
    ]

    for username, password, display_name, role in users:
        if not get_user_by_username(username):
            create_user(username, password, display_name, role)
            print(f'Created user: {username}')

    from app.models import get_user_by_username as gub, get_db
    alice = gub('alice')
    bob = gub('bob')
    charlie = gub('charlie')
    diana = gub('diana')
    evan = gub('evan')

    sample_projects = [
        (alice.id, 'Website Redesign', 'Revamp the corporate site with new branding'),
        (alice.id, 'Mobile App MVP', 'Build iOS/Android app for Q3 launch'),
        (alice.id, 'Data Pipeline', 'ETL pipeline for analytics warehouse'),
        (bob.id, 'API Integration', 'Connect third-party payment gateway'),
        (bob.id, 'Reporting Dashboard', 'Executive KPI dashboard with live data'),
        (charlie.id, 'DevOps Automation', 'CI/CD pipeline setup with Docker'),
        (charlie.id, 'Security Audit', 'Quarterly review of access controls'),
        (charlie.id, 'Customer Portal', 'Self-service portal for enterprise clients'),
        (diana.id, 'ML Model Training', 'Train recommendation engine on user data'),
        (diana.id, 'Content Moderation', 'Automated flagging system for UGC'),
        (evan.id, 'Platform Monitoring', 'SRE dashboards and alert configuration'),
        (evan.id, 'Compliance Tooling', 'GDPR/SOC2 audit log tooling'),
    ]

    conn = get_db()
    existing = conn.execute('SELECT COUNT(*) FROM projects').fetchone()[0]
    conn.close()

    if existing == 0:
        for owner_id, name, desc in sample_projects:
            create_project(owner_id, name, desc)
        print(f'Seeded {len(sample_projects)} projects')

    print('Database initialization complete.')

if __name__ == '__main__':
    seed()