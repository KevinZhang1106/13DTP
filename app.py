from flask import Flask, render_template, url_for, redirect, request
from flask_sqlalchemy import SQLAlchemy

from dotenv import load_dotenv
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from authlib.integrations.flask_client import OAuth
import os
from werkzeug.utils import secure_filename
from datetime import datetime, timezone


load_dotenv()


app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///marketplace.db"

UPLOAD_FOLDER = os.path.join("static", "uploads")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


db = SQLAlchemy(app)


app.secret_key = os.getenv("SECRET_KEY")
login_manager = LoginManager(app)
login_manager.login_view = "google_login"

oauth = OAuth(app)
google = oauth.register(
    name="google",
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},

)

favourites_table = db.Table(
    "favourites",
    db.Column("user_id", db.Integer, db.ForeignKey("user.id"), primary_key=True),
    db.Column("listing_id", db.Integer, db.ForeignKey("listing.id"), primary_key=True),
)


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    google_id = db.Column(db.String(128), unique=True, nullable=False)
    name = db.Column(db.String(128), nullable=False)
    email = db.Column(db.String(256), nullable=True)
    listings = db.relationship("Listing", backref="seller")
    favourites = db.relationship("Listing", secondary=favourites_table)
    

class Listing(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    price = db.Column(db.Float, nullable=False)
    location = db.Column(db.String(200), nullable=False)
    image_filename = db.Column(db.String(256))


@app.route('/')
def home():
    search = request.args.get("search", "").strip()

    if search:
        listings = Listing.query.filter(    
            db.or_(
                Listing.title.ilike(f"%{search}%"),
                Listing.description.ilike(f"%{search}%"),
                Listing.location.ilike(f"%{search}%"),
            )
        ).all()
    else:
        listings = Listing.query.all()

    return render_template("home.html", listings=listings, search=search)


@app.route('/create-listing', methods=["GET", "POST"])
@login_required
def create_listing():
    if request.method == "POST":
        title = request.form.get("title")
        description = request.form.get("description")
        price = request.form.get("price")
        location = request.form.get("location")
        image = request.files.get("image")

        image_filename = None
        if image and allowed_file(image.filename):
            filename = secure_filename(image.filename)
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
            image_filename = f"{timestamp}_{filename}"
            image.save(os.path.join(app.config["UPLOAD_FOLDER"], image_filename))

        listing = Listing(
            title=title,
            description=description,
            price=float(price),
            location=location,
            image_filename=image_filename,
            user_id=current_user.id
        )
        db.session.add(listing)
        db.session.commit()
        return redirect(url_for("home"))

    return render_template('create_listing.html')


@app.route('/edit-listing/<int:listing_id>', methods=["GET", "POST"])
@login_required
def edit_listing(listing_id):
    listing = Listing.query.get(listing_id)

    if listing.user_id != current_user.id:
        return redirect(url_for('home'))
    
    if request.method == "POST":
        listing.title = request.form.get("title")
        listing.description = request.form.get("description")
        listing.price = float(request.form.get("price"))
        listing.location = request.form.get("location")

        image = request.files.get("image")
        if image and allowed_file(image.filename):
            filename = secure_filename(image.filename)
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
            listing.image_filename = f"{timestamp}_{filename}"
            image.save(os.path.join(app.config["UPLOAD_FOLDER"], listing.image_filename))

        db.session.commit()
        return redirect(url_for('my_listing'))
    
    return render_template('edit_listing.html', listing=listing)


@app.route('/delete-listing/<int:listing_id>', methods=["POST"])
@login_required
def delete_listing(listing_id):
    listing = Listing.query.get(listing_id)

    if listing.user_id != current_user.id:
        return redirect(url_for("home"))
    
    db.session.delete(listing)
    db.session.commit()
    return redirect(url_for("my_listing"))


@app.route('/my-listing')
@login_required
def my_listing():
    listings = Listing.query.filter_by(user_id=current_user.id).all()
    return render_template('my_listing.html', listings=listings)


@app.route('/listing/<int:listing_id>')
def view_listing(listing_id):
    listing = Listing.query.get_or_404(listing_id)
    return render_template('view_listing.html', listing=listing)


@app.route('/favourites')
@login_required
def favourites():
    listings = current_user.favourites
    return render_template('favourites.html', listings=listings)


@app.route('/listing/<int:listing_id>/favourite', methods=["POST"])
@login_required
def toggle_favourite(listing_id):
    listing = Listing.query.get(listing_id)

    if listing in current_user.favourites:
        current_user.favourites.remove(listing)
    else:
        current_user.favourites.append(listing)

    db.session.commit()
    return redirect(url_for('view_listing', listing_id=listing_id))


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.route("/auth/google")
def google_login():
    redirect_uri = url_for("google_callback", _external=True)
    return google.authorize_redirect(redirect_uri)


@app.route("/auth/callback")
def google_callback():
    token = google.authorize_access_token()
    userinfo = token.get("userinfo")
    google_id = userinfo["sub"]
    user = User.query.filter_by(google_id=google_id).first()
    if not user:
        user = User(
            google_id=google_id,
            name=userinfo.get("name", "User"),
            email=userinfo.get("email"),
        )
        db.session.add(user)
        db.session.commit()

    login_user(user)
    return redirect(url_for("home"))


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("home"))


with app.app_context():
    db.create_all()


if __name__ == "__main__":
    app.run(debug=True)