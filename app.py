from flask import Flask, render_template, request, jsonify, redirect, url_for, session,Response,flash,Blueprint, redirect, session , request , jsonify , logging
import json
from flask_socketio import SocketIO, emit, join_room, leave_room
import os
from pathlib import Path
import bcrypt
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
import google.generativeai as genai
from Create_modules.close_end_questionaire import get_random_close_questions
import csv
from Create_modules.open_end_questions import get_random_open_questions
import pandas as pd
from Create_modules.csv_extracter import csv_to_string
from dotenv import load_dotenv
import json
from Create_modules.image_analysis import analyze_image
from werkzeug.utils import secure_filename
from Create_modules.trained_chikitsa import chatbot_response
import cv2
from fhirclient.models.patient import Patient
import bcrypt
from datetime import timedelta
from datetime import datetime
from functools import wraps
from flask_mail import Mail, Message
from datetime import datetime, timedelta
from flask import session, redirect
import requests
from functools import wraps
import logging
from Create_modules.meldx_connect import create_fhir_patient
import secrets
import base64
from Create_modules.fhir_config import get_fhir_client, create_patient
import hashlib

load_dotenv()
app = Flask(__name__)
app.secret_key = 'secret_key'

# Configure upload folder and allowed extensions
UPLOAD_FOLDER = 'image_analysis/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    """
    Checks if the file has an allowed extension.
    """
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Initialize Gemini AI
genai.configure(api_key=os.getenv("API_KEY"))

@app.route('/')
def index():
    return render_template('index.html')

# Define users.json path
USERS_FILE = "instance/users.json"

def load_users():
    with open(USERS_FILE, "r") as f:
        return json.load(f)

def save_users(users):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=4)


# @app.route('/questionnaire', methods=['GET', 'POST'])
# def questionnaire():
#     if 'email' not in session:
#         return redirect('/login')
        
#     if request.method == 'POST':
#         age = request.form.get('age')
#         gender = request.form.get('gender')
#         occupation_type = request.form.get('occupation_type')
#         occupation_detail = request.form.get('occupation_detail')
        
#         # Determine final occupation value
#         occupation = occupation_detail if occupation_type == 'Other' else occupation_type
        
#         with open(USERS_FILE, 'r') as f:
#             users = json.load(f)
            
#         user = next((user for user in users if user['email'] == session['email']), None)
        
#         if user:
#             os.makedirs('instance/user_data', exist_ok=True)
            
#             user_data = {
#                 'age': age,
#                 'gender': gender,
#                 'occupation': occupation,
#                 'timestamp': datetime.now().isoformat()
#             }
            
#             filename = f"instance/user_data/{user['name']}.json"
#             with open(filename, 'w') as f:
#                 json.dump(user_data, f, indent=4)
                
#             return redirect('/login')
            
#     return render_template('questionnaire.html')

# @app.route('/register', methods=['GET', 'POST'])
# def register():
#     if request.method == 'POST':
#         name = request.form['name']
#         email = request.form['email']
#         password = request.form['password']

#         os.makedirs('instance', exist_ok=True)

#         if not os.path.exists(USERS_FILE):
#             with open(USERS_FILE, 'w') as f:
#                 json.dump([], f)

#         with open(USERS_FILE, 'r') as f:
#             users = json.load(f)

#         # Check for existing user (both email and username)
#         if any(user['email'] == email or user['name'] == name for user in users):
#             return render_template('register.html', error='Email or username already exists.')

#         hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
#         new_user = {
#             'name': name,
#             'email': email,
#             'password': hashed_password,
#             'role': 'user',
#             'created_at': datetime.now().isoformat()
#         }

#         users.append(new_user)
#         save_users(users)

#         session['username'] = name
#         session['email'] = email
#         session['role'] = 'user'
#         return redirect('/questionnaire')  # Changed redirect to questionaire route

#     return render_template('register.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']

        # Local storage
        os.makedirs('instance', exist_ok=True)
        if not os.path.exists(USERS_FILE):
            with open(USERS_FILE, 'w') as f:
                json.dump([], f)

        with open(USERS_FILE, 'r') as f:
            users = json.load(f)

        if any(user['email'] == email or user['name'] == name for user in users):
            return render_template('register.html', error='Email or username already exists.')

        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        new_user = {
            'name': name,
            'email': email,
            'password': hashed_password,
            'role': 'user',
            'created_at': datetime.now().isoformat()
        }

        # Store in local JSON
        users.append(new_user)
        save_users(users)

        # Store in MeldRx FHIR
        try:
            smart = get_fhir_client()
            if smart:
                fhir_patient = create_fhir_patient(new_user)
                response = fhir_patient.create(smart.server)
                
                # Store FHIR ID in local user data
                new_user['fhir_id'] = response['id']
                save_users(users)
                
                logging.info(f"Patient created in MeldRx with ID: {response['id']}")
        except Exception as e:
            logging.error(f"Failed to create patient in MeldRx: {str(e)}")

        session['username'] = name
        session['email'] = email
        session['role'] = 'user'
        return redirect('/questionnaire')

    return render_template('register.html')
@app.route('/questionnaire', methods=['GET', 'POST'])
def questionnaire():
    if 'email' not in session:
        return redirect('/login')
        
    if request.method == 'POST':
        age = request.form.get('age')
        gender = request.form.get('gender')
        occupation_type = request.form.get('occupation_type')
        occupation_detail = request.form.get('occupation_detail')
        occupation = occupation_detail if occupation_type == 'Other' else occupation_type
        
        with open(USERS_FILE, 'r') as f:
            users = json.load(f)
            
        user = next((user for user in users if user['email'] == session['email']), None)
        
        if user:
            # Update local storage
            os.makedirs('instance/user_data', exist_ok=True)
            user_data = {
                'age': age,
                'gender': gender,
                'occupation': occupation,
                'timestamp': datetime.now().isoformat()
            }
            
            filename = f"instance/user_data/{user['name']}.json"
            with open(filename, 'w') as f:
                json.dump(user_data, f, indent=4)

            # Update MeldRx FHIR record
            try:
                smart = get_fhir_client()
                if smart and 'fhir_id' in user:
                    # Get existing patient
                    patient = Patient.read(user['fhir_id'], smart.server)
                    
                    # Update patient data
                    patient.gender = gender.lower()
                    birth_year = datetime.now().year - int(age)
                    patient.birthDate = f"{birth_year}-01-01"
                    
                    # Update occupation
                    patient.extension = [{
                        "url": "http://hl7.org/fhir/StructureDefinition/patient-occupation",
                        "valueString": occupation
                    }]
                    
                    # Save updates
                    patient.update(smart.server)
                    logging.info(f"Updated patient {user['fhir_id']} in MeldRx")
            except Exception as e:
                logging.error(f"Failed to update patient in MeldRx: {str(e)}")
                
            return redirect('/login')
            
    return render_template('questionnaire.html')

def generate_code_verifier():
    code_verifier = secrets.token_urlsafe(64)
    return code_verifier[:128]

def generate_code_challenge(code_verifier):
    code_challenge = hashlib.sha256(code_verifier.encode('utf-8')).digest()
    code_challenge = base64.urlsafe_b64encode(code_challenge).decode('utf-8').rstrip('=')
    return code_challenge

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        identifier = request.form.get('identifier')  # Using get() method for safe access
        password = request.form.get('password')

        if not identifier or not password:
            return render_template('login.html', error='Please provide all credentials')

        users = load_users()
        user = next((user for user in users if user['email'] == identifier or user['name'] == identifier), None)

        if user and bcrypt.checkpw(password.encode('utf-8'), user['password'].encode('utf-8')):
            session['username'] = user['name']
            session['email'] = user['email']
            session['role'] = user.get('role', 'user')

            if session['role'] == 'admin':
                return redirect('/admin/dashboard')
            elif session['role'] == 'doctor':
                return redirect('/doctor/dashboard')
            else:
                return redirect('/home') 

        return render_template('login.html', error='Invalid credentials')

    return render_template('login.html')

@app.route('/session-info')
def session_info():
    session_data = dict(session)
    return jsonify(session_data)

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/home')
def home():
    return render_template('home.html')

@app.route('/meditation')
@login_required
def meditation():
    return render_template('meditation.html')

@app.route('/log_meditation', methods=['POST'])
@login_required
def log_meditation():
    username = session.get('username')
    
    meditation_data = {
        'timestamp': datetime.now().isoformat(),
        'duration': request.json.get('duration', 300),  # Default 5 minutes
        'completed': request.json.get('completed', True)
    }
    
    # Store meditation session data
    meditation_file = f'instance/meditation_data/{username}_meditation.json'
    os.makedirs('instance/meditation_data', exist_ok=True)
    
    try:
        with open(meditation_file, 'r') as f:
            meditation_history = json.load(f)
    except FileNotFoundError:
        meditation_history = []
    
    meditation_history.append(meditation_data)
    
    with open(meditation_file, 'w') as f:
        json.dump(meditation_history, f, indent=4)
    
    return jsonify({
        'status': 'success',
        'message': 'Meditation session logged successfully',
        'total_sessions': len(meditation_history)
    })

@app.route('/get_meditation_stats')
@login_required
def get_meditation_stats():
    username = session.get('username')
    meditation_file = f'instance/meditation_data/{username}_meditation.json'
    
    try:
        with open(meditation_file, 'r') as f:
            meditation_history = json.load(f)
            
        total_minutes = sum(session['duration'] for session in meditation_history)
        total_sessions = len(meditation_history)
        
        return jsonify({
            'total_minutes': total_minutes,
            'total_sessions': total_sessions,
            'recent_sessions': meditation_history[-5:]  # Last 5 sessions
        })
    except FileNotFoundError:
        return jsonify({
            'total_minutes': 0,
            'total_sessions': 0,
            'recent_sessions': []
        })

@app.route('/personal_info')
@login_required
def personal_info():
    username = session.get('username')
    user_data_path = f'instance/user_data/{username}.json'
    
    if os.path.exists(user_data_path):
        with open(user_data_path, 'r') as f:
            user_data = json.load(f)
    else:
        user_data = {
            "age": "",
            "gender": "",
            "occupation": "",
            "timestamp": datetime.now().isoformat()
        }
    
    return render_template('personal_info.html', user_data=user_data)

@app.route('/update_personal_info', methods=['POST'])
@login_required
def update_personal_info():
    username = session.get('username')
    user_data_path = f'instance/user_data/{username}.json'
    
    updated_data = {
        "age": request.form.get('age'),
        "gender": request.form.get('gender'),
        "occupation": request.form.get('occupation'),
        "timestamp": datetime.now().isoformat()
    }
    
    os.makedirs('instance/user_data', exist_ok=True)
    with open(user_data_path, 'w') as f:
        json.dump(updated_data, f, indent=4)
    
    return redirect(url_for('personal_info'))
@app.route('/closed_ended')
def close_ended():
    random_questions = get_random_close_questions()  # Get random 5 questions
    return render_template('closed_ended.html', questions=random_questions)

@app.route('/submit_close_end', methods=['POST'])
def submit_close_ended():
    if request.method == 'POST':
        responses = []
        for question in request.form:
            answer = request.form[question]
            responses.append((question, answer))
        
        # Save responses to CSV
        save_to_csv(responses)
        
        return redirect(url_for('submit_opended'))  # Corrected here
@app.route('/mood_tracker')
@login_required
def mood_tracker():
    return render_template('mood_tracker.html')

@app.route('/log_mood', methods=['POST'])
@login_required
def log_mood():
    data = request.json
    username = session.get('username')
    mood_file = f'instance/mood_data/{username}_moods.json'
    
    os.makedirs('instance/mood_data', exist_ok=True)
    
    try:
        with open(mood_file, 'r') as f:
            moods = json.load(f)
    except FileNotFoundError:
        moods = []
    
    moods.append({
        'mood': data['mood'],
        'timestamp': data['timestamp']
    })
    
    with open(mood_file, 'w') as f:
        json.dump(moods, f)
    
    return jsonify({'status': 'success'})
@app.route('/get_moods')
@login_required
def get_moods():
    username = session.get('username')
    mood_file = f'instance/mood_data/{username}_moods.json'
    
    try:
        with open(mood_file, 'r') as f:
            moods = json.load(f)
            # Ensure moods are sorted by date
            moods.sort(key=lambda x: x['timestamp'])
            return jsonify({'moods': moods})
    except FileNotFoundError:
        return jsonify({'moods': []})

def save_to_csv(responses):
    # Get current user's email from session
    user_email = session.get('email')
    if not user_email:
        return
    
    # Load users to get username
    users = load_users()
    user = next((user for user in users if user['email'] == user_email), None)
    if not user:
        return
    
    username = user['name']
    
    # Create directory if it doesn't exist
    os.makedirs('responses/close_ended', exist_ok=True)
    
    # Define file path for this user
    file_path = f'responses/close_ended/{username}.csv'
    
    # Write responses to user's CSV file
    with open(file_path, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(['Question', 'Answer'])  # Write header
        for response in responses:
            writer.writerow(response)


@app.route('/open_ended', methods=['GET', 'POST'])
def submit_opended():
    if request.method == 'POST':
        responses = {key: value for key, value in request.form.items()}
        save_responses_to_csv(responses)
        return redirect(url_for('thank_you'))  # Corrected here
    else:
        random_questions = get_random_open_questions()  # Call the function from the imported file
        return render_template('open_ended.html', questions=random_questions)
    
    
def save_responses_to_csv(responses):
    # Get current user's email from session
    user_email = session.get('email')
    if not user_email:
        return
    
    # Load users to get username
    users = load_users()
    user = next((user for user in users if user['email'] == user_email), None)
    if not user:
        return
    
    username = user['name']
    
    # Create directory if it doesn't exist
    os.makedirs('responses/open_ended', exist_ok=True)
    
    # Define file path for this user
    file_path = f'responses/open_ended/{username}.csv'
    
    # Prepare the data to be saved
    data_to_save = [(question, responses[question]) for question in responses]
    
    # Create a DataFrame from the prepared data
    df = pd.DataFrame(data_to_save, columns=['Question', 'Response'])
    
    # Save to CSV
    df.to_csv(file_path, mode='w', index=False)

@app.route('/thank_you')
def thank_you():
    # Get the email from the session
    email = session.get('email')

    if email:
        # Load users from JSON file
        with open(USERS_FILE, 'r') as f:
            users = json.load(f)
        
        # Find user by email
        user = next((user for user in users if user['email'] == email), None)
        if user:
            user_name = user['name']
            # Read from user-specific files
            close_ended_str = csv_to_string(f"responses/close_ended/{user_name}.csv")
            open_ended_str = csv_to_string(f"responses/open_ended/{user_name}.csv")
        else:
            user_name = "Guest"
            close_ended_str = ""
            open_ended_str = ""
    else:
        user_name = "Guest"
        close_ended_str = ""
        open_ended_str = ""

    default = "This is my assessment of close-ended questions and open-ended questions. Please provide feedback on me in  friendly tone  in sumary like a professional psychiatrist , in english or hinglish or Minglish ."
    judge_gemini = gemini_chat(default + " " + close_ended_str + " " + open_ended_str)
    
    return render_template('thank_you.html', judge_gemini=judge_gemini, user_name=user_name, completejudege=judge_gemini)

@app.route('/feedback')
def feedback():
    # Check if user is logged in
    if 'username' not in session:
        return redirect(url_for('login'))
    
    username = session.get('username')
    user_file = f'instance/user_data/{username}.json'
    
    try:
        # Load existing user data
        with open(user_file, 'r') as f:
            user_data = json.load(f)
            
        # Check if wellness report exists
        if 'wellness_report' in user_data:
            judge_gemini = user_data['wellness_report']
        else:
            # Generate new report
            close_ended_str = csv_to_string(f"responses/close_ended/{username}.csv")
            open_ended_str = csv_to_string(f"responses/open_ended/{username}.csv")
            
            default = "This is my assessment of close-ended questions and open-ended questions. Please provide feedback on me in friendly tone in summary like a professional psychiatrist. in english "
            judge_gemini = gemini_chat(default + " " + close_ended_str + " " + open_ended_str)
            
            # Update user data with wellness report
            user_data['wellness_report'] = judge_gemini
            
            # Save updated user data
            with open(user_file, 'w') as f:
                json.dump(user_data, f, indent=4)
    
    except FileNotFoundError:
        # Initialize new user data with wellness report
        close_ended_str = csv_to_string(f"responses/close_ended/{username}.csv")
        open_ended_str = csv_to_string(f"responses/open_ended/{username}.csv")
        
        default = "This is my assessment of close-ended questions and open-ended questions. Please provide feedback on me in friendly tone in summary like a professional psychiatrist."
        judge_gemini = gemini_chat(default + " " + close_ended_str + " " + open_ended_str)
        
        user_data = {
            "age": "",  # You can add these from session or form data
            "gender": "",
            "occupation": "",
            "timestamp": datetime.now().isoformat(),
            "wellness_report": judge_gemini
        }
        
        # Save new user data
        os.makedirs('instance/user_data', exist_ok=True)
        with open(user_file, 'w') as f:
            json.dump(user_data, f, indent=4)
    
    return render_template('thank_you.html', 
                         judge_gemini=judge_gemini, 
                         user_name=username, 
                         completejudege=judge_gemini)

@app.route('/logout')
def logout():
    session.pop('email', None)
    return redirect('/login')


genai.configure(api_key=os.getenv("API_KEY"))
defaultprompt ="""you have to act as a sexologist , gynologist , neuroloigist also health guide  
        You are a professional, highly skilled mental doctor, and health guide.
        You act as a best friend to those who talk to you , but you have to talk based on their mental health , by seeing his age intrests qualities , if you dont know ask him indirectly by asking his/her studing or any work doing currently. 
        you can use the knowlege of geeta to make the user's mind more powerfull but you dont have to give reference of krishna or arjuna etc if the user is more towards god ( hindu gods ) then u can else wont
        You can assess if someone is under mental stress by judging their communication. 
        Your goal is to make them feel happy by cracking jokes and suggesting activities that bring joy. 
        If anyone asks anything outside your field, guide them or use your knowledge to help. 
        You can speak in Hindi, Marathi, Hinglish, or any language the user is comfortable with.
        your name is chikitsa , means Cognitive Health Intelligence Knowledge with Keen Interactive Treatment Support from AI."""
prompt = "this is my assesment of close ended questions and open ended questions , so you have to talk to me accordingly "
# Create the model
generation_config = {
  "temperature": 0.7,
  "top_p": 0.95,
  "top_k": 64,
  "max_output_tokens": 65536,
  "response_mime_type": "text/plain",
}

model = genai.GenerativeModel(
  model_name="gemini-2.0-flash-thinking-exp-01-21",
  generation_config=generation_config,
  system_instruction=defaultprompt+ prompt+ " " )#+close_ended_data+open_ended_data)


chat_session = model.start_chat()

# Chat function to handle user input
def gemini_chat(user_input, history_file="dataset/intents.json"):
    try:
        # Load intents from JSON or initialize
        if os.path.exists(history_file):
            with open(history_file, 'r') as f:
                intents_data = json.load(f)
        else:
            intents_data = {"intents": []}

        # Send user input to the model
        response = chat_session.send_message(user_input)

        # Create a new intent object for the conversation
        new_intent = {
            "patterns": [user_input],
            "responses": [response.text.strip()],
        }

        # Append the new intent to the intents list
        intents_data['intents'].insert(1, new_intent)

        # Save the updated intents JSON file
        with open(history_file, 'w') as f:
            json.dump(intents_data, f, indent=4)

        return response.text

    except Exception as e:
       
        response = chatbot_response(user_input)
        # Optionally log the error to a file
        with open('error.log', 'a') as log_file:
            log_file.write(f"{str(e)}\n")
        return response



def get_users_in_queue():
    users = load_users()
    queued_users = []
    
    for user in users:
        if user.get('questionnaire_completed') and not user.get('consultation_completed'):
            queued_users.append(user)
            
    return queued_users

@app.route('/admin/dashboard')
def admin_dashboard():
    if 'email' not in session:
        flash('Please login first', 'warning')
        return redirect('/login')
    
    if session.get('role') != 'admin':
        flash('Access restricted. Admin privileges required.', 'error')
        return redirect('/')
    
    # Load local users
    users = load_users()
    current_admin = session['email']
    
    # Load MeldRx users if connected
    meldrx_users = []
    if session.get('smart'):
        try:
            headers = {
                'Authorization': f"Bearer {session['smart']['access_token']}"
            }
            response = requests.get(
                'https://app.meldrx.com/api/users',
                headers=headers
            )
            if response.ok:
                meldrx_users = response.json()
        except Exception as e:
            flash(f'Failed to fetch MeldRx users: {str(e)}', 'error')
    
    return render_template(
        'admin_dashboard.html',
        users=users,
        meldrx_users=meldrx_users,
        current_admin=current_admin,
        admin_since=get_admin_info(current_admin)
    )

def get_admin_info(admin_email):
    users = load_users()
    for user in users:
        if user['email'] == admin_email:
            return user.get('created_at', 'Unknown')
    return 'Unknown'

@app.route('/admin/create_user', methods=['GET', 'POST'])
def create_user():
    if 'email' not in session or session.get('role') != 'admin':
        return redirect('/login')
    
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        role = request.form['role']
        
        users = load_users()
        
        if any(user['email'] == email for user in users):
            return render_template('create_user.html', error='Email already exists.')
        
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        new_user = {
            'name': name,
            'email': email,
            'password': hashed_password,
            'role': role,
            'created_at': datetime.now().isoformat(),
            'created_by': session['email']
        }
        
        users.append(new_user)
        
        with open(USERS_FILE, 'w') as f:
            json.dump(users, f, indent=4)
            
        return redirect('/admin/dashboard')
        
    return render_template('create_user.html')


@app.route('/admin/update_role/<user_email>', methods=['POST'])
def update_role(user_email):
    if 'email' not in session or session.get('role') != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    # Get the new role from form data
    new_role = request.form.get('new_role')
    
    if not new_role or new_role not in ['user', 'admin', 'doctor']:
        return jsonify({'success': False, 'message': 'Invalid role'}), 400

    # Load users from JSON file
    with open(USERS_FILE, 'r') as f:
        users = json.load(f)
    
    # Update user role
    user_found = False
    for user in users:
        if user['email'] == user_email:
            user['role'] = new_role
            user['updated_at'] = datetime.now().isoformat()
            user['updated_by'] = session['email']
            user_found = True
            break
    
    if not user_found:
        return jsonify({'success': False, 'message': 'User not found'}), 404
    
    # Save updated users back to JSON file
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, indent=4)
    
    return jsonify({'success': True, 'message': 'Role updated successfully'})



@app.route('/chat', methods=['GET', 'POST'])
def chat():
    if request.method == 'GET':
        return render_template('chat.html')
    elif request.method == 'POST':
        try:
            data = request.get_json()
            user_input = data.get('message')
            response = gemini_chat(user_input)
            return jsonify({'response': response})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

generation_config = {
    "temperature": 1,
    "top_p": 0.95,
    "top_k": 64,
    "max_output_tokens": 8192,
    "response_mime_type": "text/plain",
}

safety_settings = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
]

system_prompt = """
As a highly skilled medical practitioner specializing in image analysis, you are tasked with examining images for a renowned hospital. Your expertise is crucial in identifying any anomalies, diseases, or health issues that may be present in the images.
you have to analayse the image but and predict the cause or whats that 
Your Responsibilities include:

