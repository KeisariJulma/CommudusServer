from flask import Flask, request, jsonify, Response, render_template
import time, json
from threading import Lock
from sqlalchemy import create_engine, Column, Integer, String, Table, ForeignKey
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

# ----------------- Database setup -----------------
Base = declarative_base()

# Many-to-many association table
user_groups = Table(
    "user_groups", Base.metadata,
    Column("user_id", ForeignKey("users.id"), primary_key=True),
    Column("group_id", ForeignKey("groups.id"), primary_key=True)
)

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)
    groups = relationship("Group", secondary=user_groups, back_populates="users")

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
devices = {}  # In-memory device locations
lock = Lock()
DEVICE_TIMEOUT = 30  # seconds

# ----------------- DB helper functions -----------------
def get_or_create_user(session, name):
    user = session.query(User).filter_by(name=name).first()
    if not user:
        user = User(name=name)
        session.add(user)
        session.commit()
    return user

def get_or_create_group(session, name):
    group = session.query(Group).filter_by(name=name).first()
    if not group:
        group = Group(name=name)
        session.add(group)
        session.commit()
    return group

def assign_user_to_groups(session, username, group_names):
    user = get_or_create_user(session, username)
    for gname in group_names:
        group = get_or_create_group(session, gname)
        if group not in user.groups:
            user.groups.append(group)
    session.commit()

# ----------------- Routes -----------------
@app.route("/location", methods=["POST"])
def receive_location():
    """Receive location update from a device"""
    data = request.json or {}
    name = data.get("name")
    groups = data.get("groups")
    if not name or not groups:
        return jsonify({"status": "ERROR", "message": "Missing name or groups"}), 400

    # Store user-group info in DB
    session = Session()
    assign_user_to_groups(session, name, groups)
    session.close()

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
def stop_sharing():
    """Device stops sharing location"""
    data = request.json or {}
    name = data.get("name")
    if not name:
        return jsonify({"status": "ERROR", "message": "Missing device name"}), 400

    with lock:
        if name in devices:
            devices.pop(name)
            print(f"[STOP] Device {name} removed")

    return jsonify({"status": "OK"})

@app.route("/stream")
def stream():
    """SSE stream for a specific group"""
    group = request.args.get("group")
    if not group:
        return "Missing 'group' parameter", 400

    def event_stream():
        last_state = ""
        while True:
            now = time.time()
            with lock:
                # Remove inactive devices
                to_remove = [name for name, dev in devices.items() if now - dev["timestamp"] > DEVICE_TIMEOUT]
                for name in to_remove:
                    devices.pop(name)

                # Only send devices in the requested group
                filtered = {name: dev for name, dev in devices.items() if group in dev.get("groups", [])}
                current_state = json.dumps(filtered)

            if current_state != last_state:
                last_state = current_state
                yield f"data: {current_state}\n\n"

            time.sleep(1)

    return Response(event_stream(), mimetype="text/event-stream")

@app.route("/map")
def show_map():
    """Simple map page"""
    return render_template("map.html")

# ----------------- Group Management Endpoints -----------------
@app.route("/groups/create", methods=["POST"])
def create_group():
    data = request.json or {}
    group_name = data.get("name")
    if not group_name:
        return jsonify({"status": "ERROR", "message": "Missing group name"}), 400

    session = Session()
    group = session.query(Group).filter_by(name=group_name).first()
    if group:
        session.close()
        return jsonify({"status": "ERROR", "message": "Group already exists"}), 400

    group = Group(name=group_name)
    session.add(group)
    session.commit()
    session.close()
    return jsonify({"status": "OK", "group": group_name})

@app.route("/groups", methods=["GET"])
def list_groups():
    session = Session()
    groups = [g.name for g in session.query(Group).all()]
    session.close()
    return jsonify(groups)

@app.route("/groups/add_user", methods=["POST"])
def add_user_to_group():
    data = request.json or {}
    username = data.get("username")
    group_name = data.get("group")

    if not username or not group_name:
        return jsonify({"status": "ERROR", "message": "Missing username or group"}), 400

    session = Session()
    user = get_or_create_user(session, username)
    group = get_or_create_group(session, group_name)

    if group not in user.groups:
        user.groups.append(group)
        session.commit()

    session.close()
    return jsonify({"status": "OK", "user": username, "group": group_name})

# ----------------- Main -----------------
if __name__ == "__main__":
    print("🌍 GPS server running: multi-group support")
    app.run(host="0.0.0.0", port=5000, debug=True)
