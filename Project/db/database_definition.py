from flask import Flask, render_template, g,request,redirect,url_for
import sqlite3
import os

scripts_sql="""CREATE TABLE IF NOT EXISTS scripts(
    id integer PRIMARY KEY,
    name text NOT NULL,
    source_file_name text NOT NULL
);"""

DATABASE='toolhub_database.sqlite3'
db = None

def get_db():
    global db
    if db is None:
        db = sqlite3.connect(DATABASE)
    return db

def close_connection():
    global db
    if db is not None:
        db.close()

def create_table(sql):
    c =get_db()
    try:
        cursor = c.cursor()
        cursor.execute(sql)
    except Exception as e:
        print(e)

def insert_to_toolhub_from_sample():
    names= ["Add Two Numbers","Print all args","Convert to Reverse Case","Convert to Uppercase"]
    for dirpath, dirnames, filenames in os.walk('tools'):
        for i, file in enumerate(filenames):
            get_db().cursor().execute('insert into scripts(name,source_file_name) values(?,?)',(names[i],file))
    get_db().commit()


if __name__ == '__main__':
    cursor = get_db().cursor()
    cursor.execute('drop table scripts')
    create_table(scripts_sql)
    insert_to_toolhub_from_sample()
    print(cursor.execute('select source_file_name from scripts').fetchall())
    close_connection()
