import json

from flask import Flask, render_template, request, Response
from flask_socketio import SocketIO, send, emit
import eventlet
# from db import db

eventlet.monkey_patch()

app = Flask(__name__)
app.config['SECRET_KEY'] = "SecretKeyForFlaskApplicationMadeByJefinko"
app.config['DATABASE'] = "db/flask_db"
socketio = SocketIO(app)


def bg_emit():
    socketio.emit(
        'downloading',
        {
            "files_version": 0,
            "files": [
                {
                    "speed": "350k",
                    "downloaded": "105M"
                },
                {
                    "speed": "15M",
                    "downloaded": "1263M"
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
    response = Response(json.dumps(
        {
            "files_version": 0,
            "files": [
                {
                    "title": "Filename.mp4",
                    "total": "1955M",
                    "downloaded": "350M",
                    "speed": "105M"
                },
                {
                    "title": "Filename2.mp4",
                    "total": "2555M",
                    "downloaded": "2336M",
                    "speed": "105M"
                }
            ]
        }
    ))
    response.headers["Content-Type"] = "application/json"
    return response


@app.route('/download', methods=["POST"])
def download():
    request.json["aaa"] = "abcab"

    return request.json


if __name__ == '__main__':
    socketio.run(app, debug=True)
