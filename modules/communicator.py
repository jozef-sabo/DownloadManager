from db import db
import urllib.parse
import os
import random
import subprocess

PATH_STRUCTURE = "./modules/%s.out"
OUTPUT_PATH = "/home/user/ftp"
NOHUP_OUTPUT_PATH = OUTPUT_PATH + "/nohup"
UUID_CHARS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890"


def read_data(download_uuid: str) -> dict:
    download_uuid.replace(".", "")  # upper folder attack
    path_to_file = PATH_STRUCTURE % download_uuid

    with open(path_to_file, "r", encoding="UTF-8") as data_file:
        info_line = data_file.readlines()[-1]

    info_line.strip()
    #  % Total    % Received % Xferd  Average Speed   Time    Time     Time  Current
    #                                 Dload  Upload   Total   Spent    Left  Speed
    info_line_list = info_line.split()

    return {
        "data_percent": info_line_list[0],
        "data_total": info_line_list[1],
        "data_received": info_line_list[3],
        "time_total": info_line_list[8],
        "time_spent": info_line_list[9],
        "time_left": info_line_list[10],
        "speed_average": info_line_list[6],
        "speed_current": info_line_list[11]
    }


def struct_data_for_websocket(data: dict) -> dict:
    return {
        "speed": data["speed_current"],
        "downloaded": data["data_received"],
        "finished": True if data["data_percent"] == "100" else False
    }


def download(data):
    url_text = data["url"]
    # TODO: check if ../ working in curl
    url = urllib.parse.urlparse(url_text)
    if not url.scheme or url.scheme == "file":
        url = url._replace(scheme="http")

    filename = os.path.basename(url.path)
    url_text = url.geturl()

    add_entry_to_database(filename, url_text)


def create_uuid(size: int = 10) -> str:
    return "".join(random.sample(UUID_CHARS, size))


def execute_curl(url, name, uuid) -> int:
    if not os.path.isdir(NOHUP_OUTPUT_PATH):
        try:
            os.makedirs(NOHUP_OUTPUT_PATH)
        except Exception as e:
            return -1  # TODO: send beautiful message

    path_to_output_file = os.path.join(NOHUP_OUTPUT_PATH, uuid)
    path_to_file = os.path.join(OUTPUT_PATH, name)

    process = subprocess.Popen(
        f"nohup curl {path_to_file} {url} &",
        stdin=subprocess.DEVNULL,
        stdout=open(f"{path_to_output_file}.out", 'w'),
        stderr=subprocess.STDOUT,
        shell=True
    )

    return process.pid


def add_entry_to_database(name, url):
    connection = db.get_db()
    uuid = ""
    for _ in range(10):
        uuid_temp = create_uuid()

        entries = connection.execute("SELECT id FROM downloads WHERE uuid=?", (uuid_temp, )).fetchall()
        if not entries:
            uuid = uuid_temp
            break

    if not uuid:
        return

    pid = execute_curl(url, name, uuid)
    print(pid)