1. Detailed Analysis: Thoroughly analyze each image, focusing on identifying any abnormal findings.
2. Findings Report: Document all observed anomalies or signs of disease. Clearly articulate these findings in a structured format.
3. Recommendations and Next Steps: Based on your analysis, suggest potential next steps, including further tests or treatments as applicable.
4. Treatment Suggestions: If appropriate, recommend possible treatment options or interventions.

Important Notes:

1. Scope of Response: Only respond if the image pertains to human health issues.
2. Disclaimer: Accompany your analysis with the disclaimer: "Consult with a Doctor before making any decisions."
3. Your insights are invaluable in guiding clinical decisions. Please proceed with analysis, adhering to the structured approach outlined above.
"""
@app.route('/image_analysis', methods=['GET', 'POST'])
def image_analysis():
    analysis = None
    if request.method == 'POST':
        if 'file' not in request.files:
            return redirect(request.url)

        uploaded_file = request.files['file']
        if uploaded_file.filename == '':
            return redirect(request.url)

        if uploaded_file:
            # Process the uploaded image
            image_data = uploaded_file.read()

            # Prepare image parts
            image_parts = [{
                "mime_type": "image/jpeg",
                "data": image_data
            }]
            
            # Prepare the prompt parts
            prompt_parts = [
                image_parts[0],
                system_prompt,
            ]

            # Generate a response based on the prompt and image
            response = model.generate_content(prompt_parts)
            analysis = response.text
    return render_template('image_analysis.html', analysis=analysis)

import json
from pathlib import Path
from datetime import datetime

RATINGS_FILE = Path('instance/rating/ratings.json')

def load_ratings():
    if RATINGS_FILE.exists():
        with open(RATINGS_FILE, 'r') as f:
            return json.load(f)
    return {"ratings": []}

def save_ratings(ratings_data):
    RATINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(RATINGS_FILE, 'w') as f:
        json.dump(ratings_data, f, indent=4)

@app.route('/save_rating', methods=['POST'])
def save_rating():
    data = request.json
    ratings_data = load_ratings()
    
    # Find user's existing ratings
    user_ratings = [r for r in ratings_data["ratings"] if r["user_name"] == data["user_name"]]
    
    new_rating = {
        "n": len(user_ratings) + 1,
        "user_name": data["user_name"],
        "Wellness-rating": data["rating"],
        "timestamp": datetime.now().isoformat()
    }
    
    ratings_data["ratings"].append(new_rating)
    save_ratings(ratings_data)
    
    return jsonify({"success": True, "rating_number": new_rating["n"]})

from fer import FER
# # Initialize emotion detection model
emotion_detector = FER(mtcnn=True)


# Initialize global variables
attention_status = "Not Paying Attention"
dominant_emotion = "neutral"  # Default value

def is_paying_attention(emotions_dict, threshold=0.5):
    """ Checks if the user is paying attention based on emotion scores. """
    dominant_emotion = max(emotions_dict, key=emotions_dict.get)
    emotion_score = emotions_dict[dominant_emotion]
    return emotion_score > threshold, dominant_emotion

def detect_emotion_and_attention(frame):
    """ Detects emotion and attention from the frame. """
    global attention_status, dominant_emotion

    # Flip the frame horizontally for display
    display_frame = cv2.flip(frame.copy(), 1)
    
    # Detect emotions on the original frame
    results = emotion_detector.detect_emotions(frame)

    for result in results:
        bounding_box = result["box"]
        emotions_dict = result["emotions"]

        # Update attention status and dominant emotion
        paying_attention, dominant_emotion = is_paying_attention(emotions_dict)
        attention_status = "Paying Attention" if paying_attention else "Not Paying Attention"

        # Adjust bounding box coordinates for flipped frame
        x, y, w, h = bounding_box
        flipped_x = display_frame.shape[1] - (x + w)  # Calculate flipped x coordinate

        # Draw bounding box and display emotion info on the flipped frame
        cv2.rectangle(display_frame, (flipped_x, y), (flipped_x + w, y + h), (255, 0, 0), 2)
        
        # Add emotion text with adjusted positioning
        emotion_text = ", ".join([f"{emotion}: {prob:.2f}" for emotion, prob in emotions_dict.items()])
        cv2.putText(display_frame, f"{dominant_emotion} ({attention_status})", 
                    (flipped_x, y - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        cv2.putText(display_frame, emotion_text, 
                    (flipped_x, y + h + 20), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)

    return display_frame

def generate_frames():
    """ Captures frames from the webcam and detects emotion and attention. """
    cap = cv2.VideoCapture(0)
    
    while True:
        success, frame = cap.read()
        if not success:
            break

        processed_frame = detect_emotion_and_attention(frame)
        _, buffer = cv2.imencode('.jpg', processed_frame)
        frame = buffer.tobytes()

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

    cap.release()

# Flask route for the chatbot interaction
@app.route('/talk_to_me', methods=['GET', 'POST'])
def talk_to_me():
    """ Handles the user's input and sends it to the chatbot along with emotion and attention. """
    global attention_status, dominant_emotion

    if request.method == 'GET':
        return render_template('talk_to_me.html')

    elif request.method == 'POST':
        user_input = request.form.get('user_input', '')

        # Create the prompt with the attention status and emotion
        prompt = f"The user is in a {dominant_emotion} mood and is {'paying attention' if attention_status == 'Paying Attention' else 'not paying attention'}."

        # Call the gemini_chat function with the user input and the generated prompt
        bot_response = gemini_chat(user_input + " " + prompt)

        return jsonify({'response': bot_response})

    else:
        return "Unsupported request method", 405

