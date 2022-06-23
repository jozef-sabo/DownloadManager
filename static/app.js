let input_url = document.getElementById("input_url");
let list_downloads = document.getElementById("list_downloads");
let data_version = -1;
const size_multipliers = {
    "B": 1,
    "kB": 1024,
    "MB": 1_048_576,
    "GB": 1_073_741_824,
    "TB": 1_099_511_627_776,
    "PB": 1_125_899_906_842_624
}
let array_items = []
let socket = io();

function download() {
    let url = input_url.value
    let data = JSON.stringify(
        {
            "url": url,
            "ftp_client": -1
        }
    )
    send_request("download", "POST", data, render_items, null)

}

function send_request(
    url, type, data, on_success, on_failed,
    headers = { "Accept": "application/json", "Content-Type": "application/json"}
) {
    let xhr= new XMLHttpRequest();
    xhr.open(type, url);

    if (typeof headers === "object") {
         Object.keys(headers).forEach(key => xhr.setRequestHeader(key, headers[key]))
    }

    xhr.onload = function() {
        if (xhr.status === 200) { if (on_success) on_success(xhr.response) }
        else { if (on_failed) on_failed() }
    };

    xhr.send(data);
}

function setup_socketio() {
    socket.on('connect', function() {
        //socket.emit('my event', {data: 'I\'m connected!'});
    });

    socket.on("downloading", function(received_data) {
        received_data["files"].forEach(function (value, index) {
            normalize_totals()
            edit_list_item(index, value)
        })
    });
}

function normalize_totals(data = null) {
    if (data == null) {
        let request_data = {"ids": []}
        array_items.forEach(function (index, value) {
            if (value["total"] === "0") {
                request_data["ids"].push(index)
            }
        })
        if (request_data["ids"].length !== 0) {
            send_request("update_totals", "GET", request_data, normalize_totals)
        }
        return
    }

    let ids_dict = data["totals"]
    Object.entries(ids_dict).forEach(([key, value]) => {
        edit_list_item(Number(key), {"total": value})
})
}

function render_items(data, from_user = false) {
    if (!from_user) data = JSON.parse(data)
    data_version = data["files_version"]

    clear_list()
    data["files"].forEach(function (value) {
        add_list_item(value)
    })
}

function clear_list() {
    list_downloads.innerHTML = ""
}

function convert_size_to_array(size) {
    let size_unit = "B"
    let size_number = Number(size)

    if (isNaN(size_number)) {
        size_unit = size.charAt(size.length-1) + "B"
        size_number = Number(size.slice(0, size.length - 1))
    }

    let in_bytes = size_number * size_multipliers[size_unit]

    return [size_number, size_unit, in_bytes]
}

function add_list_item(file_data) {
    let filename = file_data["title"]
    let finished = file_data["finished"]
    let total_arr = convert_size_to_array(file_data["total"])
    let speed_arr = convert_size_to_array(file_data["speed"])
    let downloaded_arr = convert_size_to_array(file_data["downloaded"])

    array_items.push({"title": filename, "total": total_arr, "finished": finished})

    let percent = 100
    let finished_progress = "bg-success"
    let text_percent_size = "100%"
    let text_stop_button = "X"

    if (!finished) {
        percent = Math.floor(100 * downloaded_arr[2] / total_arr[2])
        percent = (percent > 99) ? 99 : percent
        percent = (percent < 0) ? 0 : percent
        finished_progress = ""
        text_percent_size = `${percent}% - ${speed_arr[0]}${speed_arr[1]}/s`
        text_stop_button = "■"
    }

    let list_item = `<li class="list-group-item">
                            <div class="pt-2 d-flex align-content-between justify-content-between flex-column flex-md-row">
                                <div class="d-flex flex-row justify-content-between w-100">
                                    <div class="py-2">
                                        <span class="text-muted"><span>${total_arr[0]}</span><span class="size-marker">${total_arr[1]}</span> </span>
                                        <span>${filename}</span>
                                    </div>
                                    <button type="button" class="btn btn-outline-danger mx-1">${text_stop_button}</button>
                                </div>
                                <div class="col-md-4 ${finished_progress} d-flex flex-column justify-content-center pt-md-0 pt-2">
                                    <div class="progress">
                                        <div class="progress-bar" role="progressbar" style="width: ${percent}%" aria-valuenow="${percent}" aria-valuemin="0" aria-valuemax="100">${text_percent_size}</div>
                                    </div>
                                </div>
                            </div>
                        </li>`
    list_downloads.append(document.createRange().createContextualFragment(list_item))
}

function edit_list_item(index, data) {
    let progress_bar = list_downloads.children[index].firstElementChild.children[1].firstElementChild.firstElementChild
    let stop_button = list_downloads.children[index].firstElementChild.firstElementChild.lastElementChild
    let progress_bar_text_arr = progress_bar.innerHTML.split("-")
    let finished = array_items[index]["finished"]

    if (finished) return

    if (data["finished"] !== undefined) {
        finished = data["finished"]
        if (finished) {
            stop_button.innerHTML = "X"
            array_items[index]["finished"] = true
        }
    }

    if (data["speed"] !== undefined) {
        let speed_arr = convert_size_to_array(data["speed"])
        progress_bar = list_downloads.children[index].firstElementChild.children[1].firstElementChild.firstElementChild
        progress_bar_text_arr[1] = ` ${speed_arr[0]}${speed_arr[1]}/s`
        progress_bar.innerHTML = progress_bar_text_arr.join("-")
    }

    if (data["downloaded"] !== undefined) {
        let downloaded_arr = convert_size_to_array(data["downloaded"])
        let percent = 100
        let text_percent_size = "100%"

        progress_bar.classList.add("bg-success")

        if (!finished) {
            progress_bar.classList.remove("bg-success")
            percent = Math.floor(100 * downloaded_arr[2] / array_items[index]["total"][2])
            percent = (percent > 99) ? 99 : percent
            percent = (percent < 0) ? 0 : percent

            progress_bar_text_arr[0] = `${percent}% `
            text_percent_size = progress_bar_text_arr.join("-")
        }

        progress_bar.innerHTML = text_percent_size
        progress_bar.style.width = percent + "%"
        progress_bar.setAttribute("aria-valuenow", String(percent))
    }

    if (data["total"] !== undefined) {
        let total_arr = convert_size_to_array(data["total"])
        let size =  list_downloads.children[0].firstElementChild.firstElementChild.firstElementChild.firstElementChild
        array_items[index]["total"] = total_arr
        size.children[0].innerHTML = String(total_arr[0])
        size.children[1].innerHTML = total_arr[1]
    }
}

function initialize() {
    send_request("init", "GET", null, render_items)
    setup_socketio()
}

initialize()
