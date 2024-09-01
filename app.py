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


app = Flask(__name__)

import mysql.connector

db_config = {
    'user': 'hackathon',
    'password': 'Kerb@um@sukp@rit',
    'host': 'rm-6nna6j8tfzby3ay3vbo.mysql.rds.aliyuncs.com',  # contoh: 'rm-xxxx.mysql.rds.aliyuncs.com'
    'database': 'hackathon',
    'port': 3306
}


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


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
