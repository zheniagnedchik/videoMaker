from flask import Flask, request, send_file
import cv2
import numpy as np
import requests
import os
import json
import uuid
import subprocess

app = Flask(__name__)


def download_image(url):
    response = requests.get(url)
    if response.status_code == 200:
        image_array = np.asarray(bytearray(response.content), dtype="uint8")
        image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
        return image
    else:
        raise Exception("Error loading image")


def send_post_request(data):
    headers = {'Content-Type': 'application/json'}
    response = requests.post(
        "http://143.110.149.184/create_video", data=json.dumps(data), headers=headers)
    return response


def process_video(video_path, image_url, output_path):

    lower_hsv = np.array([144 - 10, 100, 100])
    upper_hsv = np.array([144 + 10, 255, 199])

    cap = cv2.VideoCapture(video_path)
    frame_width = int(cap.get(3))
    frame_height = int(cap.get(4))

    videos_dir = '/var/www/videoMaker/videos/'
    # videos_dir = 'videos/'
    if not os.path.exists(videos_dir):
        os.makedirs(videos_dir)

    full_output_path = os.path.join(videos_dir, output_path)
    # out = cv2.VideoWriter(full_output_path.replace(
    #     '.mp4', '.webm'), cv2.VideoWriter_fourcc(*'VP80'), 20.0, (frame_width, frame_height))
    out = cv2.VideoWriter(full_output_path,
                          cv2.VideoWriter_fourcc(*'XVID'),  # Use 'XVID' codec
                          20.0, (frame_width, frame_height))

    insert_image = download_image(image_url)

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, lower_hsv, upper_hsv)
        contours, _ = cv2.findContours(
            mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for cnt in contours:
            if cv2.contourArea(cnt) > 100:
                x, y, w, h = cv2.boundingRect(cnt)
                insert_image_resized = cv2.resize(insert_image, (w, h))
                frame[y:y+h, x:x+w] = insert_image_resized

        out.write(frame)

    cap.release()
    out.release()
    mp4_output_path = output_path.replace('.mp4', '.mp4')
    full_mp4_output_path = os.path.join(videos_dir, mp4_output_path)
    convert_to_mp4(full_output_path, full_mp4_output_path)

    return full_mp4_output_path
    # return full_output_path


@app.route('/videos/<path:filename>')
def get_video(filename):
    videos_dir = '/var/www/videoMaker/videos/'
    videos_dir = 'videos/'
    full_path = os.path.join(videos_dir, filename)
    return send_file(full_path, mimetype='video/mp4')


def convert_to_mp4(input_path, output_path):
    # Check if input and output paths are the same
    if input_path == output_path:
        base, ext = os.path.splitext(output_path)
        output_path = f"{base}_converted{ext}"

    # Replace the placeholder below with the actual path to FFmpeg
    ffmpeg_path = '/usr/bin/ffmpeg'  # Example path on Linux
    command = [ffmpeg_path, '-i', input_path,
               '-vcodec', 'libx264', '-crf', '23', output_path]
    subprocess.run(command, check=True)

    return output_path


@app.route('/process', methods=['POST'])
def process_and_download():
    video_path = 'test.mp4'
    image_url = request.json.get('image_url')
    folderId = request.json.get('folder_id')
    name = request.json.get('name')
    if not image_url:
        return "Image URL is required", 400
    image_url_index = image_url[0]
    output_path = f"{name}.mp4"
    # output_path = "webm.webm"

    try:
        full_output_path = process_video(
            video_path, image_url_index, output_path)
        video_data = {
            "link": name,
            "folderId": folderId
        }
        send_post_request(video_data)
        app.logger.info(cv2.getBuildInformation())
        return f"Video processed successfully. Saved to {full_output_path}. Document inserted into RavenDB."
    except Exception as e:
        return str(e), 500


if __name__ == '__main__':
    app.run(debug=True)
