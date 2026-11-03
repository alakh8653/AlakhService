"""Which documents each type of work has to show before an admin reviews it.

Required only where Indian law plainly asks for the document to do the work at all; the rest are recommended,
because rules such as a wireman's licence differ from state to state and must not keep honest people out.
Categories are the ids in the apps' service type lists (mobile service_types.dart, dashboard categories.ts).
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

REGISTRATION = "PROFESSIONAL_REGISTRATION"
LICENCE = "TRADE_LICENCE"
QUALIFICATION = "QUALIFICATION"
DRIVING_LICENCE = "DRIVING_LICENCE"
FOOD_LICENCE = "FOOD_LICENCE"
POLICE_VERIFICATION = "POLICE_VERIFICATION"
WORK_PHOTO = "WORK_PHOTO"

CREDENTIAL_TYPES = (
    REGISTRATION,
    LICENCE,
    QUALIFICATION,
    DRIVING_LICENCE,
    FOOD_LICENCE,
    POLICE_VERIFICATION,
    WORK_PHOTO,
)


@dataclass(frozen=True)
class Credential:
    type: str
    label: str
    required: bool = False
    # What the admin should do with it, shown beside the document in the review.
    admin_check: Optional[str] = None


def _required(type_: str, label: str, admin_check: Optional[str] = None) -> Credential:
    return Credential(type_, label, True, admin_check)


_POLICE = Credential(POLICE_VERIFICATION, "Police verification certificate")
_ITI = "ITI, training or company certificate"

CREDENTIALS: Dict[str, Tuple[Credential, ...]] = {
    "clinic": (
        _required(
            REGISTRATION,
            "Medical Council registration certificate",
            "Check the name and number on the NMC register or the State Medical Council's site",
        ),
        Credential(QUALIFICATION, "Medical degree (MBBS, MD, BAMS, BHMS or other)"),
    ),
    "dentist": (
        _required(
            REGISTRATION,
            "State Dental Council registration certificate",
            "Check the name and number with the State Dental Council",
        ),
        Credential(QUALIFICATION, "Dental degree (BDS or MDS)"),
    ),
    "home_nursing": (
        _required(
            REGISTRATION,
            "State Nursing Council registration certificate",
            "Check the name and number with the State Nursing Council or the INC's NRTS",
        ),
        Credential(QUALIFICATION, "Nursing degree or diploma (GNM, ANM or B.Sc)"),
        _POLICE,
    ),
    "physiotherapy": (
        _required(QUALIFICATION, "Physiotherapy degree or diploma"),
        Credential(REGISTRATION, "Council registration certificate, if your state has one"),
    ),
    "lab_tests": (
        _required(LICENCE, "Laboratory registration or licence"),
        Credential(QUALIFICATION, "Technician qualification or NABL certificate"),
    ),
    "pest_control": (
        _required(
            LICENCE,
            "Pest control licence (State Agriculture Department)",
            "The licence is under the Insecticides Act, 1968",
        ),
    ),
    "catering": (
        _required(FOOD_LICENCE, "FSSAI registration or licence", "Check the 14-digit number on foscos.fssai.gov.in"),
    ),
    "driver": (
        _required(DRIVING_LICENCE, "Driving licence", "Check the class of vehicle and the expiry date"),
        _POLICE,
    ),
    "pet_care": (Credential(REGISTRATION, "Veterinary Council registration, for vets"),),
    "electrical": (Credential(LICENCE, "Wireman licence, or " + _ITI),),
    "plumbing": (Credential(QUALIFICATION, _ITI),),
    "appliance_repair": (Credential(QUALIFICATION, _ITI),),
    "water_purifier": (Credential(QUALIFICATION, _ITI),),
    "solar": (Credential(QUALIFICATION, _ITI),),
    "vehicle_repair": (Credential(QUALIFICATION, _ITI),),
    "electronics_repair": (Credential(QUALIFICATION, _ITI),),
    "welding": (Credential(QUALIFICATION, _ITI),),
    "construction": (Credential(LICENCE, "Contractor licence or registration, if you have one"),),
    "interior": (Credential(QUALIFICATION, "Design qualification, if you have one"),),
    "cook": (Credential(FOOD_LICENCE, "FSSAI registration, if you sell food"), _POLICE),
    "tax_legal": (Credential(REGISTRATION, "ICAI or Bar Council certificate, if you are a CA or advocate"),),
    "tutor": (Credential(QUALIFICATION, "Degree or teaching certificate"), _POLICE),
    "fitness": (Credential(QUALIFICATION, "Trainer or yoga certificate"),),
    "cleaning": (_POLICE,),
    "domestic_help": (_POLICE,),
    "care_giver": (_POLICE,),
    "security_guard": (Credential(LICENCE, "Agency licence (PSARA), if you run an agency"), _POLICE),
    "packers_movers": (Credential(LICENCE, "Transport or company registration"),),
}


def credentials_for(category: Optional[str]) -> List[Credential]:
    """This type of work's documents, then a photo of the work, which helps everyone get approved."""
    return [*CREDENTIALS.get(category or "", ()), Credential(WORK_PHOTO, "Photos of your work")]


def required_for(category: Optional[str]) -> List[Credential]:
    return [c for c in credentials_for(category) if c.required]
