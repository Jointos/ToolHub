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
import ntpath
import subprocess
import random
import string
import shutil
from urllib.parse import quote_plus
from enum import Enum
from flask import Flask, request
from google.cloud import storage
from marshmallow_dataclass import dataclass
import marshmallow
from typing import Any, List

app = Flask(__name__)

# More info https://cloud.google.com/logging/docs/reference/v2/rest/v2/LogEntry
class Severities(Enum):
  DEFAULT	  = 'DEFAULT'   # (0) The log entry has no assigned severity level.
  DEBUG	    = 'DEBUG'     # (100) Debug or trace information.
  INFO	    = 'INFO'      # (200) Routine information, such as ongoing status or performance.
  NOTICE	  = 'NOTICE'    # (300) Normal but significant events, such as start up, shut down, or a configuration change.
  WARNING	  = 'WARNING'   # (400) Warning events might cause problems.
  ERROR	    = 'ERROR'     # (500) Error events are likely to cause problems.
  CRITICAL  = 'CRITICAL'	# (600) Critical events cause more severe problems or outages.
  ALERT	    = 'ALERT'     # (700) A person must take an action immediately.
  EMERGENCY = 'EMERGENCY'	# (800) One or more systems are unusable.

@dataclass
class Input:
    name : str
    value : Any
    type : str


@dataclass
class HTTPSMessage:
    inputs: List[Input]
    output_filenames: List[str]
    executable_name: str
    temporary_folder: str

def create_error_output(message):
  return json.dumps({'error':message})

# TODO: move this into common library
def log(severity: Severities, message: str):
  print(json.dumps(dict(severity=severity.value,message=message)))

# TODO This functino is a copy paste, move this into a common library
def download_blob(bucket_name, source_blob_name, destination_file_name):
  """Downloads a blob from the bucket."""
  # bucket_name = "your-bucket-name"
  # source_blob_name = "storage-object-name"
  # destination_file_name = "local/path/to/file"
  storage_client = storage.Client()
  bucket = storage_client.bucket(bucket_name)
  blob = bucket.blob(source_blob_name)
  blob.download_to_filename(destination_file_name)
  log(Severities.NOTICE, "Blob {} downloaded to {}.".format(source_blob_name, destination_file_name))

# TODO This functino is a copy paste, move this into a common library
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

def get_random_alphaNumeric_string(stringLength=8):
    lettersAndDigits = string.ascii_letters + string.digits
    return ''.join((random.choice(lettersAndDigits) for i in range(stringLength)))

EXECUTABLES_BUCKET_NAME = "toolhub_executables"
TEMPORARY_SCRIPT_INPUTS_BUCKET_NAME = "toolhub_temporary_script_inputs"
TEMPORARY_SCRIPT_OUTPUTS_BUCKET_NAME = "toolhub_temporary_script_outputs"
NO_OUTPUT = 'Script did not have output result'