def log_conversation(user_input, bot_response, history_file="dataset/intents.json"):
    # Load or initialize intents data
    if os.path.exists(history_file):
        with open(history_file, 'r') as f:
            intents_data = json.load(f)
    else:
        intents_data = {"intents": []}

    # Create a new intent object
    new_intent = {
        "patterns": [user_input],
        "responses": [bot_response],
    }

    # Append the new intent
    intents_data['intents'].append(new_intent)

    # Save the updated intents JSON file
    with open(history_file, 'w') as f:
        json.dump(intents_data, f, indent=4)

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')




# Add these routes after existing routes
@app.route('/appointment')
@login_required
def appointment():
    if session.get('role') == 'doctor':
        return redirect(url_for('doctor_dashboard'))
    return render_template('patient_dashboard.html')

@app.route('/doctor/dashboard')
@login_required
def doctor_dashboard():
    if session.get('role') != 'doctor':
        return redirect(url_for('appointment'))
    return render_template('doctor_dashboard.html')

@app.route('/api/appointments', methods=['GET', 'POST'])
@login_required
def handle_appointments():
    username = session.get('username')
    appointments_file = f'instance/appointments/{username}.json'
    os.makedirs('instance/appointments', exist_ok=True)
    
    if request.method == 'GET':
        try:
            with open(appointments_file, 'r') as f:
                appointments = json.load(f)
            return jsonify(appointments)
        except FileNotFoundError:
            return jsonify([])
    
    elif request.method == 'POST':
        data = request.json
        appointment_date = datetime.strptime(data['date'], '%Y-%m-%d')
        
        # Check if it's weekend
        if appointment_date.weekday() >= 5:  # 5=Saturday, 6=Sunday
            return jsonify({'error': 'No appointments on weekends'}), 400
            
        try:
            with open(appointments_file, 'r') as f:
                appointments = json.load(f)
        except FileNotFoundError:
            appointments = []

        # Check weekly limit (1 per week)
        week_start = appointment_date - timedelta(days=appointment_date.weekday())
        week_end = week_start + timedelta(days=6)
        week_appointments = [a for a in appointments 
                           if week_start <= datetime.strptime(a['date'], '%Y-%m-%d') <= week_end
                           and a['status'] != 'cancelled']
        
        if len(week_appointments) >= 1:
            return jsonify({'error': 'Maximum 1 appointment per week allowed'}), 400

        # Check monthly limit (4 per month)
        month_start = appointment_date.replace(day=1)
        month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        month_appointments = [a for a in appointments 
                            if month_start <= datetime.strptime(a['date'], '%Y-%m-%d') <= month_end
                            and a['status'] != 'cancelled']
        
        if len(month_appointments) >= 4:
            return jsonify({'error': 'Maximum 4 appointments per month allowed'}), 400

        new_appointment = {
            'id': len(appointments) + 1,
            'patient': username,
            'date': data['date'],
            'slot': data['slot'],
            'status': 'pending',
            'created_at': datetime.now().isoformat(),
            'cancellation_reason': None
        }
        
        appointments.append(new_appointment)
        
        # Update appointment stats
        update_appointment_stats(username, 'booked', appointment_date)
        
        with open(appointments_file, 'w') as f:
            json.dump(appointments, f, indent=4)
            
        return jsonify(new_appointment)
    
