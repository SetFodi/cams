from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from requests.auth import HTTPDigestAuth
from datetime import datetime
import requests
import json
import threading
from security import apply_security
import time
import re
import aiohttp
import asyncio
import os
from celery import Celery
from datetime import timedelta
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor
import httpx
import pytz
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from dotenv import load_dotenv
load_dotenv()
MAX_CAMERAS = int(os.getenv('MAX_CAMERAS'))




tbilisi_tz = pytz.timezone('Asia/Tbilisi')
current_time = datetime.now(tbilisi_tz)
print("Current Time in Tbilisi:", current_time.strftime("%Y-%m-%d %H:%M:%S"))
app = Flask(__name__)
apply_security(app)
celery = Celery(app.name, broker='redis://localhost:6379/0')
app.secret_key = '45^54'  # Replace with a strong random secret key

# Global camera configurations
cameras = []


# Global variables for Day and Night profile times
day_profile_time = None
night_profile_time = None
day_mode_count = 0
night_mode_count = 0

MODES_FILE = 'camera_modes.json'
# Load camera details from the JSON file
def load_camera_config():
    global cameras
    try:
        with open('cameras_configure.json', 'r') as f:
            cameras = json.load(f)
        if len(cameras) > MAX_CAMERAS:
            raise ValueError(f"Camera limit exceeded in configuration. Max allowed is {MAX_CAMERAS}")
    except (FileNotFoundError, json.JSONDecodeError):
        cameras = []
    except ValueError as e:
        print(str(e))
        cameras = []  # Optionally clear the list or handle as needed

def convert_to_tbilisi(local_time_str):
    local_time = datetime.strptime(local_time_str, "%H:%M")  # Assume input in HH:MM format
    local_time = tbilisi_tz.localize(local_time)  # Localize to Tbilisi timezone
    return local_time.strftime("%H:%M")
day_time_tbilisi = convert_to_tbilisi('08:00')  # '08:00' AM in Tbilisi
print("Day time in Tbilisi:", day_time_tbilisi)

