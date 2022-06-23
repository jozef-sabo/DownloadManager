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

data_version = -1
files_structure = []
uuids_pids = []


def send_websocket():
    websocket_files = []
    for uuid_pid_num in range(len(uuids_pids)):
        uuid = uuids_pids[uuid_pid_num][0]
        file_data = communicator.read_data(uuid)

        websocket_data = communicator.struct_data_for_websocket(file_data)
        files_structure[uuid_pid_num]["downloaded"] = websocket_data["downloaded"]
        files_structure[uuid_pid_num]["speed"] = websocket_data["speed"]

        if files_structure[uuid_pid_num]["total"] != websocket_data["total"]\
                and files_structure[uuid_pid_num]["total"] == "0":
            files_structure[uuid_pid_num]["total"] = websocket_data["total"]
            pass

        del websocket_data["total"]
        websocket_files.append(websocket_data)

    websocket_data_to_send = get_websocket_data_dict(websocket_files)

    socketio.emit('downloading', websocket_data_to_send)


def create_sender():
    while True:
        send_websocket()
        eventlet.sleep(10)


def recreate_file_structure():
    global files_structure, uuids_pids, data_version
    files_structure, uuids_pids = communicator.get_files_structure()
    data_version += 1
    if not files_structure:
        data_version = -1


eventlet.spawn(create_sender)


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
    global data_version, files_structure, uuids_pids
    communicator.download(request.json)

    recreate_file_structure()

    response = Response(get_files_structure())
    response.headers["Content-Type"] = "application/json"

    return response


@app.route("/update_totals", methods=["GET"])
def update_totals():
    ids = request.json["ids"]
    response_dict = {"totals": {}}

    length = len(files_structure)
    for id_index in ids:
        if id_index < 0 or length < id_index:
            continue

        if files_structure[id_index] != "0":
            response_dict["totals"][str(id_index)] = files_structure[id_index]

    response = Response(response_dict)
    response.headers["Content-Type"] = "application/json"
    if not response_dict["total"]:
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
        recreate_file_structure()

    socketio.run(app, debug=True)
