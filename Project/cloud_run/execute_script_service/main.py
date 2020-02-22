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
    executable_name: str

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

EXECUTABLES_BUCKET_NAME = "toolhub_executables"
TEMPORARY_SCRIPT_INPUTS_BUCKET_NAME = "toolhub_temporary_script_inputs"
EXEC_FOLDER = "exec"
NO_OUTPUT = 'Script did not have output result'

# TODO: VERY IMPORTANT!!!! ONE CONTAINER CAN GHANDLE MULTIPLE REQUEST SO WHAT IF WE OVERWRITE THE INPUT AND EXEC FILE?
# TODO:  VERY IMPORTANT!!!! ALSO EVERY WRITTEN FILE GOES TO IN MEMORY SPACE WHICH CAN COST MUCH
# TODO:   VERY IMPORTANT!!!! NEED TO CLEAN UP FILES BECAUSE THEY CAN REMAIN BETWEEN INVOCATIONS!!! 
# [START run_pubsub_handler]
@app.route('/', methods=['POST'])
def index():
  envelope = request.get_json()
  if not envelope:
    msg = 'no message received'
    print(f'error: {msg}')
    return f'Bad Request: {msg}', 400

  # TODO: IMPORTANT LATER ON!!! Could use another container only for the executable, because of other notes and parallel request script could refer to other ones.
  try:
    message : HTTPSMessage = HTTPSMessage.Schema().loads(json.dumps(envelope))
  except marshmallow.exceptions.ValidationError as e:
    msg = f'invalid message format: {e}'
    print(f'error: {msg}')
    return f'Bad Request: {msg}', 400
  # Download as the same file name
  executable_path = os.path.join(EXEC_FOLDER, message.executable_name)
  download_blob(EXECUTABLES_BUCKET_NAME, message.executable_name, executable_path)
  # Download input files to exec folder
  for input in message.inputs:
    if input.type == 'file':
      download_blob(TEMPORARY_SCRIPT_INPUTS_BUCKET_NAME, input.value, os.path.join(EXEC_FOLDER, ntpath.basename(str(input.value))))
  # Create the input file for the script TODO: IMPORTANT!!! this should be reworked to just passing the parameters in the stdin of script 
  inputs_with_only_values = json.dumps({input.name: input.value for input in message.inputs})
  with open(os.path.join(EXEC_FOLDER, "input"),"w") as input_file:
    input_file.write(inputs_with_only_values)
  # Execute the script TODO: remove these cd commands and make the script to handle this.

  print("chmod 777 exec path",subprocess.check_output(f'chmod 777 {executable_path}', shell=True))
  print("chmod 777 exec path",subprocess.check_output(f'chmod 777 exec/input', shell=True))
  try:
    print(f'executable_path stderr: {executable_path}',subprocess.check_output(f'cd exec;./{message.executable_name};cd ..', shell=True,stderr=subprocess.STDOUT))
  except subprocess.CalledProcessError as e:
    print("command '{}' return with error (code {}): {}".format(e.cmd, e.returncode, e.output))
  sys.stdout.flush()
  # Retrieve the output TODO: just as a string yet, this is not applicable because response have limited size
  #                            output file needs to be copied into a bucket
  output_string = None
  with open(os.path.join(EXEC_FOLDER, "output"),"r") as output_file:
    output_string = output_file.read()
    print("output:",output_string)
  if not output_string:
    log(Severities.ERROR, f'{NO_OUTPUT}. Script name: {message.executable_name}')
    # Flush the stdout to avoid log buffering. TODO: look after it, why not using it above?
    sys.stdout.flush()
    return (NO_OUTPUT, 400)
  sys.stdout.flush()
  return (output_string, 200)


if __name__ == '__main__':
  PORT = int(os.getenv('PORT')) if os.getenv('PORT') else 8080  # type: ignore

  # This is used when running locally. Gunicorn is used to run the
  # application on Cloud Run. See entrypoint in Dockerfile.
  app.run(host='127.0.0.1', port=PORT, debug=True)

