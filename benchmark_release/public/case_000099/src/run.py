import os
from app import create_app, init_db

app = create_app()

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 9000))
    app.run(host='0.0.0.0', port=port, debug=False)