# Refer to the document for workspace information: https://www.alibabacloud.com/help/en/model-studio/developer-reference/model-calling-in-sub-workspace    
        
from http import HTTPStatus
import dashscope
import random
from flask import Flask, request, redirect, session, render_template, jsonify, url_for
from flask_sqlalchemy import SQLAlchemy
import re
from flask import Flask
import mysql.connector
import pandas as pd
from flask_cors import CORS
from werkzeug.security import check_password_hash
from PyPDF2 import PdfReader
import os
from werkzeug.utils import secure_filename
from io import BytesIO

app = Flask(__name__)
# CORS(app, resources={r"/*": {"origins": ["http://localhost:3000/", "http://147.139.246.21:3000"]}})
CORS(app)
import mysql.connector


UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Buat direktori 'uploads' jika belum ada
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

db_config = {
    'user': 'hackathon',
    'password': 'Kerb@um@sukp@rit',
    'host': 'rm-6nna6j8tfzby3ay3vbo.mysql.rds.aliyuncs.com',  # contoh: 'rm-xxxx.mysql.rds.aliyuncs.com'
    'database': 'hackathon',
    'port': 3306
}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_text_from_pdf(pdf_file):
    reader = PdfReader(pdf_file)
    text = ''
    for page in reader.pages:
        text += page.extract_text()
    return text

def get_db_connection():
    return mysql.connector.connect(**db_config)


