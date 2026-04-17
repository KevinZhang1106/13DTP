from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///marketplace.db"

db = SQLAlchemy(app)


favourites_table = db.Table(
    "favourites",
    db.Column("user_id", db.Integer, db.ForeignKey("user.user_id"), primary_key=True),
    db.Column("listing_id", db.Integer, db.ForeignKey("listing.listing_id"), primary_key=True),
)


class User(db.Model):
    user_id = db.Column(db.Integer, primary_key=True)
    google_id = db.Column(db.String(128), unique=True, nullable=False)
    name = db.Column(db.String(128), nullable=False)


class Listing(db.Model):
    listing_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.user_id"))
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    price = db.Column(db.Float, nullable=False)
    location = db.Column(db.String(200), nullable=False)
    image_filename = db.Column(db.String(256))


@app.route('/')
def login():
    return render_template("login.html")


with app.app_context():
    db.create_all()


if __name__ == "__main__":
    app.run(debug=True)