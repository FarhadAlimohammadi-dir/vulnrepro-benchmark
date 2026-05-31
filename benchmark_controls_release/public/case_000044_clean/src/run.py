import os
from app import create_app
from app.database import init_db

app = create_app()

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=9000, debug=False)