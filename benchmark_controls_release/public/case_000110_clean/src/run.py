import os
from app import create_app, db

app = create_app()

if __name__ == "__main__":
    with app.app_context():
        if not os.path.exists(app.config["DATABASE_PATH"]):
            db.seed_data()
    app.run(host="0.0.0.0", port=9000, debug=False)