from fhirclient.models.patient import Patient as FHIRPatient
from fhirclient.models.humanname import HumanName
from fhirclient.models.contactpoint import ContactPoint
from datetime import datetime

def create_fhir_patient(user_data):
    """Convert user data to FHIR Patient resource"""
    patient = FHIRPatient()
    
    # Set name
    name = HumanName()
    name.text = user_data['name']
    patient.name = [name]
    
    # Set email
    email = ContactPoint()
    email.system = 'email'
    email.value = user_data['email']
    patient.telecom = [email]
    
    # Set gender if available
    if 'gender' in user_data:
        patient.gender = user_data['gender'].lower()
    
    # Set age/birthDate if available
    if 'age' in user_data:
        birth_year = datetime.now().year - int(user_data['age'])
        patient.birthDate = f"{birth_year}-01-01"
    
    # Set occupation as an extension
    if 'occupation' in user_data:
        patient.extension = [{
            "url": "http://hl7.org/fhir/StructureDefinition/patient-occupation",
            "valueString": user_data['occupation']
        }]
    
    return patient