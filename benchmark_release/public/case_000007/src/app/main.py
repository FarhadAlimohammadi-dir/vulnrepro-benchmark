import os
from app import create_app
from db import init_db

if __name__ == "__main__":
    init_db()
    application = create_app()
    application.run(host="0.0.0.0", port=9000, debug=False)