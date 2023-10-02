import uuid

import flask
from flask import Flask, request, redirect, send_from_directory, url_for
from flask import stream_with_context, Response, abort
from flask_cors import CORS  # Importing CORS to handle Cross-Origin Resource Sharing
from extensions import db  # Importing the database object from extensions module
import tutor
import json
import time
import os
import pymysql
import sqlite3
import openai
import loader


if 'CHATUTOR_GCP' in os.environ: 
    openai.api_key = os.environ['OPENAI_API_KEY']
else:
    import yaml
    with open('.env.yaml') as f:
        yamlenv = yaml.safe_load(f)
    keys = yamlenv["env_variables"]
    print(keys)
    os.environ['OPENAI_API_KEY'] = keys["OPENAI_API_KEY"]
    os.environ['ACTIVELOOP_TOKEN'] = keys["ACTIVELOOP_TOKEN"]

app = Flask(__name__)
CORS(app)  # Enabling CORS for the Flask app to allow requests from different origins
db.init_db()

# connection = pymysql.connect(
#     host='34.41.31.71',
#     user='admin',
#     password='password',
#     db='mydatabase',
#     charset='utf8mb4',
#     cursorclass=pymysql.cursors.DictCursor
# ) ## for mysql server TO BE USED INSTEAD OF 'con'

# Only for deleting the db when you first access the site. Can be used for debugging
presetTables1 = """
    DROP TABLE IF EXISTS lchats
"""
# only for deleting the db when you first access the site. Can be used for debugging
presetTables2 = """
    DROP TABLE IF EXISTS lmessages
"""

chats_table_Sql = """
CREATE TABLE IF NOT EXISTS lchats (
    chat_id varchar(100) PRIMARY KEY
    )"""


def connect_to_database():
    """Function that connects to the database"""
    # for mysql server
    # connection = pymysql.connect(
    #     host='localhost',
    #     user='root',
    #     password='password',
    #     db='mydatabase',
    #     charset='utf8mb4',
    #     cursorclass=pymysql.cursors.DictCursor
    # )
    # return connection

    connection = pymysql.connect(
        host='34.41.31.71',
        user='admin',
        password='AltaParolaPuternica1245',
        db='chatmsg',
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )

    return connection
    # return sqlite3.connect('')


messages_table_Sql = """
CREATE TABLE IF NOT EXISTS lmessages (
    mes_id varchar(100) PRIMARY KEY,
    role text NOT NULL,
    content text NOT NULL,
    chat_key varchar(100) NOT NULL,
    clear_number integer NOT NULL,
    time_created text NOT NULL,
    FOREIGN KEY (chat_key) REFERENCES lchats (chat_id)
    )"""


def initialize_ldatabase():
    """Creates the tables if they don't exist"""
    con = connect_to_database()
    cur = con.cursor()
    #if you want to delete the database when a user acceses the site. (For DEBUGGING purposes only
    # cur.execute(presetTables1)
    # cur.execute(presetTables2)
    cur.execute(chats_table_Sql)
    cur.execute(messages_table_Sql)

initialize_ldatabase()

@app.route("/")
def index():
    """
        Serves the landing page of the web application which provides
        the ChatTutor interface. Users can ask the Tutor questions and it will
        response with information from its database of papers and information.
        Redirects the root URL to the index.html in the static folder
    """
    return redirect(url_for('static', filename='index.html'))

@app.route('/static/<path:path>')
def serve_static(path):
    """Serving static files from the 'static' directory"""
    return send_from_directory('static', path)

@app.route("/ask", methods=["POST", "GET"])
def ask():
    """Route that facilitates the asking of questions. The response is generated
    based on an embedding.
    
    URLParams:
        conversation (List({role: ... , content: ...})):  snapshot of the current conversation 
        collection: embedding used for vectorization
    Yields:
        response: {data: {time: ..., message: ...}}
    """
    data = request.json
    conversation = data["conversation"]
    collection_name = data["collection"]
    from_doc = data.get("from_doc")
    # Logging whether the request is specific to a document or can be from any document
    if(from_doc): print("only from doc", from_doc)
    else: print("from any doc")

    db.load_datasource(collection_name)
    def generate():
        # This function generates responses to the questions in real-time and yields the response
        # along with the time taken to generate it.
        chunks = ""
        start_time = time.time()
        for chunk in tutor.ask_question(db, conversation, from_doc):
            chunk_content = ""
            if 'content' in chunk:
                chunk_content = chunk['content']
            chunks += chunk_content
            chunk_time = time.time() - start_time
            yield f"data: {json.dumps({'time': chunk_time, 'message': chunk})}\n\n"
    return Response(stream_with_context(generate()), content_type='text/event-stream')

