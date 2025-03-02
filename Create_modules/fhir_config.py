from fhirclient import client
from fhirclient.models.patient import Patient
from fhirclient.models.humanname import HumanName
from fhirclient.models.contactpoint import ContactPoint

FHIR_SETTINGS = {
    'app_id': '462ef5aa1efc4eb1b69d517846a6f65a',
    'api_base': 'https://app.meldrx.com/api/fhir/0f8ca64e-a18b-4117-82e3-23bd48ba346c',
    'redirect_uri': 'http://localhost:5000/callback',
    'client_id': '462ef5aa1efc4eb1b69d517846a6f65a',
    'scope': 'launch patient/*.* user/*.* launch/patient launch/encounter'
}

def get_fhir_client():
    smart = client.FHIRClient(settings=FHIR_SETTINGS)
    return smart

def create_patient(user_data):
    patient = Patient()
    
    # Set name
    name = HumanName()
    name.text = user_data['name']
    patient.name = [name]
    
    # Set contact info
    contact = ContactPoint()
    contact.system = 'email'
    contact.value = user_data['email']
    patient.telecom = [contact]
    
    return patient