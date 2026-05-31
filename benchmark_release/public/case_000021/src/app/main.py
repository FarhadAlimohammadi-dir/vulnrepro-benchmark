import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.db import init_db
from app.factory import create_app

if __name__ == '__main__':
    init_db()
    application = create_app()
    port = int(os.environ.get('PORT', 9000))
    application.run(host='0.0.0.0', port=port)

init_db()
application = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 9000))
    application.run(host='0.0.0.0', port=port)