def update_appointment_stats(username, action, date):
    stats_file = f'instance/appointment_stats/{username}.json'
    os.makedirs('instance/appointment_stats', exist_ok=True)
    
    try:
        with open(stats_file, 'r') as f:
            stats = json.load(f)
    except FileNotFoundError:
        stats = {
            'total_appointments': 0,
            'total_cancellations': 0,
            'yearly_stats': {},
            'monthly_stats': {},
            'rating': 'white'  # default rating
        }
    
    year = str(date.year)
    month = str(date.month)
    
    if year not in stats['yearly_stats']:
        stats['yearly_stats'][year] = {'booked': 0, 'cancelled': 0}
    if month not in stats['monthly_stats']:
        stats['monthly_stats'][month] = {'booked': 0, 'cancelled': 0}
        
    if action == 'booked':
        stats['total_appointments'] += 1
        stats['yearly_stats'][year]['booked'] += 1
        stats['monthly_stats'][month]['booked'] += 1
    elif action == 'cancelled':
        stats['total_cancellations'] += 1
        stats['yearly_stats'][year]['cancelled'] += 1
        stats['monthly_stats'][month]['cancelled'] += 1
        
    # Update rating based on cancellation rate
    monthly_cancel_rate = stats['monthly_stats'][month]['cancelled'] / max(stats['monthly_stats'][month]['booked'], 1)
    
    if monthly_cancel_rate < 0.1:
        stats['rating'] = 'blue'    # genuine patient
    elif monthly_cancel_rate > 0.4:
        stats['rating'] = 'red'     # frequent canceller
    else:
        stats['rating'] = 'white'   # normal patient
        
    with open(stats_file, 'w') as f:
        json.dump(stats, f, indent=4)
