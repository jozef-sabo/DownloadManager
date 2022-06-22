PATH_STRUCTURE = "./%s.out"


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


print(read_data("nohup"))
