from flask import Blueprint, redirect, session , request , jsonify , logging
from fhirclient import client
from smart_config import MELDRX_CONFIG, get_fhir_data, get_meldrx_users

smart_bp = Blueprint('smart', __name__)

@smart_bp.route('/launch')
def launch():
    """Launch SMART app"""
    smart = client.FHIRClient(settings=MELDRX_CONFIG)
    auth_url = smart.authorize_url
    session['state'] = smart.state
    return redirect(auth_url)

@smart_bp.route('/callback')
def callback():
    """Handle SMART auth callback"""
    try:
        # Get auth code from request
        code = request.args.get('code')
        state = request.args.get('state')
        
        if not code or not state:
            raise ValueError("Missing auth parameters")
            
        if state != session.get('state'):
            raise ValueError("State mismatch")
            
        # Exchange code for token
        smart = client.FHIRClient(state=state)
        smart.handle_callback(request.url)
        
        # Store token in session
        session['smart'] = {
            'access_token': smart.access_token,
            'patient_id': smart.patient_id,
            'user_id': smart.user_id
        }
        
        return redirect('/home')
        
    except Exception as e:
        # Log error and redirect to home
        logging.error(f"SMART callback error: {str(e)}")
        return redirect('/home')

@smart_bp.route('/admin/users/smart')
def smart_users():
    """Get SMART users for admin"""
    if session.get('role') != 'admin':
        return redirect('/home')
        
    try:
        meldrx_users = get_meldrx_users()
        return jsonify(meldrx_users)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@smart_bp.route('/patient/<patient_id>')
def get_patient(patient_id):
    """Get patient data from FHIR server"""
    try:
        patient_data = get_fhir_data('Patient', patient_id)
        if not patient_data:
            return jsonify({'error': 'Patient not found'}), 404
        return jsonify(patient_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500