@app.route('/api/appointments/<int:appointment_id>', methods=['PUT'])
@login_required
def update_appointment(appointment_id):
    if session.get('role') != 'doctor':
        return jsonify({'error': 'Unauthorized'}), 401

    appointments_dir = 'instance/appointments'
    doctor_username = session.get('username')
    doctor_appointments_dir = 'instance/doctor_appointments'
    doctor_file = f'{doctor_appointments_dir}/{doctor_username}.json'

    # Ensure doctor appointments directory exists
    os.makedirs(doctor_appointments_dir, exist_ok=True)

    for filename in os.listdir(appointments_dir):
        if not filename.endswith('.json'):
            continue

        file_path = os.path.join(appointments_dir, filename)
        with open(file_path, 'r') as f:
            appointments = json.load(f)
            appointment = next((a for a in appointments if a['id'] == appointment_id), None)
            
            if not appointment:
                continue

            # Update appointment status
            appointment['status'] = request.json['status']
            
            # Save updated patient appointments
            with open(file_path, 'w') as f:
                json.dump(appointments, f, indent=4)

            # Handle doctor's appointments
            try:
                with open(doctor_file, 'r') as f:
                    doctor_appointments = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                doctor_appointments = []

            # Create new doctor appointment entry
            new_doctor_appointment = {
                'appointment_id': appointment_id,
                'patient': filename[:-5],
                'date': appointment['date'],
                'slot': appointment['slot'],
                'status': request.json['status'],
                'patient_info': get_user_basic_info(filename[:-5]),
                'updated_at': datetime.now().isoformat()
            }

            # Add to doctor's appointments
            doctor_appointments.append(new_doctor_appointment)

            # Save doctor's appointments
            with open(doctor_file, 'w') as f:
                json.dump(doctor_appointments, f, indent=4)

            return jsonify({'success': True})

    return jsonify({'error': 'Appointment not found'}), 404

