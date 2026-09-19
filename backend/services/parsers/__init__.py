from .passport_parser import PassportParser
from .visa_parser import VisaParser
from .aadhaar_parser import AadhaarParser
from .pan_parser import PANParser
from .voter_id_parser import VoterIDParser
from .driving_license_parser import DrivingLicenseParser
from .permit_parser import PermitParser

PARSERS = {p.document_type: p for p in [
    PassportParser(),        # "passport"
    VisaParser(),            # "visa"
    AadhaarParser(),         # "aadhaar"
    PANParser(),             # "pan"
    VoterIDParser(),         # "voter_id"
    DrivingLicenseParser(),  # "driving_license"
    PermitParser(),          # "permit"
]}