def read_camera_modes():
    if not os.path.exists(MODES_FILE) or os.path.getsize(MODES_FILE) == 0:
        # Initialize the file if it's missing or empty
        with open(MODES_FILE, 'w') as f:
            json.dump({}, f, indent=4)
        return {}

    try:
        with open(MODES_FILE, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError:
        print(f"Error reading {MODES_FILE}: Invalid JSON format.")
        return {}  # Return an empty dictionary if the JSON is malformed
    except Exception as e:
        print(f"Unexpected error while reading {MODES_FILE}: {e}")
        return {}

def write_camera_modes(modes):
    try:
        with open(MODES_FILE, 'w') as f:
            json.dump(modes, f, indent=4)
    except Exception as e:
        print(f"Error writing to {MODES_FILE}: {e}")

def update_camera_mode_in_json(camera_ip, mode):
    modes = read_camera_modes()
    modes[camera_ip] = mode
    write_camera_modes(modes)


def is_valid_ip(ip):
    """
    Validates the IP address format and range.
    """
    ip_regex = r"^(\d{1,3}\.){3}\d{1,3}$"
    if not re.match(ip_regex, ip):
        return False

    parts = ip.split('.')
    for part in parts:
        if not (0 <= int(part) <= 255):
            return False

    return True


def is_duplicate_ip(ip):
    """
    Checks if the IP address is already in the cameras list.
    """
    return any(camera['ip'] == ip for camera in cameras)


# Save camera details to the JSON file
def save_camera_config():
    try:
        with open('cameras_configure.json', 'w') as f:
            json.dump(cameras, f, indent=2)
    except Exception as e:
        pass





# Update status labels
def update_status_labels():
    day_label = f"{day_mode_count}/{len(cameras)} - Day"
    night_label = f"{night_mode_count}/{len(cameras)} - Night"

    day_time_status = f"Day starts at {day_profile_time[0]:02d}:{day_profile_time[1]:02d}" if day_profile_time else "Day profile time not set"
    night_time_status = f"Night starts at {night_profile_time[0]:02d}:{night_profile_time[1]:02d}" if night_profile_time else "Night profile time not set"

    return day_label, night_label, day_time_status, night_time_status


async def async_is_camera_connected(camera):
    camera_ip = camera["ip"]
    url = f"http://{camera_ip}/cgi-bin/magicBox.cgi?action=getSystemInfo"

    async with httpx.AsyncClient() as client:
        try:
            auth = httpx.DigestAuth(camera["username"], camera["password"])
            response = await client.get(url, auth=auth, timeout=5)
            if response.status_code == 200:
                print(f"Camera {camera_ip} is connected.")
                return True
        except httpx.TimeoutException:
            print(f"Camera {camera_ip} timed out.")
        except Exception as e:
            print(f"Error connecting to camera {camera_ip}: {e}")

    return False


async def initialize_camera_modes_async():
    global day_mode_count, night_mode_count  # Declare both as global at the start
    semaphore = asyncio.Semaphore(10)
    day_mode_count = 0  # Reset count before processing
    night_mode_count = 0  # Reset count before processing

    async def check_camera(camera):
        global day_mode_count, night_mode_count  # Declare as global again here
        async with semaphore:
            connected = await async_is_camera_connected(camera)
            camera["status"] = "Connected" if connected else "Not Connected"

            if connected:
                # Read mode from JSON file
                camera_ip = camera["ip"]
                modes = read_camera_modes()
                current_mode = modes.get(camera_ip, "day")  # Default to "day" if mode is not set

                # Debug prints
                print(f"Checking camera {camera_ip}, Current Mode: {current_mode}")
                if current_mode == "night":
                    night_mode_count += 1
                else:
                    day_mode_count += 1

    tasks = [check_camera(camera) for camera in cameras]
    await asyncio.gather(*tasks)

    # Debug prints to check final counts
    print(f"Final Day Mode Count: {day_mode_count}")
    print(f"Final Night Mode Count: {night_mode_count}")







def set_day_night_mode(mode):
    global day_mode_count, night_mode_count
    day_mode_count = 0
    night_mode_count = 0

    def set_mode(camera):
        try:
            camera_ip = camera["ip"]
            set_config_url = f"http://{camera_ip}/cgi-bin/configManager.cgi?action=setConfig"
            config = {
                "VideoInDayNight[0][0].Mode": mode,
                "VideoInDayNight[0][1].Mode": mode,
            }
            response = requests.get(set_config_url, params=config,
                                    auth=HTTPDigestAuth(camera["username"], camera["password"]), timeout=3)
            if response.status_code == 200 and response.text == "OK":
                update_camera_mode_in_json(camera_ip, mode)  # Update mode in JSON file
                if mode == "Color":
                    return "Day"
                elif mode == "BlackWhite":
                    return "Night"
        except requests.RequestException:
            pass
        return None

    # Use ThreadPoolExecutor for concurrent execution
    with ThreadPoolExecutor(max_workers=10) as executor:
        results = executor.map(set_mode, cameras)

    for result in results:
        if result == "Day":
            day_mode_count += 1
        elif result == "Night":
            night_mode_count += 1






def monitor_time():
    global cameras
    while True:
        current_time = datetime.now()
        current_hour = current_time.hour
        current_minute = current_time.minute

        if day_profile_time and (current_hour, current_minute) == day_profile_time:
            set_day_night_mode("Color")
            print("Day mode activated for all cameras")

        if night_profile_time and (current_hour, current_minute) == night_profile_time:
            set_day_night_mode("BlackWhite")
            print("Night mode activated for all cameras")

        time.sleep(60)



def initialize_camera_modes_file():
    if not os.path.exists(MODES_FILE) or os.path.getsize(MODES_FILE) == 0:
        with open(MODES_FILE, 'w') as f:
            json.dump({}, f, indent=4)  # Initialize with an empty dictionary

# Call this at the start of your app
initialize_camera_modes_file()


# Function to refresh the camera list and update the status labels
def refresh_camera_list():
    global cameras, day_mode_count, night_mode_count
    load_camera_config()
    asyncio.run(initialize_camera_modes_async())

def load_time_profile():
    global day_profile_time, night_profile_time
    try:
        with open('latest_time.json', 'r') as f:
            latest_times = json.load(f)
            day_profile_time = tuple(map(int, latest_times["day_time"].split(":")))
            night_profile_time = tuple(map(int, latest_times["night_time"].split(":")))
    except (FileNotFoundError, json.JSONDecodeError):
        day_profile_time = None
        night_profile_time = None


def login_required(func):
    def wrapper(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return func(*args, **kwargs)
    wrapper.__name__ = func.__name__  # Preserve original function name
    return wrapper


@app.route('/')
@login_required
def index():
    global day_mode_count, night_mode_count

    # Read camera modes from the JSON file
    modes = read_camera_modes()

    # Reset counters
    day_mode_count = 0
    night_mode_count = 0

    # Count cameras in day and night mode
    for camera_ip, mode in modes.items():
        if mode == "Color":  # Or "day" if using that term
            day_mode_count += 1
        elif mode == "BlackWhite":  # Or "night"
            night_mode_count += 1

    # Update the status labels
    day_label, night_label, day_time_status, night_time_status = update_status_labels()

    # Render the template with the updated counts
    return render_template(
        'index.html',
        day_mode_count=day_mode_count,
        night_mode_count=night_mode_count,
        day_label=day_label,
        night_label=night_label,
        day_time_status=day_time_status,
        night_time_status=night_time_status
    )




@app.route('/add_camera', methods=['POST'])
def add_camera():
    if len(cameras) >= MAX_CAMERAS:
        return jsonify({"status": "error", "message": f"Camera limit reached. Max allowed is {MAX_CAMERAS}"}), 400

    camera_ip = request.form['ip']

    if not is_valid_ip(camera_ip):
        return jsonify({"status": "error", "message": "Invalid IP address format"}), 400

    if is_duplicate_ip(camera_ip):
        return jsonify({"status": "error", "message": "Camera with this IP already exists"}), 400

    camera = {
        "ip": camera_ip,
        "port": 80,
        "username": "admin",
        "password": "admin12345",
        "status": "Not Connected"
    }
    cameras.append(camera)
    save_camera_config()
    return jsonify({"status": "success", "message": "Camera added successfully"}), 200


@app.route('/set_day_mode', methods=['POST'])
def set_day_mode():
    set_day_night_mode("Color")
    return jsonify({"message": "All cameras set to Day Mode"})


@app.route('/set_night_mode', methods=['POST'])
def set_night_mode():
    set_day_night_mode("BlackWhite")
    return jsonify({"message": "All cameras set to Night Mode"})


@app.route('/set_time_profile', methods=['POST'])
def set_time_profile():
    global day_profile_time, night_profile_time
    day_profile_time = tuple(map(int, request.form['day_time'].split(":")))
    night_profile_time = tuple(map(int, request.form['night_time'].split(":")))

    latest_times = {
        "day_time": request.form['day_time'],
        "night_time": request.form['night_time']
    }
    with open('latest_time.json', 'w') as f:
        json.dump(latest_times, f)

    return jsonify(latest_times)


@app.route('/initialize_modes')
def initialize_modes():
    asyncio.run(initialize_camera_modes_async())
    return jsonify({"message": "Camera modes initialized asynchronously"})


@app.route('/get_time_profile', methods=['GET'])
def get_time_profile():
    try:
        with open('latest_time.json', 'r') as f:
            latest_times = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        latest_times = {"day_time": "Not Set", "night_time": "Not Set"}

    return jsonify(latest_times)


#@app.route('/reports')
#def reports():
#    for camera in cameras:
#        connected = asyncio.run(async_is_camera_connected(camera))
# ##   return render_template('reports.html', cameras=cameras)

@app.route('/get_camera_status', methods=['GET'])
def get_camera_status():
    global day_mode_count, night_mode_count

    # Read camera modes from the JSON file
    modes = read_camera_modes()  # This reads the current mode of each camera from the file

    # Reset the counters
    day_mode_count = 0
    night_mode_count = 0

    # Count cameras in "day" or "night" mode
    for camera_ip, mode in modes.items():
        if mode == "Color":  # Or "day" if using that term
            day_mode_count += 1
        elif mode == "BlackWhite":  # Or "night"
            night_mode_count += 1

    # Create the status strings
    day_label = f"{day_mode_count}/{len(cameras)} - Day"
    night_label = f"{night_mode_count}/{len(cameras)} - Night"

    day_time_status = f"Day starts at {day_profile_time[0]:02d}:{day_profile_time[1]:02d}" if day_profile_time else "Day profile time not set"
    night_time_status = f"Night starts at {night_profile_time[0]:02d}:{night_profile_time[1]:02d}" if night_profile_time else "Night profile time not set"

    # Return the updated counts and labels
    return jsonify({
        "day_mode_count": day_mode_count,
        "night_mode_count": night_mode_count,
        "day_label": day_label,
        "night_label": night_label,
        "day_time_status": day_time_status,
        "night_time_status": night_time_status
    })



@app.route('/refresh_camera_status', methods=['GET'])
def refresh_camera_status():
    global cameras, day_mode_count, night_mode_count

    # Read camera modes from the JSON file
    modes = read_camera_modes()

    # Reset counts
    day_mode_count = 0
    night_mode_count = 0

    # Count cameras in day and night mode
    for camera_ip, mode in modes.items():
        if mode == "Color":
            day_mode_count += 1
        elif mode == "BlackWhite":
            night_mode_count += 1

    # Update camera status
    def check_camera(camera):
        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(asyncio.run, async_is_camera_connected(camera))
                connected = future.result(timeout=3)  # Set timeout for each camera
            camera["status"] = "Connected" if connected else "Not Connected"
        except FuturesTimeoutError:
            camera["status"] = "Not Connected"  # Default to not connected on timeout
        except Exception:
            camera["status"] = "Not Connected"  # Handle other exceptions

    with ThreadPoolExecutor(max_workers=10) as executor:  # Adjust max workers
        executor.map(check_camera, cameras)

    save_camera_config()  # Save updated camera configurations
    return jsonify({"cameras": cameras})



@app.route('/reports')
def reports():
    return render_template('reports.html', cameras=cameras)

@app.route('/remove_camera/<camera_ip>', methods=['POST'])
def remove_camera(camera_ip):
    global cameras
    updated_cameras = [camera for camera in cameras if camera["ip"] != camera_ip]
    if len(updated_cameras) == len(cameras):
        return jsonify({"status": "error", "message": "Camera not found"}), 404

    cameras = updated_cameras
    save_camera_config()
    return jsonify({"status": "success", "message": "Camera removed successfully"}), 200

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        # Validate credentials
        if username == 'psp_admin' and password == '@dm!nP$P45^54':
            session['logged_in'] = True
            return redirect(url_for('index'))  # Redirect to the home page
        else:
            return render_template('login.html', error="Invalid username or password")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)  # Remove logged-in flag from session
    return redirect(url_for('login'))

@celery.task
def refresh_camera_status_periodically():
    global cameras
    for camera in cameras:
        connected = asyncio.run(async_is_camera_connected(camera))
        camera["status"] = "Connected" if connected else "Not Connected"
    save_camera_config()

if __name__ == '__main__':
    load_camera_config()
    load_time_profile()
    threading.Thread(target=monitor_time, daemon=True).start()
    app.run(debug=True)
