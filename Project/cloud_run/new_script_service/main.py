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
from google.cloud import storage, firestore
app = Flask(__name__)
# [END run_pubsub_server_setup]
firestore_client = firestore.Client()

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

    def replace_default_with_custom_dependency():
      data = script_details["custom_dependencies"]
      custom_deps = dict(
        map(
          lambda x: (x['name'],x['version']),
          filter(lambda x: not x['is_disabled'], data)))
      disabled_dep_names = list(map(lambda x: x['name'],filter(lambda x: x['is_disabled'], data)))
      print("custom_deps:",custom_deps)
      if not custom_deps and not disabled_dep_names:
        return
      default_deps = {}
      with open(SCRIPT_REQUIREMENTS,"r") as requirements_file:
        content = requirements_file.read().strip().split("\n")
        print(f"content start:{content}:end")
        sys.stdout.flush()
        default_deps = dict(filter(lambda x:x[0] not in disabled_dep_names, map(lambda x: tuple(x), filter(lambda x: len(x)==2, map(lambda x: x.split("=="),content)))))
      with open(SCRIPT_REQUIREMENTS,"w") as requirements_file:
        new_deps = {**default_deps,**custom_deps}
        requirements = "\n".join(map(lambda x:x[0]+"=="+x[1],new_deps.items()))
        requirements_file.write(requirements)
        print("requirements:", requirements)
      

    def get_hidden_imports():
      data = script_details["hidden_imports"]
      return " ".join(map(lambda h_import: f"--hidden-import={h_import}" , data))


    metadata = json.loads(base64.b64decode(pubsub_message['data']).decode('utf-8').strip())
    script_details = firestore_client.collection("scripts").document(metadata['name']).get().to_dict()
    download_blob(metadata['bucket'], metadata['name'], os.path.join(DOWNLOAD_FOLDER, FILE_NAME_WITH_EXT))
    # TODO: IMPORTANT! --onefile option is slow, better to make it one folder!
    subprocess.check_output(f'pipreqs --force --savepath {SCRIPT_REQUIREMENTS} {DOWNLOAD_FOLDER}', shell=True)
    replace_default_with_custom_dependency()
    subprocess.check_output(f'pip install -r {SCRIPT_REQUIREMENTS}', shell=True,stderr=subprocess.STDOUT)
    hidden_imports_string = get_hidden_imports()
    pyinstaller_command = f'python -O -m PyInstaller {hidden_imports_string} --onefile {os.path.join(DOWNLOAD_FOLDER, FILE_NAME_WITH_EXT)}'
    print("pyinstaller_command:", pyinstaller_command)
    sys.stdout.flush()
    try:
      subprocess.check_output(pyinstaller_command, shell=True,stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
      print("error while pyinstalling:", e.output)
      sys.stdout.flush()
      raise RuntimeError("command '{}' return with error (code {}): {}".format(e.cmd, e.returncode, e.output))

    script_name_without_ext = os.path.splitext(metadata['name'])[0]
    upload_blob(DESTIONATION_BUCKET_NAME, os.path.join("dist",FILE_NAME), script_name_without_ext)
    # Script is no longer being installed, update firestore, so it will be available to users.
    firestore_client.collection("scripts").document(metadata['name']).update({'is_being_installed': firestore.DELETE_FIELD})
  # Flush the stdout to avoid log buffering.
  sys.stdout.flush()

  return ('', 204)
# [END run_pubsub_handler]


if __name__ == '__main__':
  PORT = int(os.getenv('PORT')) if os.getenv('PORT') else 8080

  # This is used when running locally. Gunicorn is used to run the
  # application on Cloud Run. See entrypoint in Dockerfile.
  app.run(host='127.0.0.1', port=PORT, debug=True)
