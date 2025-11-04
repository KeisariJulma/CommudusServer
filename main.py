from flask import Flask, request, jsonify, Response, render_template
from flask_jwt_extended import (
    JWTManager, create_access_token, jwt_required, get_jwt_identity
)
import time, json
from threading import Lock
from sqlalchemy import create_engine, Column, Integer, String, Table, ForeignKey
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from werkzeug.security import generate_password_hash, check_password_hash

# ----------------- Database setup -----------------
Base = declarative_base()

user_groups = Table(
    "user_groups", Base.metadata,
    Column("user_id", ForeignKey("users.id"), primary_key=True),
    Column("group_id", ForeignKey("groups.id"), primary_key=True)
)

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)

    groups = relationship("Group", secondary=user_groups, back_populates="users")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Group(Base):
    __tablename__ = "groups"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)
    users = relationship("User", secondary=user_groups, back_populates="groups")

engine = create_engine("sqlite:///gps.db", echo=False)
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)

# ----------------- Flask app -----------------
app = Flask(__name__)
app.config["JWT_SECRET_KEY"] = "replace_with_a_secure_random_key"
jwt = JWTManager(app)

devices = {}
lock = Lock()
DEVICE_TIMEOUT = 30  # seconds

# ----------------- Helper functions -----------------
def get_or_create_user(session_db, name):
    user = session_db.query(User).filter_by(name=name).first()
    if not user:
        user = User(name=name, email=f"{name}@example.com", password_hash="")
        session_db.add(user)
        session_db.commit()
    return user

def get_or_create_group(session_db, name):
    group = session_db.query(Group).filter_by(name=name).first()
    if not group:
        group = Group(name=name)
        session_db.add(group)
        session_db.commit()
    return group

def assign_user_to_groups(session_db, username, group_names):
    user = get_or_create_user(session_db, username)
    for gname in group_names:
        group = get_or_create_group(session_db, gname)
        if group not in user.groups:
            user.groups.append(group)
    session_db.commit()

# ----------------- Auth routes -----------------
@app.route("/register", methods=["POST"])
def register():
    data = request.json or {}
    username = data.get("name")
    email = data.get("email")
    password = data.get("password")
    confirm_password = data.get("confirmPassword")

    if not username or not email or not password or not confirm_password:
        return jsonify({"status": "ERROR", "message": "Missing fields"}), 400
    if password != confirm_password:
        return jsonify({"status": "ERROR", "message": "Passwords do not match"}), 400

    session_db = Session()
    if session_db.query(User).filter((User.name == username) | (User.email == email)).first():
        session_db.close()
        return jsonify({"status": "ERROR", "message": "Username or email already exists"}), 400

    user = User(name=username, email=email)
    user.set_password(password)
    session_db.add(user)
    session_db.commit()
    session_db.close()

    return jsonify({"status": "OK", "username": username})

@app.route("/login", methods=["POST"])
def login():
    data = request.json or {}
    identifier = data.get("identifier")
    password = data.get("password")

    if not identifier or not password:
        return jsonify({"status": "ERROR", "message": "Missing fields"}), 400

    session_db = Session()
    user = session_db.query(User).filter(
        (User.name == identifier) | (User.email == identifier)
    ).first()
    session_db.close()

    if not user or not user.check_password(password):
        return jsonify({"status": "ERROR", "message": "Invalid credentials"}), 400

    access_token = create_access_token(identity=user.name)
    return jsonify({"status": "OK", "username": user.name, "token": access_token})

# ----------------- Location routes -----------------
@app.route("/location", methods=["POST"])
@jwt_required()
def receive_location():
    data = request.json or {}
    name = get_jwt_identity()
    groups = data.get("groups")
    if not groups:
        return jsonify({"status": "ERROR", "message": "Missing groups"}), 400

    session_db = Session()
    assign_user_to_groups(session_db, name, groups)
    session_db.close()

    timestamp = time.time()
    with lock:
        devices[name] = {
            "id": name,
            "lat": data.get("latitude") or data.get("lat"),
            "lon": data.get("longitude") or data.get("lon"),
            "heading": data.get("heading"),
            "timestamp": timestamp,
            "name": name,
            "groups": groups
        }

    return jsonify({"status": "OK"})

@app.route("/location/stop", methods=["POST"])
@jwt_required()
def stop_sharing():
    name = get_jwt_identity()
    with lock:
        devices.pop(name, None)
    return jsonify({"status": "OK"})


@app.route("/stream")
def stream():
    token = request.args.get("token")
    if not token:
        return jsonify({"msg": "Missing token"}), 401

    try:
        decoded = decode_token(token)
    except Exception:
        return jsonify({"msg": "Invalid token"}), 401

    user = decoded.get("sub")

    def event_stream():
        last_state = ""
        while True:
            now = time.time()
            with lock:
                to_remove = [name for name, dev in devices.items() if now - dev["timestamp"] > DEVICE_TIMEOUT]
                for name in to_remove:
                    devices.pop(name)

                current_state = json.dumps(devices)

            if current_state != last_state:
                last_state = current_state
                yield f"data: {current_state}\n\n"

            time.sleep(1)

    print(f"✅ Stream opened for {user}")
    return Response(event_stream(), mimetype="text/event-stream")

# ----------------- Group Management -----------------
@app.route("/groups/create", methods=["POST"])
@jwt_required()
def create_group():
    data = request.json or {}
    group_name = data.get("name")
    if not group_name:
        return jsonify({"status": "ERROR", "message": "Missing group name"}), 400

    session_db = Session()
    if session_db.query(Group).filter_by(name=group_name).first():
        session_db.close()
        return jsonify({"status": "ERROR", "message": "Group already exists"}), 400

    group = Group(name=group_name)
    session_db.add(group)
    session_db.commit()
    session_db.close()
    return jsonify({"status": "OK", "group": group_name})

@app.route("/groups", methods=["GET"])
@jwt_required()
def list_groups():
    session_db = Session()
    groups = [g.name for g in session_db.query(Group).all()]
    session_db.close()
    return jsonify(groups)

@app.route("/groups/add_user", methods=["POST"])
@jwt_required()
def add_user_to_group():
    data = request.json or {}
    username = data.get("username")
    group_name = data.get("group")
    if not username or not group_name:
        return jsonify({"status": "ERROR", "message": "Missing username or group"}), 400

    session_db = Session()
    user = get_or_create_user(session_db, username)
    group = get_or_create_group(session_db, group_name)
    if group not in user.groups:
        user.groups.append(group)
        session_db.commit()
    session_db.close()
    return jsonify({"status": "OK", "user": username, "group": group_name})

# ----------------- Frontend pages -----------------
@app.route("/map")
def map():
    return render_template("map.html")

# ----------------- Main -----------------
if __name__ == "__main__":
    print("🌍 GPS server running with JWT authentication")
    app.run(host="0.0.0.0", port=5000, debug=True)