# TODO: VERY IMPORTANT!!!! ONE CONTAINER CAN GHANDLE MULTIPLE REQUEST SO WHAT IF WE OVERWRITE THE INPUT AND EXEC FILE?
# TODO:  VERY IMPORTANT!!!! ALSO EVERY WRITTEN FILE GOES TO IN MEMORY SPACE WHICH CAN COST MUCH
# TODO:   VERY IMPORTANT!!!! NOT GOOD:NEED TO CLEAN UP FILES BECAUSE THEY CAN REMAIN BETWEEN INVOCATIONS!!! MULTIPLE INVOCATION CAN RIUN AT THE SAME TIME, NEED SOMETHINFG BETTER
# [START run_pubsub_handler]
@app.route('/', methods=['POST'])
def index():
  envelope = request.get_json()
  if not envelope:
    msg = 'no message received'
    print(f'error: {msg}')
    return f'Bad Request: {msg}', 400

  try:
    message : HTTPSMessage = HTTPSMessage.Schema().loads(json.dumps(envelope))
  except marshmallow.exceptions.ValidationError as e:
    msg = f'invalid message format: {e}'
    print(f'error: {msg}')
    return f'Bad Request: {msg}', 400
  # Create folder for the current tasks execution
  EXEC_FOLDER = "EXEC_" + get_random_alphaNumeric_string()
  os.mkdir(EXEC_FOLDER)
  os.chmod(EXEC_FOLDER,0o777)
  os.system('echo "DISK USAGE:"')
  os.system("du -h ./")
  # Download as the same file name
  executable_path = os.path.join(EXEC_FOLDER, message.executable_name)
  download_blob(EXECUTABLES_BUCKET_NAME, message.executable_name, executable_path)
  # Download input files to exec folder
  for input in message.inputs:
    if input.type == 'file':
      print("temp input path:",os.path.join(message.temporary_folder, input.value))
      sys.stdout.flush()
      download_blob(TEMPORARY_SCRIPT_INPUTS_BUCKET_NAME, os.path.join(message.temporary_folder, input.value), os.path.join(EXEC_FOLDER, ntpath.basename(str(input.value))))
  # Create the input file for the script TODO: IMPORTANT!!! this should be reworked to just passing the parameters in the stdin of script 
  inputs_with_only_values = json.dumps({input.name: input.value for input in message.inputs})
  with open(os.path.join(EXEC_FOLDER, "input"),"w") as input_file:
    input_file.write(inputs_with_only_values)
  #TODO: remove these cd commands and make the script to handle this.
  print("chmod 777 exec path",subprocess.check_output(f'chmod 777 {executable_path}', shell=True))
  print("chmod 777 exec path",subprocess.check_output(f'chmod 777 {EXEC_FOLDER}/input', shell=True))
  # Prepare chroot jail for the script execution
  
  # Execute the script 
  sp_details = None
  try:
    print("Running executable")
    sp_details = subprocess.run(f'cd {EXEC_FOLDER} && ./{message.executable_name} && cd ..', capture_output=True, universal_newlines=True, shell=True)
    print("subprocess result:", sp_details)
  except Exception as e:
    shutil.rmtree(EXEC_FOLDER)
    return (create_error_output(str(e)), 200)
  sys.stdout.flush()
  if sp_details.returncode != 0:
    shutil.rmtree(EXEC_FOLDER)
    return (create_error_output(sp_details.stderr), 200)
  else:
    # TODO: only collect the output names from the results (both text,file). In other words, dont let other output values back
    output_path = os.path.join(EXEC_FOLDER, "output")
    outputs = {}
    # Gathering textual outputs
    if os.path.exists(output_path):
      with open(output_path,"r") as output_file:
        output_texts = json.loads(output_file.read())
        print("output_texts:", output_texts)
        sys.stdout.flush()
        outputs.update(output_texts)
    # Upload file outputs Gathering public links in Cloud Storage TODO: considering calling Cloud Function to delete them or is it more costy than deleteing by the end of the day?
    for local_file_name in message.output_filenames:
      local_file_path = os.path.join(EXEC_FOLDER, local_file_name)
      if os.path.exists(local_file_path):
        uploaded_name = message.temporary_folder + "-" + local_file_name
        upload_blob(TEMPORARY_SCRIPT_OUTPUTS_BUCKET_NAME, local_file_path, uploaded_name)
        public_link = 'https://storage.cloud.google.com/'+ quote_plus(f'{TEMPORARY_SCRIPT_OUTPUTS_BUCKET_NAME}/{uploaded_name}')
        outputs.update({local_file_name: public_link})
    # Minimal error check TODO: consider checking that every declared output exist
    if not outputs:
      log(Severities.ERROR, f'{NO_OUTPUT}. Script name: {message.executable_name}')
      # Flush the stdout to avoid log buffering. TODO: look after it, why not using it above?
      sys.stdout.flush()
      shutil.rmtree(EXEC_FOLDER)
      return (create_error_output(NO_OUTPUT), 200)
    shutil.rmtree(EXEC_FOLDER)
    return (json.dumps({"result":outputs}), 200)


if __name__ == '__main__':
  PORT = int(os.getenv('PORT')) if os.getenv('PORT') else 8080  # type: ignore

  # This is used when running locally. Gunicorn is used to run the
  # application on Cloud Run. See entrypoint in Dockerfile.
  app.run(host='127.0.0.1', port=PORT, debug=True)

