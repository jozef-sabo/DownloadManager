import json

from flask import Flask, render_template, request, Response
from flask_socketio import SocketIO, send, emit
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


def bg_emit():
    socketio.emit(
        'downloading',
        {
            "files_version": 0,
            "files": [
                {
                    "speed": "350k",
                    "downloaded": "13605M",
                    "finished": True
                },
                {
                    "speed": "15M",
                    "downloaded": "1763M",
                    "finished": False
                }
            ]
        }
    )


def listen():
    while True:
        bg_emit()
        eventlet.sleep(10)


eventlet.spawn(listen)


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

    files_structure, uuids_pids = communicator.get_files_structure()
    data_version += 1
    if not files_structure:
        data_version = -1

    response = Response(get_files_structure())
    response.headers["Content-Type"] = "application/json"

    return response


def get_files_structure() -> str:
    dict_files_structure = {
        "files_version": data_version,
        "files": files_structure
    }

    return json.dumps(dict_files_structure)


if __name__ == '__main__':
    with app.app_context():
        db.init_app(app)
    socketio.run(app, debug=True)