def get_user_appointment_stats(username):
    stats_file = f'instance/appointment_stats/{username}.json'
    os.makedirs('instance/appointment_stats', exist_ok=True)
    
    try:
        with open(stats_file, 'r') as f:
            stats = json.load(f)
    except FileNotFoundError:
        stats = {
            'total_appointments': 0,
            'total_cancellations': 0,
            'yearly_stats': {},
            'monthly_stats': {},
            'rating': 'white'  # default rating
        }
    
    return stats

def calculate_patient_rating(username):
    stats = get_user_appointment_stats(username)
    monthly_appointments = stats['monthly_stats'].get(str(datetime.now().month), {})
    
    if not monthly_appointments:
        return 'white'
        
    total = monthly_appointments.get('booked', 0)
    cancelled = monthly_appointments.get('cancelled', 0)
    
    if total == 0:
        return 'white'
        
    cancel_rate = cancelled / total
    
    if cancel_rate < 0.1:
        return 'blue'
    elif cancel_rate > 0.4:
        return 'red'
    return 'white'

@app.route('/api/appointments/cancel/<int:appointment_id>', methods=['POST'])
@login_required
def cancel_appointment(appointment_id):
    username = session.get('username')
    appointments_file = f'instance/appointments/{username}.json'
    
    with open(appointments_file, 'r') as f:
        appointments = json.load(f)
    
    appointment = next((a for a in appointments if a['id'] == appointment_id), None)
    if appointment:
        appointment['status'] = 'cancelled'
        appointment['cancellation_reason'] = request.json.get('reason')
        
        # Update cancellation stats
        appointment_date = datetime.strptime(appointment['date'], '%Y-%m-%d')
        update_appointment_stats(username, 'cancelled', appointment_date)
        
        with open(appointments_file, 'w') as f:
            json.dump(appointments, f, indent=4)
            
        return jsonify({'success': True})
    
    return jsonify({'error': 'Appointment not found'}), 404

