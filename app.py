from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os
import uuid
import requests
from dotenv import load_dotenv
import openai



HF_API_KEY = os.getenv("HF_API_KEY")

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")


def get_trust_score(text):
    API_URL = "https://api-inference.huggingface.co/models/distilbert-base-uncased-finetuned-sst-2-english"
    headers = {"Authorization": f"Bearer {HF_API_KEY}"}
    payload = {"inputs": text}
    try:
        response = requests.post(API_URL, headers=headers, json=payload)
        result = response.json()
        if isinstance(result, list) and result:
            return f"{result[0]['label']} ({result[0]['score']:.2f})"
    except Exception as e:
        print("Trust score API error:", e)
    return "UNKNOWN"

app = Flask(__name__)
CORS(app)
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


def init_db():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE,
            password TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fullname TEXT,
            age INTEGER,
            gender TEXT,
            phone TEXT,
            email TEXT,
            address TEXT,
            languages TEXT,
            education TEXT,
            availability TEXT,
            caretype TEXT,
            experience TEXT,
            experience_desc TEXT,
            certification TEXT,
            assist TEXT,
            gov_id TEXT,
            selfie TEXT,
            emergency_contact TEXT,
            reference_name TEXT,
            reference_number TEXT,
            quick_experience TEXT,
            quick_helpedElderly TEXT,
            quick_assist TEXT,
            quick_smokeDrink TEXT,
            quick_urgentHelp TEXT,
            quick_shortNotice TEXT,
            quick_communicate TEXT,
            quick_legalComplaint TEXT,
            quick_shareId TEXT,
            quick_motivation TEXT,
            trust_score TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS care_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fullName TEXT,
            phone TEXT,
            address TEXT,
            whoNeedsCare TEXT,
            daysNeeded INTEGER,
            timeSlot TEXT,
            tasks TEXT,
            language TEXT,
            notes TEXT
        )
    ''')
    conn.commit()
    conn.close()

def build_matching_prompt(care_request, caretakers):
    prompt = f"""
A family submitted a care request:
- Who needs care: {care_request['whoNeedsCare']}
- Days needed: {care_request['daysNeeded']}
- Time slot: {care_request['timeSlot']}
- Tasks: {care_request['tasks']}
- Preferred language: {care_request['language']}
- Notes: {care_request['notes']}

Below are caretaker applicants:
"""
    for i, ct in enumerate(caretakers):
        prompt += f"""
Caretaker #{i+1}:
- Name: {ct['fullname']}
- Age: {ct['age']}
- Gender: {ct['gender']}
- Languages: {ct['languages']}
- Care types: {ct['caretype']}
- Availability: {ct['availability']}
- Experience: {ct['experience']}
- Description: {ct['experience_desc']}
- Motivation: {ct['quick_motivation']}
- Trust Score: {ct['trust_score']}
"""

    prompt += "\nPlease choose the best caretaker based on how well they match the family's request. Only return the caretaker’s full name and a short explanation."
    return prompt
   

init_db()


def ask_ai_for_best_caretaker(prompt):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",  # Use "gpt-4" if you have access
            messages=[
                {"role": "system", "content": "You are an assistant that recommends the best caretaker based on a family's care request."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.4,
            max_tokens=500
        )
        return response['choices'][0]['message']['content']
    except Exception as e:
        print("AI Matching Error:", e)
        return "AI matching failed."


@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    email = data.get('email')
    password = generate_password_hash(data.get('password'))
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    try:
        c.execute('INSERT INTO users (email, password) VALUES (?, ?)', (email, password))
        conn.commit()
        return jsonify({'success': True, 'message': 'User registered!'})
    except sqlite3.IntegrityError:
        return jsonify({'success': False, 'message': 'Email already exists.'})
    finally:
        conn.close()

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('SELECT password FROM users WHERE email = ?', (email,))
    row = c.fetchone()
    conn.close()
    if row and check_password_hash(row[0], password):
        return jsonify({'success': True, 'message': 'Login successful'})
    else:
        return jsonify({'success': False, 'message': 'Invalid credentials'})

@app.route('/apply', methods=['POST'])
def apply():
    data = request.form
    files = request.files
    answers = f"{data.get('quick_experience', '')} {data.get('quick_helpedElderly', '')} {data.get('quick_motivation', '')}"
    trust_score = get_trust_score(answers)

    def save_file(field):
        file = files.get(field)
        if file and file.filename:
            unique_filename = f"{uuid.uuid4().hex}_{file.filename}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            file.save(filepath)
            return unique_filename
        return None

    certification_doc = save_file('certification-doc')
    gov_id = save_file('gov-id')
    selfie = save_file('selfie')

    caretype = ','.join(request.form.getlist('caretype'))
    assist = ','.join(request.form.getlist('assist[]'))

    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''
        INSERT INTO applications (
            fullname, age, gender, phone, email, address, languages, education, availability,
            caretype, experience, experience_desc, certification, assist, gov_id, selfie,
            emergency_contact, reference_name, reference_number,
            quick_experience, quick_helpedElderly, quick_assist, quick_smokeDrink, quick_urgentHelp,
            quick_shortNotice, quick_communicate, quick_legalComplaint, quick_shareId, quick_motivation, trust_score
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        data.get('fullname'),
        data.get('age'),
        data.get('gender'),
        data.get('phone'),
        data.get('email'),
        data.get('address'),
        data.get('languages'),
        data.get('education'),
        data.get('availability'),
        caretype,
        data.get('experience'),
        data.get('experience-desc'),
        certification_doc,
        assist,
        gov_id,
        selfie,
        data.get('emergency-contact'),
        data.get('reference-name'),
        data.get('reference-number'),
        data.get('quick_experience'),
        data.get('quick_helpedElderly'),
        data.get('quick_assist'),
        data.get('quick_smokeDrink'),
        data.get('quick_urgentHelp'),
        data.get('quick_shortNotice'),
        data.get('quick_communicate'),
        data.get('quick_legalComplaint'),
        data.get('quick_shareId'),
        data.get('quick_motivation'),
        trust_score
    ))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': 'Application submitted!'})

@app.route('/')
def home():
    return "API is running!"

@app.route('/submit_care_request', methods=['POST'])
def submit_care_request():
    data = request.get_json()
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''
        INSERT INTO care_requests (
            fullName, phone, address, whoNeedsCare, daysNeeded, timeSlot, tasks, language, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        data.get('fullName'),
        data.get('phone'),
        data.get('address'),
        data.get('whoNeedsCare'),
        data.get('daysNeeded'),
        data.get('timeSlot'),
        ','.join(data.get('tasks', [])),
        data.get('language'),
        data.get('notes')
    ))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': 'Care request submitted!'})


@app.route('/match_caretaker', methods=['POST'])
def match_caretaker():
    data = request.get_json()
    request_id = data.get('request_id')  # ID of the care request

    if not request_id:
        return jsonify({'success': False, 'message': 'Request ID is required.'}), 400

    conn = sqlite3.connect('users.db')
    c = conn.cursor()

    # Get care request
    c.execute("SELECT * FROM care_requests WHERE id = ?", (request_id,))
    care_request = c.fetchone()
    if not care_request:
        conn.close()
        return jsonify({'success': False, 'message': 'Care request not found'}), 404

    care_request_columns = [column[0] for column in c.description]
    care_request_data = dict(zip(care_request_columns, care_request))

    # Get all applicants
    c.execute("SELECT * FROM applications")
    caretakers = c.fetchall()
    caretaker_columns = [column[0] for column in c.description]
    caretakers_data = [dict(zip(caretaker_columns, row)) for row in caretakers]

    conn.close()

    # Build prompt and ask AI
    prompt = build_matching_prompt(care_request_data, caretakers_data)
    result = ask_ai_for_best_caretaker(prompt)

    return jsonify({
        'success': True,
        'care_request': care_request_data,
        'best_match_result': result
    })

if __name__ == '__main__':
    app.run(debug=True)



