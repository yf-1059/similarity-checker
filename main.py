import sys
import os
import mysql.connector
import json
import io
import PyPDF2
import docx
import string
from gensim.parsing.preprocessing import remove_stopwords
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from flask import Flask, request

app = Flask(__name__)

def preprocess_text(text):
    # Remove punctuation and convert to lowercase
    text = text.translate(str.maketrans('', '', string.punctuation)).lower()
    # Remove stopword
    filtered_text = remove_stopwords(text)
    return filtered_text


def vectorize(text):
    return TfidfVectorizer(stop_words='english').fit_transform(text).toarray()


def similarity(doc1, doc2):
    return cosine_similarity([doc1, doc2])


def check_plagiarism(reportId, s_vectors):
    similarity_result = {}
    total_sim_score = 0

    for student_a, text_vector_a in s_vectors:
        if (student_a == reportId):
            new_vectors = s_vectors.copy()
            current_index = new_vectors.index((student_a, text_vector_a))
            del new_vectors[current_index]
            for student_b, text_vector_b in new_vectors:
                sim_score = similarity(text_vector_a, text_vector_b)[0][1]
                if (sim_score > 0):
                    sim_score = round(sim_score, 2)
                    # student_pair = sorted((os.path.splitext(student_a)[0], os.path.splitext(student_b[0])))
                    res = (student_a+' similar to '+student_b)
                    similarity_result[res] = sim_score
                    total_sim_score = sim_score + total_sim_score

            avg_sim_score = (total_sim_score / len(new_vectors)) * 100
            
            return round(avg_sim_score)

    api = json.dumps(similarity_result)
    print('api', api)


@app.route('/similarity-check', methods=['GET', 'POST'])
def checker():
    # Connect to mysql database
    try:
        # Extract the input data from the request
        data = request.json
        reportId = data.get("reportId")

        userId = data.get("userId")
        userId = int(userId)

        connection = mysql.connector.connect(host='localhost',
                                            database='ppms',
                                            user='root',
                                            password='')

        cursor = connection.cursor()
        sql_query = """SELECT report_id, data, file_name from reports WHERE user_id != %s AND is_final=true OR report_id = %s"""

        cursor.execute(sql_query, (userId, reportId))
        record = cursor.fetchall()
        
        if (len(record) <= 1):
            return json.dumps(0)
        else:
            files_id_array = []
            files_array = []
            files_name_array = []
            files_content = []
            for row in record:
                files_id_array.append(row[0])
                files_name_array.append(row[2])
                file = row[1]
                if (row[2].endswith(".pdf")):
                    pdf_file = io.BytesIO(file)
                    # Use PyPDF2 to extract text from the PDF file
                    pdf_reader = PyPDF2.PdfFileReader(pdf_file)
                    text = ''
                    for page_num in range(pdf_reader.numPages):
                        page = pdf_reader.getPage(page_num)
                        text += page.extractText()

                    filtered_text = preprocess_text(text)
                    files_content.append(filtered_text)
                else:
                    docx_data = io.BytesIO(file)
                    doc = docx.Document(docx_data)
                    text = ''
                    for paragraph in doc.paragraphs:
                        text += paragraph.text

                    filtered_text = preprocess_text(text)
                    files_content.append(filtered_text)

            # for file in files_array:
            #     pdf_file = io.BytesIO(file)
            #     # Use PyPDF2 to extract text from the PDF file
            #     pdf_reader = PyPDF2.PdfFileReader(pdf_file)
            #     text = ''
            #     for page_num in range(pdf_reader.numPages):
            #         page = pdf_reader.getPage(page_num)
            #         text += page.extractText()

            #     filtered_text = preprocess_text(text)
            #     files_content.append(filtered_text)

            # student_files = [doc for doc in files_name_array if doc.endswith('.pdf')]
            # iterate each doc in files_id_array and assign to doc
            student_files = [doc for doc in files_id_array]

            vectors = vectorize(files_content)
            s_vectors = list(zip(student_files, vectors))

            # Process the input data and generate the model output
            output = check_plagiarism(reportId, s_vectors)

            # Return the model output as the response
            return json.dumps(output)

    except mysql.connector.Error as error:
        print("Failed to read BLOB data from MySQL table {}".format(error))

    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()
            print("MySQL connection is closed")

@app.route("/")
def index():
    return "Testing"

if __name__ == '__main__':
    app.run()