@app.route('/api/doctor/appointments', methods=['GET'])
@login_required
def get_all_appointments():
    if session.get('role') != 'doctor':
        return jsonify({'error': 'Unauthorized'}), 401
        
    all_appointments = []
    appointments_dir = 'instance/appointments'
    
    for filename in os.listdir(appointments_dir):
        if filename.endswith('.json'):
            username = filename[:-5]
            with open(os.path.join(appointments_dir, filename), 'r') as f:
                user_appointments = json.load(f)
                
            # Get user's rating
            stats_file = f'instance/appointment_stats/{username}.json'
            with open(stats_file, 'r') as f:
                stats = json.load(f)
                
            for appointment in user_appointments:
                appointment['patient_rating'] = stats['rating']
                all_appointments.append(appointment)
    
    # Sort by rating priority (blue > white > red)
    rating_priority = {'blue': 0, 'white': 1, 'red': 2}
    all_appointments.sort(key=lambda x: (rating_priority[x['patient_rating']], x['created_at']))
    
    return jsonify(all_appointments)

@app.route('/api/user/stats', methods=['GET'])
@login_required
def get_user_stats():
    username = session.get('username')
    return jsonify(get_user_appointment_stats(username))

# Constants for time slots
AVAILABLE_SLOTS = [
    '10:00-11:00',
    '12:00-13:00',
    '15:00-16:00',
    '17:00-18:00'
]

@app.route('/api/available-slots', methods=['GET'])
@login_required
def get_available_slots():
    return jsonify(AVAILABLE_SLOTS)

@app.route('/api/doctor/patient-info/<username>', methods=['GET'])
@login_required
def get_patient_info(username):
    if session.get('role') != 'doctor':
        return jsonify({'error': 'Unauthorized'}), 401
        
    patient_info = {
        'basic_info': get_user_basic_info(username),
        'appointment_history': get_appointment_history(username),
        'mood_history': get_mood_history(username),
        'questionnaire_responses': get_questionnaire_responses(username)
    }
    
    return jsonify(patient_info)

def check_appointment_limits(username, appointment_date):
    appointments_file = f'instance/appointments/{username}.json'
    
    try:
        with open(appointments_file, 'r') as f:
            appointments = json.load(f)
    except FileNotFoundError:
        return True, None
        
    # Weekly limit check
    week_start = appointment_date - timedelta(days=appointment_date.weekday())
    week_end = week_start + timedelta(days=6)
    week_appointments = [a for a in appointments 
                        if week_start <= datetime.strptime(a['date'], '%Y-%m-%d') <= week_end
                        and a['status'] != 'cancelled']
    
    if len(week_appointments) >= 1:
        return False, "Weekly limit reached (maximum 1 appointment per week)"
        
    # Monthly limit check
    month_start = appointment_date.replace(day=1)
    month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    month_appointments = [a for a in appointments 
                         if month_start <= datetime.strptime(a['date'], '%Y-%m-%d') <= month_end
                         and a['status'] != 'cancelled']
    
    if len(month_appointments) >= 4:
        return False, "Monthly limit reached (maximum 4 appointments per month)"
        
    return True, None
   
def save_appointment(username, appointment_data):
    os.makedirs('instance/appointments', exist_ok=True)
    file_path = f'instance/appointments/{username}.json'
    
    try:
        with open(file_path, 'r') as f:
            appointments = json.load(f)
    except FileNotFoundError:
        appointments = []
        
    appointments.append(appointment_data)
    
    with open(file_path, 'w') as f:
        json.dump(appointments, f, indent=4)

def get_user_basic_info(username):
    """Get basic user information from user data file"""
    try:
        with open(f'instance/user_data/{username}.json', 'r') as f:
            user_data = json.load(f)
        return user_data
    except FileNotFoundError:
        return {
            'age': 'Unknown',
            'gender': 'Unknown',
            'occupation': 'Unknown'
        }

def get_appointment_history(username):
    """Get user's appointment history"""
    try:
        with open(f'instance/appointments/{username}.json', 'r') as f:
            appointments = json.load(f)
        return appointments
    except FileNotFoundError:
        return []

def get_mood_history(username):
    """Get user's mood tracking history"""
    try:
        with open(f'instance/mood_data/{username}_moods.json', 'r') as f:
            moods = json.load(f)
        return moods
    except FileNotFoundError:
        return []

def get_questionnaire_responses(username):
    """Get user's questionnaire responses"""
    responses = {
        'close_ended': [],
        'open_ended': []
    }
    
    # Get close-ended responses
    try:
        with open(f'responses/close_ended/{username}.csv', 'r') as f:
            reader = csv.DictReader(f)
            responses['close_ended'] = list(reader)
    except FileNotFoundError:
        pass
        
    # Get open-ended responses
    try:
        with open(f'responses/open_ended/{username}.csv', 'r') as f:
            reader = csv.DictReader(f)
            responses['open_ended'] = list(reader)
    except FileNotFoundError:
        pass
        
    return responses



app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'your-email@gmail.com'
app.config['MAIL_PASSWORD'] = 'your-app-password'
mail = Mail(app)

