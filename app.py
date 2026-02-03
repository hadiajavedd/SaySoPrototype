from flask import Flask, request, session, redirect, jsonify, render_template, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from io import BytesIO
import qrcode
import base64
import json
from sqlalchemy import text

app = Flask(__name__)
# secret key is used for sessions (keeps users logged in)
app.secret_key = "dev-secret-key"
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///feedback.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# models for the database tables
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

    questionnaires = db.relationship(
        "Questionnaire",
        backref="user",
        cascade="all, delete"
    )

class Questionnaire(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_opened = db.Column(db.DateTime, default=datetime.utcnow)

    questions = db.relationship(
        "Question",
        backref="questionnaire",
        cascade="all, delete"
    )

    responses = db.relationship(
        "Response",
        backref="questionnaire",
        cascade="all, delete"
    )

class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(500), nullable=False)
    qtype = db.Column(db.String(20), nullable=False)
    questionnaire_id = db.Column(
        db.Integer,
        db.ForeignKey('questionnaire.id'),
        nullable=False
    )

class Response(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    questionnaire_id = db.Column(
        db.Integer,
        db.ForeignKey('questionnaire.id'),
        nullable=False
    )
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    answers_json = db.Column(db.Text, nullable=False)

# checks the database has the right columns (helps if an old db file exists)
def ensure_response_schema():
    """
    Makes sure the database has the columns we need for the Response table.
    This avoids breaking existing feedback.db files.
    """
    db.create_all()

    table_check = db.session.execute(
        text("SELECT name FROM sqlite_master WHERE type='table' AND name='response'")
    ).fetchone()

    if not table_check:
        return

    columns = db.session.execute(text("PRAGMA table_info(response)")).fetchall()
    column_names = [c[1] for c in columns]

    if "answers_json" not in column_names:
        db.session.execute(text("ALTER TABLE response ADD COLUMN answers_json TEXT"))
        db.session.commit()

    if "submitted_at" not in column_names:
        db.session.execute(text("ALTER TABLE response ADD COLUMN submitted_at DATETIME"))
        db.session.commit()


# runs the schema check once when the app starts
with app.app_context():
    ensure_response_schema()

# routes for pages
@app.route('/', methods=["GET", "POST"])
def login():
    # if user submits the login form
    if request.method == "POST":
        user = User.query.filter_by(
            username=request.form["username"],
            password=request.form["password"]
        ).first()

        # if login fails, just show login page again
        if not user:
            return render_template("login.html")

        # saves user info in session so they stay logged in
        session["user_id"] = user.id
        session["username"] = user.username
        return redirect("/homepage")

    return render_template("login.html")

@app.route("/signup", methods=["GET", "POST"])
def signup():
    # creates a new user account
    if request.method == "POST":
        if User.query.filter_by(username=request.form["username"]).first():
            return render_template("signup.html")

        db.session.add(User(
            username=request.form["username"],
            password=request.form["password"]
        ))
        db.session.commit()
        return redirect("/")

    return render_template("signup.html")

@app.route("/logout")
def logout():
    # clears session so user is logged out
    session.clear()
    return redirect("/")

@app.route("/delete-account", methods=["POST"])
def delete_account():
    # only logged in users can delete their account
    if "user_id" not in session:
        return redirect("/")

    user = User.query.get(session["user_id"])
    if user:
        db.session.delete(user)
        db.session.commit()

    session.clear()
    return redirect("/")

@app.route("/homepage")
def homepage():
    # blocks access if not logged in
    if "user_id" not in session:
        return redirect("/")
    return render_template("homepage.html")

@app.route("/profile")
def profile_page():
    if "user_id" not in session:
        return redirect("/")
    return render_template("profile.html")

@app.route("/create-questionnaire")
def create_questionnaire_page():
    if "user_id" not in session:
        return redirect("/")
    return render_template("create_questionnaire.html")

@app.route("/view-questionnaire/<int:id>")
def view_questionnaire_page(id):
    if "user_id" not in session:
        return redirect("/")

    q = Questionnaire.query.get(id)
    # makes sure the questionnaire exists and belongs to the user
    if not q or q.user_id != session["user_id"]:
        return "Questionnaire not found", 404

    # updates last opened time
    q.last_opened = datetime.utcnow()
    db.session.commit()

    return render_template("view_questionnaire.html", questionnaire=q)

@app.route("/edit-questionnaire/<int:id>")
def edit_questionnaire_page(id):
    if "user_id" not in session:
        return redirect("/")

    q = Questionnaire.query.get(id)
    if not q or q.user_id != session["user_id"]:
        return "Questionnaire not found", 404

    q.last_opened = datetime.utcnow()
    db.session.commit()

    return render_template("edit_questionnaire.html")

@app.route("/take-questionnaire/<int:id>", methods=["GET", "POST"])
def take_questionnaire_page(id):
    # this page can be accessed without logging in
    q = Questionnaire.query.get(id)
    if not q:
        return "Questionnaire not found", 404

    q.last_opened = datetime.utcnow()
    db.session.commit()

    # when someone submits answers
    if request.method == "POST":
        answers = {}
        questions_sorted = sorted(q.questions, key=lambda x: x.id)

        for ques in questions_sorted:
            key = f"q{ques.id}"
            answers[str(ques.id)] = request.form.get(key, "")

        # stores answers as json in the database
        r = Response(
            questionnaire_id=q.id,
            answers_json=json.dumps(answers)
        )
        db.session.add(r)
        db.session.commit()

        return render_template("thank_you.html", questionnaire=q)

    return render_template("take_questionnaire.html", questionnaire=q)

@app.route("/responses/<int:id>")
def view_responses_page(id):
    if "user_id" not in session:
        return redirect("/")

    q = Questionnaire.query.get(id)
    if not q or q.user_id != session["user_id"]:
        return "Questionnaire not found", 404

    # keeps questions in a consistent order
    questions_sorted = sorted(q.questions, key=lambda x: x.id)
    responses = Response.query.filter_by(questionnaire_id=id).order_by(Response.submitted_at.desc()).all()

    # builds rows for the template so each response matches the question order
    rows = []
    for r in responses:
        try:
            answers = json.loads(r.answers_json) if r.answers_json else {}
        except:
            answers = {}

        row = []
        for ques in questions_sorted:
            row.append(answers.get(str(ques.id), ""))
        rows.append({
            "submitted_at": r.submitted_at,
            "answers": row
        })

    return render_template("view_responses.html", questionnaire=q, questions=questions_sorted, responses=rows)

@app.route("/share/<int:id>")
def share_questionnaire_page(id):
    if "user_id" not in session:
        return redirect("/")

    q = Questionnaire.query.get(id)
    if not q or q.user_id != session["user_id"]:
        return "Questionnaire not found", 404

    # creates a public link to take the questionnaire
    share_url = url_for("take_questionnaire_page", id=id, _external=True)

    # makes a qr code image for the link
    qr = qrcode.QRCode(box_size=10, border=4)
    qr.add_data(share_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    # converts the qr image to base64 so it can be shown in html
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    qr_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

    return render_template(
        "share_questionnaire.html",
        qr_code=qr_base64,
        share_url=share_url,
        q_title=q.title
    )

@app.route("/help")
def help_page():
    if "user_id" not in session:
        return redirect("/")
    return render_template("help.html")

# api routes used by the frontend javascript
@app.route("/api/me")
def api_me():
    if "user_id" not in session:
        return jsonify({"error": "Not logged in"}), 401
    return jsonify({"username": session["username"]})

@app.route("/api/my-questionnaires")
def api_my_questionnaires():
    if "user_id" not in session:
        return jsonify([])

    return jsonify([
        {
            "id": q.id,
            "title": q.title,
            "created_at": q.created_at.isoformat(),
            "last_opened": q.last_opened.isoformat()
        }
        for q in Questionnaire.query.filter_by(user_id=session["user_id"])
    ])

@app.route("/api/questionnaire/<int:id>")
def api_get_questionnaire(id):
    q = Questionnaire.query.get(id)
    return jsonify({
        "title": q.title,
        "questions": [{"text": x.text, "qtype": x.qtype} for x in q.questions]
    })

@app.route("/api/questionnaire/<int:id>", methods=["PUT"])
def api_edit_questionnaire(id):
    q = Questionnaire.query.get(id)
    if not q or q.user_id != session.get("user_id"):
        return jsonify({"error": "Not found"}), 404

    # updates title and replaces the old questions
    data = request.get_json()
    q.title = data["title"]

    Question.query.filter_by(questionnaire_id=q.id).delete()
    for ques in data["questions"]:
        db.session.add(Question(
            text=ques["text"],
            qtype=ques["qtype"],
            questionnaire_id=q.id
        ))

    db.session.commit()
    return jsonify({"success": True})

@app.route("/api/questionnaires", methods=["POST"])
def api_create_questionnaire():
    # creates a questionnaire then adds its questions
    data = request.get_json()
    q = Questionnaire(title=data["title"], user_id=session["user_id"])
    db.session.add(q)
    db.session.commit()

    for ques in data["questions"]:
        db.session.add(Question(
            text=ques["text"],
            qtype=ques["qtype"],
            questionnaire_id=q.id
        ))

    db.session.commit()
    return jsonify({"id": q.id})

@app.route("/api/questionnaires/<int:id>", methods=["DELETE"])
def api_delete_questionnaire(id):
    # deletes questionnaire if it belongs to the logged in user
    q = Questionnaire.query.get(id)
    if q and q.user_id == session.get("user_id"):
        db.session.delete(q)
        db.session.commit()
        return jsonify({"success": True})
    return jsonify({"error": "Not found"}), 404

if __name__ == "__main__":
    app.run(debug=True)
