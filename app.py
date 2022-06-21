from flask import Flask

app = Flask(__name__)


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
    app.run()
