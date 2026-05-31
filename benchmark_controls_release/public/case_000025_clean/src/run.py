from app import create_app
from app.models.database import init_db, seed_data

app = create_app()

if __name__ == "__main__":
    with app.app_context():
        init_db()
        seed_data()
    app.run(host="0.0.0.0", port=9000, debug=False)