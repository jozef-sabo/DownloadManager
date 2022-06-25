import json

from flask import Flask, render_template, request, Response
from flask_socketio import SocketIO
import eventlet
from db import db
from modules import communicator

eventlet.monkey_patch()

app = Flask(__name__)
app.config['SECRET_KEY'] = "SecretKeyForFlaskApplicationMadeByJefinko"
app.config['DATABASE'] = "db/db"
socketio = SocketIO(app, cors_allowed_origins="*")

COMPUTER_RESTARTED = False
data_version = -1
files_structure = []
not_for_user = []


def send_websocket():
    websocket_files = []
    for not_for_user_num in range(len(not_for_user)):
        changed = False
        uuid = not_for_user[not_for_user_num][0]
        pid = not_for_user[not_for_user_num][1]
        is_orphan = not_for_user[not_for_user_num][2]
        title = files_structure[not_for_user_num]["title"]
        if is_orphan:
            websocket_files.append({"status": communicator.get_status(
                title, False, "100", files_structure[not_for_user_num]["total"])})
            continue

        status = files_structure[not_for_user_num]["status"]
        if status > 2:
            websocket_files.append({"status": status})
            continue

        file_data = communicator.read_data(uuid)

        if status < 3:
            status = communicator.get_status(
                title, communicator.is_process_running(pid), file_data["percent"], file_data["data_total"])
            if status != files_structure[not_for_user_num]["status"]:
                files_structure[not_for_user_num]["status"] = status
                changed = True

        websocket_data, total = communicator.struct_data_for_websocket(file_data, status)
        files_structure[not_for_user_num]["downloaded"] = websocket_data["downloaded"]
        files_structure[not_for_user_num]["speed"] = websocket_data["speed"]

        if files_structure[not_for_user_num]["total"] != total and files_structure[not_for_user_num]["total"] == "0":
            files_structure[not_for_user_num]["total"] = total
            changed = True

        if changed:
            with app.app_context():
                communicator.edit_status_total_in_database(status, total, uuid)

        websocket_files.append(websocket_data)
    websocket_data_to_send = get_websocket_data_dict(websocket_files)
    socketio.emit('downloading', websocket_data_to_send)


def create_sender():
    while True:
        send_websocket()
        eventlet.sleep(10)


def recreate_file_structure(count_on_with_restart=False):
    global files_structure, not_for_user, data_version
    files_structure, not_for_user = communicator.get_files_structure(count_on_with_restart)
    data_version += 1
    if not files_structure:
        data_version = -1


@socketio.on('message')
def handle_message(data):
    print('received message: ' + data)


@app.route('/')
def index():
    return render_template("index.html")


@app.route("/init", methods=["GET"])
def initialize():
    response = Response(get_files_structure())
    response.headers["Content-Type"] = "application/json"

    return response


@app.route('/download', methods=["POST"])
def download():
    global data_version, files_structure, not_for_user
    communicator.download(request.json)
    recreate_file_structure()

    response = Response(get_files_structure())
    response.headers["Content-Type"] = "application/json"

    return response


@app.route("/update_totals", methods=["POST"])
def update_totals():
    ids = request.json["ids"]
    response_dict = {"totals": {}}

    length = len(files_structure)
    for id_index in ids:
        if id_index < 0 or length < id_index:
            continue

        if files_structure[id_index]["total"] != "0":
            response_dict["totals"][str(id_index)] = files_structure[id_index]["total"]

    response = Response(json.dumps(response_dict))
    response.headers["Content-Type"] = "application/json"
    if not response_dict["totals"]:
        response.status = 204

    return response


def get_files_structure() -> str:
    dict_files_structure = {
        "files_version": data_version,
        "files": files_structure
    }

    return json.dumps(dict_files_structure)


def get_websocket_data_dict(files_data: list) -> dict:
    dict_websocket_data = {
        "files_version": data_version,
        "files": files_data
    }

    return dict_websocket_data


if __name__ == '__main__':
    with app.app_context():
        db.init_app(app)
        COMPUTER_RESTARTED = communicator.was_restarted()
        recreate_file_structure(COMPUTER_RESTARTED)
    eventlet.spawn(create_sender)
    socketio.run(app, debug=True)