def send_appointment_reminder(recipient_email, appointment_data, reminder_type):
    """Send email reminder for appointment"""
    
    subject_templates = {
        'day_before': "🗓️ Your Appointment Tomorrow - CHIKITSA Wellness",
        'hours_before': "⏰ Your Appointment Today - CHIKITSA Wellness"
    }
    
    body_templates = {
        'day_before': """
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f5f9ff; border-radius: 10px;">
            <h2 style="color: #4a90e2; text-align: center;">Appointment Reminder</h2>
            <p>Dear {patient_name},</p>
            <p>This is a friendly reminder about your appointment tomorrow:</p>
            <div style="background-color: white; padding: 15px; border-radius: 5px; margin: 15px 0;">
                <p><strong>Date:</strong> {appointment_date}</p>
                <p><strong>Time:</strong> {appointment_time}</p>
                <p><strong>Doctor:</strong> Dr. {doctor_name}</p>
            </div>
            <p>Please ensure you're available 5 minutes before your scheduled time.</p>
            <p style="color: #666;">If you need to reschedule, please do so at least 4 hours before the appointment.</p>
            <div style="text-align: center; margin-top: 20px;">
                <p style="color: #4a90e2;">CHIKITSA Wellness - Your Path to Better Health</p>
            </div>
        </div>
        """,
        'hours_before': """
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f5f9ff; border-radius: 10px;">
            <h2 style="color: #4a90e2; text-align: center;">⚡ Your Appointment is Coming Up!</h2>
            <p>Dear {patient_name},</p>
            <p>Your appointment is scheduled in a few hours:</p>
            <div style="background-color: white; padding: 15px; border-radius: 5px; margin: 15px 0;">
                <p><strong>Time:</strong> {appointment_time}</p>
                <p><strong>Doctor:</strong> Dr. {doctor_name}</p>
            </div>
            <p style="color: #e74c3c;">Please be ready 5 minutes before your scheduled time.</p>
            <div style="text-align: center; margin-top: 20px;">
                <a href="{meeting_link}" style="background-color: #4a90e2; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Join Meeting</a>
            </div>
        </div>
        """
    }
    
    msg = Message(
        subject=subject_templates[reminder_type],
        recipients=[recipient_email],
        html=body_templates[reminder_type].format(
            patient_name=appointment_data['patient'],
            appointment_date=appointment_data['date'],
            appointment_time=appointment_data['slot'],
            doctor_name=appointment_data['doctor'],
            meeting_link=appointment_data.get('meet_link', '#')
        )
    )
    
    mail.send(msg)

# def check_and_send_reminders():
#     """Check for appointments and send reminders"""
#     appointments_dir = 'instance/appointments'
    
#     for filename in os.listdir(appointments_dir):
#         if filename.endswith('.json'):
#             with open(os.path.join(appointments_dir, filename), 'r') as f:
#                 appointments = json.load(f)
                
#             for appointment in appointments:
#                 if appointment['status'] != 'accepted':
#                     continue
                    
#                 appointment_datetime = datetime.strptime(
#                     f"{appointment['date']} {appointment['slot'].split('-')[0]}", 
#                     '%Y-%m-%d %H:%M'
#                 )
#                 now = datetime.now()
                
#                 # Send day before reminder
#                 if (appointment_datetime - now).days == 1:
#                     send_appointment_reminder(
#                         get_user_email(appointment['patient']),
#                         appointment,
#                         'day_before'
#                     )
                
#                 # Send 2-hour before reminder
#                 elif timedelta(hours=0) <= (appointment_datetime - now) <= timedelta(hours=2):
#                     send_appointment_reminder(
#                         get_user_email(appointment['patient']),
#                         appointment,
#                         'hours_before'
#                     )

# def start_reminder_scheduler():
#     """Start the reminder scheduler in a separate thread"""
#     def run_scheduler():
#         schedule.every(30).minutes.do(check_and_send_reminders)
#         while True:
#             schedule.run_pending()
#             time.sleep(60)
    
#     scheduler_thread = threading.Thread(target=run_scheduler)
#     scheduler_thread.daemon = True
#     scheduler_thread.start()

# # Start the reminder scheduler when the app starts
# @app.before_first_request
# def initialize_reminder_system():
#     start_reminder_scheduler()

from flask import Flask, redirect, session, request, render_template, flash
from fhirclient import client
from fhirclient.models.questionnaireresponse import QuestionnaireResponse
import google.generativeai as genai
import secrets
import base64
import hashlib
import os

# SMART on FHIR Configuration for MeldRx
MELDRX_CONFIG = {
    'app_id': '3aec544d06aa406e8c6363fa546cd728',
    'api_base': 'https://app.meldrx.com/api/fhir/0f8ca64e-a18b-4117-82e3-23bd48ba346c',
    'redirect_uri': 'http://localhost:5000/callback',
    'client_id': '3aec544d06aa406e8c6363fa546cd728',
    'client_secret': 'jDZP4pd0AXSZ_KHVfezo7lXMufrs0E',
    'scope': 'offline_access openid fhirUser launch/patient patient/*.read',
    'authorize_url': 'https://app.meldrx.com/oauth/authorize',
    'token_url': 'https://app.meldrx.com/oauth/token'
}  
from functools import wraps
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'smart' not in session:  # Align with /analyze route’s auth
            return redirect('/launch')
        return f(*args, **kwargs)
    return decorated_function

# Existing routes (unchanged)
def generate_code_verifier():
    return secrets.token_urlsafe(64)[:128]

def generate_code_challenge(code_verifier):
    code_challenge = hashlib.sha256(code_verifier.encode('utf-8')).digest()
    return base64.urlsafe_b64encode(code_challenge).decode('utf-8').rstrip('=')

# @app.route('/launch')
# def launch():
#     code_verifier = generate_code_verifier()
#     code_challenge = generate_code_challenge(code_verifier)
#     session['code_verifier'] = code_verifier
    
#     smart = client.FHIRClient(settings=MELDRX_CONFIG)
#     smart.prepare()
#     authorize_url = f"{smart.authorize_url}&code_challenge={code_challenge}&code_challenge_method=S256"
#     return redirect(authorize_url)
@app.route('/launch')
def launch():
    smart = client.FHIRClient(settings=MELDRX_CONFIG)
    smart.prepare()
    session['state'] = smart.state
    return redirect(smart.authorize_url)

@app.route('/callback')
def callback():
    request_state = request.args.get('state')
    if request_state != session.get('state'):
        return "State mismatch error - possible security issue", 400
    smart = client.FHIRClient(state=request_state)
    smart.handle_callback(request.url)
    session['smart'] = smart.to_dict()
    return redirect('/analyze')
if __name__ == "__main__":
    app.run(debug=True)
    