@app.route('/addtodb', methods=["POST", "GET"])
def addtodb():
    data = request.json
    content = data['content']
    role = data['role']
    chat_k_id = data['chat_k']
    clear_number = data['clear_number']
    time_created = data['time_created']
    insert_chat(chat_k_id)
    message_to_upload = {'content': content, 'role': role, 'chat': chat_k_id, 'clear_number': clear_number, 'time_created': time_created}
    insert_message(message_to_upload)
    print_for_debug()
    return Response('inserted!', content_type='text')

@app.route('/getfromdb', methods=["POST", "GET"])
def getfromdb():
    data = request.form
    username = data.get('lusername', 'nan')
    passcode = data.get('lpassword', 'nan')
    print(data)
    print(username, passcode)
    if username == 'root' and passcode == 'admin':
        with connect_to_database() as con:
            cur = con.cursor()
            res = cur.execute("SELECT * FROM lmessages ORDER BY chat_key, clear_number, time_created")
            messages_arr = cur.fetchall()
            renderedString = ""
            i = 0
            for message in messages_arr:
                role = message['role']
                content = message['content']
                chat_id = message['chat_key']
                clear_number = message['clear_number']
                style = 'font-size: 10px; background-color: var(--msg-input-bg); overflow: hidden; padding: 2px; border-radius: 2px'

                side = 'left'
                if role != 'assistant':
                    side = 'right'

                msg_html = f"""
                    <div class="{side}-msg">
                        <div class="msg-bgd">
                          <div class="msg-bubble">
                            <div class="msg-info">
                              <div class="msg-info-name">role: {role}</div>
                              <div class="msg-info-name" style="{style}">chat_key: {chat_id}, {clear_number}</div>
                            </div>

                            <div class="msg-text">content: {content}</div>
                          </div>
                        </div>
                    </div>
                """
                renderedString += msg_html

            return flask.render_template('display_messages.html', renderedString=renderedString)
    else:
        return flask.render_template_string('Error, please <a href="/static/display_db.html">Go back</a>')


@app.route('/exesql', methods=["POST", "GET"])
def exesql():
    data = request.json
    username = data['lusername']
    passcode = data['lpassword']
    sqlexec = data['lexesql']
    if username == 'root' and passcode == 'admin':
        with connect_to_database() as con:
            cur = con.cursor()
            response = cur.execute(sqlexec)
            messages_arr = cur.fetchall()
            con.commit()
            return Response(f'{messages_arr}', 200)
    else:
        return Response('fail', 404)

def print_for_debug():
    """For debugging purposes. Acceses  the content of the lmessages table"""
    with connect_to_database() as con:
        cur = con.cursor()
        response = cur.execute('SELECT * FROM lmessages ORDER BY clear_number, time_created')
        # con.commit()



def insert_message(a_message):
    """This inserts a message into the sqlite3 database."""
    with connect_to_database() as con:
        cur = con.cursor()

        role = a_message['role']
        content = a_message['content']
        chat_key = a_message['chat']
        clear_number = a_message['clear_number']
        time_created = a_message['time_created']
        insert_format_lmessages = f"INSERT INTO lmessages (mes_id ,role, content, chat_key, clear_number, time_created) VALUES ('{uuid.uuid4()}','{role}', %s, '{chat_key}', {clear_number}, '{time_created}')"
        cur.execute(insert_format_lmessages, (content,))
        con.commit()



def insert_chat(chat_key):
    """This inserts a chat into the sqlite3 database, ignoring the command if the chat already exists."""
    with connect_to_database() as con:
        cur = con.cursor()
        insert_format_lchats = ""
        cur.execute(f"INSERT IGNORE INTO lchats (chat_id) VALUES ('{chat_key}')")
        con.commit()
        # print('inserted!')

@app.route('/compile_chroma_db', methods=['POST'])
def compile_chroma_db():
    token = request.headers.get('Authorization')

    if token != openai.api_key:
        abort(401)  # Unauthorized
    
    loader.init_chroma_db()

    return "Chroma db created successfully", 200

if __name__ == "__main__":
    app.run(debug=True)  # Running the app in debug mode
