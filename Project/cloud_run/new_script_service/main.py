# Copyright 2019 Google, LLC.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# [START run_pubsub_server_setup]
import base64
import os
import sys
import json
import subprocess
from flask import Flask, request
from google.cloud import storage

app = Flask(__name__)
# [END run_pubsub_server_setup]


def download_blob(bucket_name, source_blob_name, destination_file_name):
  """Downloads a blob from the bucket."""
  # bucket_name = "your-bucket-name"
  # source_blob_name = "storage-object-name"
  # destination_file_name = "local/path/to/file"

  storage_client = storage.Client()

  bucket = storage_client.bucket(bucket_name)
  blob = bucket.blob(source_blob_name)
  blob.download_to_filename(destination_file_name)

  print(
    json.dumps(dict(
      severity='NOTICE',
      message="Blob {} downloaded to {}.".format(source_blob_name, destination_file_name)
    ))
  )


def upload_blob(bucket_name, source_file_name, destination_blob_name):
  """Uploads a file to the bucket."""
  # bucket_name = "your-bucket-name"
  # source_file_name = "local/path/to/file"
  # destination_blob_name = "storage-object-name"

  storage_client = storage.Client()
  bucket = storage_client.bucket(bucket_name)
  blob = bucket.blob(destination_blob_name)

  blob.upload_from_filename(source_file_name)
  print(
    json.dumps(dict(
      severity='NOTICE',
      message="File {} uploaded to {}.".format(source_file_name, destination_blob_name)
    ))
  )

FILE_NAME="script"
FILE_NAME_WITH_EXT = FILE_NAME + ".py"
DESTIONATION_BUCKET_NAME = "toolhub_executables"
SCRIPT_REQUIREMENTS = "script_requirements.txt"
DOWNLOAD_FOLDER = 'download'

# [START run_pubsub_handler]
@app.route('/', methods=['POST'])
def index():
  envelope = request.get_json()
  if not envelope:
    msg = 'no Pub/Sub message received'
    print(f'error: {msg}')
    return f'Bad Request: {msg}', 400

  if not isinstance(envelope, dict) or 'message' not in envelope:
    msg = 'invalid Pub/Sub message format'
    print(f'error: {msg}')
    return f'Bad Request: {msg}', 400

  pubsub_message = envelope['message']

  if isinstance(pubsub_message, dict) and 'data' in pubsub_message:
    metadata = json.loads(base64.b64decode(pubsub_message['data']).decode('utf-8').strip())
    download_blob(metadata['bucket'], metadata['name'], os.path.join(DOWNLOAD_FOLDER, FILE_NAME_WITH_EXT))
    # TODO: IMPORTANT! --onefile option is slow, better to make it one folder!
    subprocess.check_output(f'pipreqs --force --savepath {SCRIPT_REQUIREMENTS} {DOWNLOAD_FOLDER}', shell=True)
    subprocess.check_output(f'pip install -r {SCRIPT_REQUIREMENTS}', shell=True,stderr=subprocess.STDOUT)
    subprocess.check_output(f'python -O -m PyInstaller --onefile {os.path.join(DOWNLOAD_FOLDER, FILE_NAME_WITH_EXT)}', shell=True,stderr=subprocess.STDOUT)
    script_name_without_ext = os.path.splitext(metadata['name'])[0]
    upload_blob(DESTIONATION_BUCKET_NAME, os.path.join("dist",FILE_NAME), script_name_without_ext)
  # Flush the stdout to avoid log buffering.
  sys.stdout.flush()

  return ('', 204)
# [END run_pubsub_handler]


if __name__ == '__main__':
  PORT = int(os.getenv('PORT')) if os.getenv('PORT') else 8080

  # This is used when running locally. Gunicorn is used to run the
  # application on Cloud Run. See entrypoint in Dockerfile.
  app.run(host='127.0.0.1', port=PORT, debug=True)
