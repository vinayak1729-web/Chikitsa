from fhirclient import client
from flask import session, redirect
import requests
from functools import wraps
import logging
from .fhir_models import ChikitsaPatient as Patient
from .fhir_models import ChikitsaPractitioner as Practitioner
# SMART on FHIR Configuration
MELDRX_CONFIG = {
    'app_id': '462ef5aa1efc4eb1b69d517846a6f65a',  
    'api_base': 'https://app.meldrx.com/api/fhir/0f8ca64e-a18b-4117-82e3-23bd48ba346c',
    'redirect_uri': 'http://localhost:5000/callback',
    'client_id': '462ef5aa1efc4eb1b69d517846a6f65a',
    'scope': 'launch patient/*.* user/*.* launch/patient launch/encounter'
}

class FHIRError(Exception):
    pass

def handle_fhir_error(func):
    @wraps(func) 
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logging.error(f"FHIR Error: {str(e)}")
            raise FHIRError(f"FHIR operation failed: {str(e)}")
    return wrapper

def get_fhir_client():
    """Get FHIR client instance"""
    if 'smart' not in session:
        return None
    return client.FHIRClient(state=session['smart'])

def get_fhir_data(resource_type, resource_id):
    """Get FHIR resource data"""
    smart = get_fhir_client()
    if not smart:
        return None
        
    if resource_type == 'Patient':
        return Patient.read(resource_id, smart.server).as_json()
    elif resource_type == 'Practitioner':
        return Practitioner.read(resource_id, smart.server).as_json()

@handle_fhir_error
def get_meldrx_users():
    """Get users from MeldRx"""
    if not session.get('smart'):
        return []
        
    headers = {
        'Authorization': f"Bearer {session['smart']['access_token']}"
    }
    response = requests.get(
        'https://app.meldrx.com/api/users',
        headers=headers
    )
    return response.json()
