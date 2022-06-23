from db import db
import urllib.parse
import os
import random
import subprocess
import time

PATH_STRUCTURE = "./modules/%s.out"
OUTPUT_PATH = "/home/user/ftp"
NOHUP_OUTPUT_PATH = OUTPUT_PATH + "/nohup"
UUID_CHARS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890"
STARTUP_TIME_FILE = ".startup_time"


def read_data(download_uuid: str) -> dict:
    download_uuid.replace(".", "")  # upper folder attack
    path_to_file = f"{NOHUP_OUTPUT_PATH}/{download_uuid}.out"

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
        "finished": True if data["data_percent"] == "100" else False,
        "available_for_unzip": False,  # TODO: available to unzip,
        "total": data["data_total"]
    }


def struct_data_for_reinit(status: int, name: str, total: str, url: str, running: bool, data: dict) -> dict:
    finished = True if 2 < status < 5 else False
    available_to_unzip = True if status == 4 else False

    return {
        "title": name,
        "total": total,
        "downloaded": data["data_received"],
        "speed": data["speed_current"],
        "finished": finished,
        "available_for_unzip": available_to_unzip,
        "running": running,
        "url": url
    }


def is_process_running(pid: int):
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    else:
        return True


def get_files_structure():
    connection = db.get_db()
    all_files = connection.execute("SELECT name, total, status, uuid, url, pid, running FROM downloads").fetchall()

    array_files = []
    array_uuids_pids = []
    for file in all_files:
        name = file[0]
        total = file[1]
        status = file[2]
        uuid = file[3]
        url = file[4]
        pid = file[5]
        running = True if file[6] == 1 else False
        uuid_pid = [uuid, pid]
        array_uuids_pids.append(uuid_pid)

        if running:
            running = is_process_running(pid)

        actual_data = read_data(uuid)
        if actual_data["data_percent"] == "100" and status < 3:
            status = 3
            connection.execute("UPDATE downloads SET status = ?, running = ? WHERE uuid = ?", (status, int(running),
                                                                                               uuid))
            connection.commit()

        dict_file = struct_data_for_reinit(status, name, total, url, running, actual_data)
        array_files.append(dict_file)

    return array_files, array_uuids_pids


def process_uptime_date():
    process = subprocess.check_output(["who", "-b"])
    startup_time_str = process.decode("UTF-8").strip()
    last_startup_time_str = ""

    if os.path.isfile(STARTUP_TIME_FILE):
        with open(STARTUP_TIME_FILE, "r") as startup_time_file:
            last_startup_time = startup_time_file.readlines()
            if len(last_startup_time) > 0:
                last_startup_time_str = last_startup_time[0]

    if last_startup_time_str != startup_time_str:
        connection = db.get_db()
        connection.execute("UPDATE downloads SET running = ? WHERE 1", (0,))
        connection.commit()

        with open(STARTUP_TIME_FILE, "w") as startup_time_file:
            startup_time_file.write(startup_time_str)


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
        f"nohup curl -Lo {path_to_file} {url} &",
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
    time.sleep(0.1)
    data = read_data(uuid)

    connection.execute("INSERT INTO downloads(uuid, name, total, status, url, pid) VALUES (?, ?, ?, ?, ?, ?)",
                       (uuid, name, data["data_total"], 0, url, pid))
    connection.commit()


def edit_total_in_database(new_total: str, uuid: str):
    connection = db.get_db()
    connection.execute("UPDATE downloads SET total = ? WHERE uuid = ?", (new_total, uuid))
    connection.commit()


def edit_status_in_database(new_status: int, uuid: str):
    connection = db.get_db()
    connection.execute("UPDATE downloads SET status = ? WHERE uuid = ?", (new_status, uuid))
    connection.commit()
