Python 3.7.x REQUIRED!!!
dependencies:
	pip install flask:
		Jinja2-2.10.1 
		MarkupSafe-1.1.1 
		Werkzeug-0.15.4 click-7.0
		flask-1.0.3 itsdangerous-1.1.0
	pip install flask-cors:
		Six-1.12.0 
		flask-cors-3.0.7

In a terminal run the following commands from the root folder of the forked project.

python -m venv venv
For homebrew installed Python run:

python3 -m venv venv
Once that completes, also run this command from the same folder.

Windows

venv\Scripts\activate.bat

Previewing Your Work
You can preview your work by running "flask run" in the root of your fork. Then visit http://localhost:5000 in your browser. You will see a working preview after completing the first module.
