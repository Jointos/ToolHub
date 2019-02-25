from flask import Flask, render_template, g,request,redirect,url_for,flash,jsonify,current_app
from flask_wtf import Form
from wtforms import TextField, TextAreaField, validators, StringField, SubmitField
import sqlite3, os, re, io, sys, subprocess, json
app = Flask(__name__)
with app.app_context():
    DATABASE = os.path.join('../db','toolhub_database.sqlite3')
    #Formoknál kell valamiért secret key
    app.config['SECRET_KEY'] = 'any secret string'
    print(current_app.name)

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

class InputForm(Form):
    input = StringField('input_field',id='input_field')


@app.route('/run_script',methods=['POST'])
def run_script():
    # result = input_form.input.data
    input_form = InputForm()
    print("SAJTOSROLLÓSGECI")
    print(input_form.data)
    # print(json.loads(input_form.data))
    print(input_form.input)
    print(input_form.input.data)
    print(input.filename_without_extension)

    if input_form.validate_on_submit():
        source_file_path=os.path.join('../db/tools',input.data.filename_without_extension+'.py')
        output = subprocess.check_output("python " + source_file_path + " " + input_form.input.data.input, shell=True)
        return output
    return "Error"

def get_tools():
    cursor = get_db().cursor()
    rows =  cursor.execute('select name,source_file_name from scripts limit 10').fetchall()
    results = []
    for row in rows:
        with open(os.path.join('../db/tools',row[1]), 'r') as scriptfile:
            results.append({'name':row[0],'source_file_name':row[1].split('.')[0],'source_code':scriptfile.read()})
    return results

@app.route('/')
@app.route('/index')
def index():
    tools=get_tools()
    for tool in tools:
        tool['input_form']=InputForm()
    return render_template('index.html',datas=tools)
