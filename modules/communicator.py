from db import db
import urllib.parse
import os
import random
import subprocess
import time

OUTPUT_PATH = "/home/user/ftp"
NOHUP_OUTPUT_PATH = OUTPUT_PATH + "/nohup"
UUID_CHARS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890"
STARTUP_TIME_FILE = ".startup_time"


def read_data(download_uuid: str) -> dict:
    download_uuid.replace(".", "")  # upper folder attack
    path_to_file = f"{NOHUP_OUTPUT_PATH}/{download_uuid}.out"

    if not os.path.isfile(path_to_file):
        return {"data_percent": False}

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


def struct_data_for_websocket(data: dict, status: int) -> tuple:
    return {
        "status": status,
        "speed": data["speed_current"],
        "downloaded": data["data_received"]
    }, data["data_total"]


def struct_data_for_reinit(status: int, name: str, total: str, url: str, data: dict) -> dict:
    return {
        "status": status,
        "title": name,
        "total": total,
        "downloaded": data["data_received"],
        "speed": data["speed_current"],
        "url": url
    }


def is_process_running(pid: int):
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    else:
        return True


def get_status(name: str, running: bool, percent: str, total: str):
    status = 5
    if running:
        status = 1
        if percent != "0":
            status = 2
    if percent == "100":
        status = 3
        if name.endswith(".zip") or name.endswith(".rar") or name.endswith(".tar") or name.endswith(".gz"):
            status = 4

    # if not running and percent != "100" and total != "0":
    #     status = 5

    return status


def get_files_structure(count_on_with_restart=False):
    connection = db.get_db()
    all_files = connection.execute("SELECT name, total, status, uuid, url, pid FROM downloads").fetchall()

    array_files = []
    array_not_for_user = []
    for file in all_files:
        name = file[0]
        total = file[1]
        status = file[2]
        uuid = file[3]
        url = file[4]
        pid = file[5]
        orphan = False

        running = (True if 0 < status < 4 else False) and not count_on_with_restart
        # when computer was restarted, no chance process is running
        if running:
            # it is running only according to db
            running = is_process_running(pid)
            # now we have actual and real information

        if not os.path.isfile(f"{OUTPUT_PATH}/{name}") and (total != "0" or status != 1):
            connection.execute("DELETE FROM downloads WHERE uuid = ?", (uuid, ))
            connection.commit()
            continue

        if not os.path.isfile(f"{NOHUP_OUTPUT_PATH}/{uuid}.out"):
            orphan = True

            if running:
                os.kill(pid, 9)

            if not 2 < status < 5:
                connection.execute("DELETE FROM downloads WHERE uuid = ?", (uuid,))
                connection.commit()
                continue

        actual_data = read_data(uuid)
        if total == "0" and total != actual_data["data_total"]:
            total = actual_data["data_total"]

        status = get_status(name, running, actual_data["data_percent"])

        connection.execute("UPDATE downloads SET total = ?, status = ? WHERE uuid = ?", (total, status, uuid))
        connection.commit()

        # not for user = uuid, pid, orphan
        not_for_user = [uuid, pid, orphan]
        array_not_for_user.append(not_for_user)
        dict_file = struct_data_for_reinit(status, name, total, url, actual_data)
        array_files.append(dict_file)

    return array_files, array_not_for_user


def was_restarted() -> bool:
    process = subprocess.check_output(["who", "-b"])
    startup_time_str = process.decode("UTF-8").strip()
    last_startup_time_str = ""

    if os.path.isfile(STARTUP_TIME_FILE):
        with open(STARTUP_TIME_FILE, "r") as startup_time_file:
            last_startup_time = startup_time_file.readlines()
            if len(last_startup_time) > 0:
                last_startup_time_str = last_startup_time[0]

    with open(STARTUP_TIME_FILE, "w") as startup_time_file:
        startup_time_file.write(startup_time_str)

    if last_startup_time_str != startup_time_str:
        return True

    return False


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

    actual_pid = process.pid + 1
    # because process.pid returns pid of nohup, nohup immediately creates a new process curl with pid one greater
    return actual_pid


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
                       (uuid, name, data["data_total"], 1, url, pid))
    connection.commit()


def edit_status_total_in_database(new_status: int, new_total: str, uuid: str):
    connection = db.get_db()
    connection.execute("UPDATE downloads SET status = ?, total = ? WHERE uuid = ?", (new_status, new_total, uuid))
    connection.commit()