@app.route('/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({'status': 'error', 'message': 'Username and password are required'}), 400

    try:
        db_connection = get_db_connection()
        cursor = db_connection.cursor(dictionary=True)

        query = "SELECT user_id, username, password, role FROM users WHERE username = %s AND password = %s"
        cursor.execute(query, (username, password))
        user = cursor.fetchone()

        if user:
            return jsonify({
                'status': 'success',
                'user_id': user['user_id'],
                'username': user['username'],
                'role': user['role']
            }), 200
        else:
            return jsonify({'status': 'error', 'message': 'Invalid username or password'}), 401

    except mysql.connector.Error as err:
        return jsonify({'status': 'error', 'message': str(err)}), 500

    finally:
        if cursor:
            cursor.close()
        if db_connection:
            db_connection.close()

dashscope.base_http_api_url = 'https://dashscope-intl.aliyuncs.com/api/v1'
dashscope.api_key='sk-a1311b4902ae4d34bc944af0165b52e5'

def call_with_stream(materi, n_soal):
    messages = [
        {'role': 'user', 
         'content': f"""
            Kamu adalah AI yang bertugas untuk membuat pertanyaan pilihan ganda dengan 3 opsi. 
            Kalimat pertanyaan diawali dengan <q>, sedangkan opsi jawaban diawali dengan <o>, sedangkan level soal diawali dengan <l> dengan value : [mudah, sedang, sulit] ketiga value tersebut harus ada,
            sedangkan kunci jawaban diawali dengan <a>.
            Contoh:
            <q> Soal 1. berapa nilai dari 1+1 ?
            <o> A. 2
            <o> B. 1
            <o> C. 3
            <l> mudah
            <a> jawabannya adalah A. 2
            <q> Soal 2. berapa nilai dari 2 log 4 ?
            <o> A. 2
            <o> B. 1
            <o> C. 4
            <l> sulit
            <a> jawabannya adalah A. 2

            Buatlah {n_soal} pertanyaan berdasarkan materi ini:
            {materi}          
        """}]
    
    responses = dashscope.Generation.call("qwen-max",
                                messages=messages,
                                result_format='message',  
                                stream=True,              
                                incremental_output=True   
                                )
    
    full_text = ""
    for response in responses:
        if response.status_code == HTTPStatus.OK:
            full_text += response.output.choices[0]['message']['content']
        else:
            error_message = ('Request id: %s, Status code: %s, error code: %s, error message: %s' % (
                response.request_id, response.status_code,
                response.code, response.message
            ))
            return error_message
    
    # Parsing multiple questions, options, levels, and answers
    questions = re.findall(r'<q>(.*?)\s*(?=<o>)', full_text, re.DOTALL)
    options_blocks = re.findall(r'(?:<o>.*?)(?=<l>)', full_text, re.DOTALL)
    levels = re.findall(r'<l>\s*(.*?)\s*(?=<a>)', full_text, re.DOTALL)
    answers = re.findall(r'<a>\s*(.*?)\s*(?=<|$)', full_text, re.DOTALL)

    results = []
    for i in range(len(questions)):
        question = questions[i].strip()
        option_set = re.findall(r'<o>\s*(.*?)\s*(?=<|$)', options_blocks[i], re.DOTALL)
        level = levels[i].strip()
        answer = answers[i].strip()
        
        result = {
            "question": question,
            "options": [opt.strip() for opt in option_set],
            "level": level,
            "answer": answer
        }
        results.append(result)
    
    return results


@app.route('/data_kuis/<int:id_siswa>')
def data_kuis(id_siswa):
    pass

@app.route('/generate/<int:chapter_id>',methods=['POST'])
def generate(chapter_id):
    db_connection = mysql.connector.connect(**db_config)
    cursor = db_connection.cursor()
    content = pd.read_sql_query(f"SELECT content FROM chapters WHERE chapter_id = {chapter_id}",db_connection)['content'][0]
    print(content)
    data = call_with_stream(content,10)
    db_connection.close()
    return data
    
@app.route('/chapter_list/<int:course_id>', methods=['GET'])
def chapter_list(course_id):
    db_connection = mysql.connector.connect(**db_config)
    cursor = db_connection.cursor()
    try:
        cursor = db_connection.cursor(dictionary=True)

        query = "SELECT chapter_id, chapter_name, content FROM chapters WHERE course_id = %s"
        cursor.execute(query, (course_id,))
        chapters = cursor.fetchall()

        if chapters:
            return jsonify({'status': 'success', 'chapters': chapters}), 200
        else:
            return jsonify({'status': 'error', 'message': 'No chapters found for this course'}), 404

    except mysql.connector.Error as err:
        return jsonify({'status': 'error', 'message': str(err)}), 500

    finally:
        cursor.close()
        db_connection.close()


@app.route('/course_list', methods=['GET'])
def course_list():
    db_connection = get_db_connection()
    cursor = db_connection.cursor()

    try:
        query = "SELECT course_name FROM courses"
        cursor.execute(query)
        courses = cursor.fetchall()

        course_list = [course[0] for course in courses]  # Mengambil nilai course_name

        return jsonify({'status': 'success', 'courses': course_list}), 200

    except mysql.connector.Error as err:
        return jsonify({'status': 'error', 'message': str(err)}), 500

    finally:
        cursor.close()
        db_connection.close()

# @app.route('/show_content/<int:chapter_id>')
# def show_content(chapter_id):


@app.route('/upload_pdf', methods=['POST'])
def upload_pdf():
    course_name = request.form.get('course_name')
    chapter_name = request.form.get('chapter_name')
    pdf_file = request.files.get('file')

    if not course_name or not chapter_name or not pdf_file or not allowed_file(pdf_file.filename):
        return jsonify({"status": "error", "message": "Invalid input"}), 400

    try:
        # Save the PDF to the server
        filename = secure_filename(pdf_file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        pdf_file.save(file_path)

        # Extract text from PDF
        with open(file_path, 'rb') as file:
            pdf_content = extract_text_from_pdf(file)

        # Connect to the database
        db_connection = get_db_connection()
        cursor = db_connection.cursor()

        # Get course_id from course_name
        cursor.execute("SELECT course_id FROM courses WHERE course_name = %s", (course_name,))
        course = cursor.fetchone()
        if not course:
            return jsonify({"status": "error", "message": "Course not found"}), 404
        course_id = course[0]

        # Insert the new chapter into the chapters table
        insert_query = """
            INSERT INTO chapters (chapter_name, content, course_id)
            VALUES (%s, %s, %s)
        """
        cursor.execute(insert_query, (chapter_name, pdf_content, course_id))
        db_connection.commit()
        cursor.close()
        db_connection.close()

        return jsonify({"status": "success", "message": "Chapter uploaded successfully"}), 201

    except mysql.connector.Error as err:
        return jsonify({"status": "error", "message": str(err)}), 500

    finally:
        if os.path.exists(file_path):
            os.remove(file_path)





if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
