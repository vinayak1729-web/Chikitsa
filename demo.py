from flask import Flask, redirect, session, request, render_template, flash
from fhirclient import client
from fhirclient.models.questionnaireresponse import QuestionnaireResponse
import google.generativeai as genai
import secrets
import base64
import hashlib
import os

app = Flask(__name__)
app.secret_key = 'secret_key'  # Replace with a secure key in production

# MELDRX_CONFIG remains unchanged
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

# Configure Google Generative AI (unchanged)
genai.configure(api_key=os.getenv("API_KEY"))

# Model configurations (unchanged)
model = genai.GenerativeModel(
    model_name="gemini-2.0-flash-thinking-exp-01-21",
    generation_config={"temperature": 0.7, "top_p": 0.95, "top_k": 64, "max_output_tokens": 65536},
    system_instruction="You are a professional mental health doctor. Analyze the patient's questionnaire responses and provide a detailed assessment, including predictions about their mental health status and recommendations for next steps."
)

image_analysis_prompt = """
As a highly skilled medical practitioner specializing in image analysis, you are tasked with examining images for a renowned hospital. Your expertise is crucial in identifying any anomalies, diseases, or health issues that may be present in the images.
Your Responsibilities include:
1. Detailed Analysis: Thoroughly analyze each image, focusing on identifying any abnormal findings.
2. Findings Report: Document all observed anomalies or signs of disease. Clearly articulate these findings in a structured format.
3. Recommendations and Next Steps: Based on your analysis, suggest potential next steps, including further tests or treatments as applicable.
4. Treatment Suggestions: If appropriate, recommend possible treatment options or interventions.
Important Notes:
1. Scope of Response: Only respond if the image pertains to human health issues.
2. Disclaimer: Accompany your analysis with the disclaimer: 'Consult with a Doctor before making any decisions.'
3. Your insights are invaluable in guiding clinical decisions. Please proceed with analysis, adhering to the structured approach outlined above.
"""
image_analysis_model = genai.GenerativeModel(
    model_name="gemini-2.0-flash-thinking-exp-01-21",
    generation_config={"temperature": 0.7, "top_p": 0.95, "top_k": 64, "max_output_tokens": 65536},
    system_instruction=image_analysis_prompt
)

# Helper functions (unchanged)
def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def generate_code_verifier():
    return secrets.token_urlsafe(64)[:128]

def generate_code_challenge(code_verifier):
    code_challenge = hashlib.sha256(code_verifier.encode('utf-8')).digest()
    return base64.urlsafe_b64encode(code_challenge).decode('utf-8').rstrip('=')

# Login required decorator (unchanged)
from functools import wraps
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'smart' not in session:
            return redirect('/launch')
        return f(*args, **kwargs)
    return decorated_function

# Updated /launch route
@app.route('/launch')
def launch():
    code_verifier = generate_code_verifier()
    code_challenge = generate_code_challenge(code_verifier)
    session['code_verifier'] = code_verifier
    
    smart = client.FHIRClient(settings=MELDRX_CONFIG)
    smart.prepare()
    session['state'] = smart.state  # Store state in session
    authorize_url = f"{smart.authorize_url}&code_challenge={code_challenge}&code_challenge_method=S256"
    return redirect(authorize_url)

@app.route('/callback')
def callback():
    request_state = request.args.get('state')
    if request_state != session.get('state'):
        return "State mismatch error - possible security issue", 400
    
    # Initialize FHIR client with both settings and state
    smart = client.FHIRClient(settings=MELDRX_CONFIG, state=request_state)
    
    # Handle the OAuth callback
    smart.handle_callback(request.url)
    session['smart'] = smart.to_dict()
    return redirect('/analyze')

# /analyze route (unchanged)
@app.route('/analyze')
def analyze():
    if 'smart' not in session:
        return redirect('/launch')
    
    smart = client.FHIRClient(state=session['smart'])
    patient_id = smart.patient_id
    search = QuestionnaireResponse.where({'patient': patient_id})
    responses = search.perform_resources(smart.server)
    
    response_text = ""
    for resp in responses:
        for item in resp.item or []:
            question = item.text
            answer = item.answer[0].valueString if item.answer else "No answer"
            response_text += f"Q: {question}\nA: {answer}\n"
    
    prompt = f"Analyze these questionnaire responses and provide a mental health assessment:\n{response_text}"
    analysis = model.generate_content(prompt).text
    
    return render_template('analysis.html', analysis=analysis)

# /image_analysis route (unchanged)
@app.route('/image_analysis', methods=['GET', 'POST'])
@login_required
def image_analysis():
    analysis = None
    error = None
    if request.method == 'POST':
        if 'file' not in request.files:
            error = 'No file uploaded'
        else:
            uploaded_file = request.files['file']
            if uploaded_file.filename == '':
                error = 'No file selected'
            elif not allowed_file(uploaded_file.filename):
                error = 'Invalid file type. Please upload an image (png, jpg, jpeg, gif).'
            else:
                try:
                    image_data = uploaded_file.read()
                    image_part = {"mime_type": "image/jpeg", "data": image_data}
                    response = image_analysis_model.generate_content([image_part])
                    analysis = response.text
                except Exception as e:
                    error = f"Error analyzing image: {str(e)}"
    return render_template('image_analysis.html', analysis=analysis, error=error)

# Run the app
if __name__ == '__main__':
    app.run(debug=True, port=8000)

