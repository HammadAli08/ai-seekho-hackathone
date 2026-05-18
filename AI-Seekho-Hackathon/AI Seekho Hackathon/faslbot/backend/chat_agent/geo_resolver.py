"""
Pakistan geographic hierarchy resolver.
Handles province → district → tehsil resolution with confidence scoring.
"""

from __future__ import annotations

from typing import Any

# Pakistan provinces (canonical)
PROVINCES = [
    "Punjab",
    "Sindh",
    "Khyber Pakhtunkhwa",
    "Balochistan",
    "Islamabad Capital Territory",
    "Gilgit-Baltistan",
    "Azad Jammu and Kashmir",
]

# District → province mapping (comprehensive)
DISTRICT_TO_PROVINCE: dict[str, str] = {
    # Punjab (36 districts)
    "attock": "Punjab",
    "bahawalnagar": "Punjab",
    "bahawalpur": "Punjab",
    "bhakkar": "Punjab",
    "chakwal": "Punjab",
    "chiniot": "Punjab",
    "dera ghazi khan": "Punjab",
    "faisalabad": "Punjab",
    "gujranwala": "Punjab",
    "gujrat": "Punjab",
    "hafizabad": "Punjab",
    "jhang": "Punjab",
    "jhelum": "Punjab",
    "kasur": "Punjab",
    "khanewal": "Punjab",
    "khoshab": "Punjab",
    "lahore": "Punjab",
    "layyah": "Punjab",
    "lodhran": "Punjab",
    "mandi bahauddin": "Punjab",
    "mianwali": "Punjab",
    "multan": "Punjab",
    "muzzafargarh": "Punjab",
    "nankana sahib": "Punjab",
    "narowal": "Punjab",
    "okara": "Punjab",
    "pakpattan": "Punjab",
    "rahim yar khan": "Punjab",
    "rajanpur": "Punjab",
    "rawalpindi": "Punjab",
    "sahiwal": "Punjab",
    "sargodha": "Punjab",
    "sheikhupura": "Punjab",
    "sialkot": "Punjab",
    "toba tek singh": "Punjab",
    "vehari": "Punjab",
    # Sindh (23 districts)
    "badin": "Sindh",
    "dadu": "Sindh",
    "ghotki": "Sindh",
    "hyderabad": "Sindh",
    "jamshoro": "Sindh",
    "karachi": "Sindh",
    "karachi central": "Sindh",
    "karachi east": "Sindh",
    "karachi south": "Sindh",
    "karachi west": "Sindh",
    "kashmore": "Sindh",
    "khairpur": "Sindh",
    "larkana": "Sindh",
    "matiari": "Sindh",
    "mirpurkhas": "Sindh",
    "naushahro feroze": "Sindh",
    "nawabshah": "Sindh",
    "qambar shahdadkot": "Sindh",
    "sanghar": "Sindh",
    "shaheed benazirabad": "Sindh",
    "shikarpur": "Sindh",
    "sujawal": "Sindh",
    "sukkur": "Sindh",
    "tando allahyar": "Sindh",
    # KP (28 districts)
    "abbottabad": "Khyber Pakhtunkhwa",
    "bannu": "Khyber Pakhtunkhwa",
    "batagram": "Khyber Pakhtunkhwa",
    "buner": "Khyber Pakhtunkhwa",
    "charsadda": "Khyber Pakhtunkhwa",
    "chitral": "Khyber Pakhtunkhwa",
    "coswat": "Khyber Pakhtunkhwa",
    "dir lower": "Khyber Pakhtunkhwa",
    "dir upper": "Khyber Pakhtunkhwa",
    "hangu": "Khyber Pakhtunkhwa",
    "haripur": "Khyber Pakhtunkhwa",
    "hatian": "Khyber Pakhtunkhwa",
    "karak": "Khyber Pakhtunkhwa",
    "kohistan": "Khyber Pakhtunkhwa",
    "kohat": "Khyber Pakhtunkhwa",
    "lakki marwat": "Khyber Pakhtunkhwa",
    "malakand": "Khyber Pakhtunkhwa",
    "mansehra": "Khyber Pakhtunkhwa",
    "mardan": "Khyber Pakhtunkhwa",
    "nowshera": "Khyber Pakhtunkhwa",
    "peshawar": "Khyber Pakhtunkhwa",
    "shangla": "Khyber Pakhtunkhwa",
    "swabi": "Khyber Pakhtunkhwa",
    "swat": "Khyber Pakhtunkhwa",
    "tank": "Khyber Pakhtunkhwa",
    "torghar": "Khyber Pakhtunkhwa",
    "dera ismail khan": "Khyber Pakhtunkhwa",
    # Balochistan (32 districts)
    "awaran": "Balochistan",
    "barkhan": "Balochistan",
    "bolan": "Balochistan",
    "chagai": "Balochistan",
    "dalbadin": "Balochistan",
    "gwadar": "Balochistan",
    "harnai": "Balochistan",
    "hoshab": "Balochistan",
    "jaffarabad": "Balochistan",
    "jhol": "Balochistan",
    "kalat": "Balochistan",
    "kech": "Balochistan",
    "kharan": "Balochistan",
    "khuzdar": "Balochistan",
    "kindial": "Balochistan",
    "kundar": "Balochistan",
    "lasbela": "Balochistan",
    "loralai": "Balochistan",
    "mastung": "Balochistan",
    "musal": "Balochistan",
    "musakhel": "Balochistan",
    "naal": "Balochistan",
    "nasirabad": "Balochistan",
    "nushki": "Balochistan",
    "panjgur": "Balochistan",
    "pishin": "Balochistan",
    "quetta": "Balochistan",
    "surab": "Balochistan",
    "turbat": "Balochistan",
    "washuk": "Balochistan",
    "zhob": "Balochistan",
    # Islamabad Capital Territory
    "islamabad": "Islamabad Capital Territory",
    # Gilgit-Baltistan
    "astore": "Gilgit-Baltistan",
    "bagesar": "Gilgit-Baltistan",
    "diamer": "Gilgit-Baltistan",
    "ghanche": "Gilgit-Baltistan",
    "gilgit": "Gilgit-Baltistan",
    "kharmang": "Gilgit-Baltistan",
    "nagar": "Gilgit-Baltistan",
    "skardu": "Gilgit-Baltistan",
    "shigar": "Gilgit-Baltistan",
    # Azad Jammu and Kashmir
    "bhimber": "Azad Jammu and Kashmir",
    "kotli": "Azad Jammu and Kashmir",
    "mirpur": "Azad Jammu and Kashmir",
    "muzaffarabad": "Azad Jammu and Kashmir",
    "neelum": "Azad Jammu and Kashmir",
    "poonch": "Azad Jammu and Kashmir",
    "rawalakot": "Azad Jammu and Kashmir",
    "sudhnoti": "Azad Jammu and Kashmir",
}

# Tehsil → district mapping (selected key tehsils)
TEHSIL_TO_DISTRICT: dict[str, str] = {
    # Lahore
    "lahore cantonment": "Lahore",
    "lacaton": "Lahore",
    "lahore city": "Lahore",
    # Rawalpindi
    "chakri": "Rawalpindi",
    "kahuta": "Rawalpindi",
    "kotli sattian": "Rawalpindi",
    "murree": "Rawalpindi",
    "rawalakot": "Rawalpindi",
    "rawalpindi city": "Rawalpindi",
    # Karachi
    "karachi city": "Karachi",
    "clifton": "Karachi",
    "korangi": "Karachi",
    "malir": "Karachi",
    # Peshawar
    "peshawar city": "Peshawar",
    "peshawar cantonment": "Peshawar",
    # Skardu
    "skardu city": "Skardu",
    "kharmang": "Skardu",
    # Quetta
    "quetta city": "Quetta",
    # Multan
    "multan city": "Multan",
    "shujabad": "Multan",
    # Faisalabad
    "faisalabad city": "Faisalabad",
    "tandlianwala": "Faisalabad",
    # Gujranwala
    "gujranwala city": "Gujranwala",
    "sidhpur": "Gujranwala",
    # Hyderabad
    "hyderabad city": "Hyderabad",
    # Sukkur
    "sukkur city": "Sukkur",
    # Swat
    "mingora": "Swat",
    "saidu swat": "Swat",
}

# City/major town → district mapping (broader lookup)
CITY_TO_DISTRICT: dict[str, str] = {
    "lahore": "Lahore",
    "karachi": "Karachi",
    "islamabad": "Islamabad",
    "rawalpindi": "Rawalpindi",
    "peshawar": "Peshawar",
    "multan": "Multan",
    "faisalabad": "Faisalabad",
    "gujranwala": "Gujranwala",
    "hyderabad": "Hyderabad",
    "sukkur": "Sukkur",
    "quetta": "Quetta",
    "skardu": "Skardu",
    "swat": "Swat",
    "abbottabad": "Abbottabad",
    "mardan": "Mardan",
    "dera ghazi khan": "Dera Ghazi Khan",
    "bahawalpur": "Bahawalpur",
    "muzaffarabad": "Muzaffarabad",
    "mirpur": "Mirpur",
    "gwadar": "Gwadar",
    "chitral": "Chitral",
    "kohat": "Kohat",
    "khuzdar": "Khuzdar",
    "zhob": "Zhob",
}


def normalize_geo_input(location: str | None) -> str:
    """Normalize location string for matching."""
    if not location:
        return ""
    return " ".join(str(location).split()).casefold()


def resolve_region(location: str | None) -> dict[str, Any]:
    """
    Resolve a location string to struct with province/district/tehsil.
    Returns:
    {
        "input": original location,
        "province": matched province or None,
        "district": matched district or None,
        "tehsil": matched tehsil or None,
        "confidence": 0..1,
        "resolved": True/False
    }
    """
    if not location:
        return {
            "input": None,
            "province": None,
            "district": None,
            "tehsil": None,
            "confidence": 0.0,
            "resolved": False,
        }

    normalized = normalize_geo_input(location)

    # Check if it's a province
    for prov in PROVINCES:
        if prov.casefold() == normalized:
            return {
                "input": location,
                "province": prov,
                "district": None,
                "tehsil": None,
                "confidence": 1.0,
                "resolved": True,
            }

    # Check if it's a district (direct match)
    if normalized in DISTRICT_TO_PROVINCE:
        prov = DISTRICT_TO_PROVINCE[normalized]
        return {
            "input": location,
            "province": prov,
            "district": location.title(),
            "tehsil": None,
            "confidence": 0.95,
            "resolved": True,
        }

    # Check if it's a tehsil
    if normalized in TEHSIL_TO_DISTRICT:
        dist_name = TEHSIL_TO_DISTRICT[normalized]
        prov = DISTRICT_TO_PROVINCE.get(dist_name.casefold())
        return {
            "input": location,
            "province": prov,
            "district": dist_name,
            "tehsil": location.title(),
            "confidence": 0.9,
            "resolved": True,
        }

    # Check if it's a city
    if normalized in CITY_TO_DISTRICT:
        dist_name = CITY_TO_DISTRICT[normalized]
        prov = DISTRICT_TO_PROVINCE.get(dist_name.casefold())
        return {
            "input": location,
            "province": prov,
            "district": dist_name,
            "tehsil": None,
            "confidence": 0.88,
            "resolved": True,
        }

    # Substring match for partial names
    for dist, prov in DISTRICT_TO_PROVINCE.items():
        if normalized in dist or dist in normalized:
            return {
                "input": location,
                "province": prov,
                "district": dist.title(),
                "tehsil": None,
                "confidence": 0.75,
                "resolved": True,
            }

    # Default to National if unresolved
    return {
        "input": location,
        "province": None,
        "district": None,
        "tehsil": None,
        "confidence": 0.0,
        "resolved": False,
    }


def get_province_neighbors(province: str | None) -> list[str]:
    """Return neighboring provinces for fallback context."""
    neighbors: dict[str, list[str]] = {
        "Punjab": ["Sindh", "Khyber Pakhtunkhwa", "Balochistan"],
        "Sindh": ["Punjab", "Balochistan"],
        "Khyber Pakhtunkhwa": ["Punjab", "Balochistan", "Gilgit-Baltistan"],
        "Balochistan": ["Punjab", "Sindh", "Khyber Pakhtunkhwa"],
        "Islamabad Capital Territory": ["Punjab", "Khyber Pakhtunkhwa"],
        "Gilgit-Baltistan": ["Khyber Pakhtunkhwa", "Azad Jammu and Kashmir"],
        "Azad Jammu and Kashmir": ["Khyber Pakhtunkhwa", "Gilgit-Baltistan"],
    }
    return neighbors.get(province or "", [])


def get_districts_in_province(province: str | None) -> list[str]:
    """Get all districts belonging to a province."""
    if not province:
        return []
    target = province.casefold()
    districts = set()
    for dist, prov in DISTRICT_TO_PROVINCE.items():
        if prov.casefold() == target:
            districts.add(dist.title())
    return sorted(list(districts))


def _extract_region_from_text(text: str | None) -> str | None:
    """Extract first recognizable Pakistan region from free text."""
    if not text:
        return None
    text_lower = text.casefold()
    
    # Check provinces first (higher priority)
    for prov in PROVINCES:
        if prov.casefold() in text_lower:
            return prov
    
    # Check districts
    for dist in DISTRICT_TO_PROVINCE:
        if dist in text_lower:
            return dist.title()
    
    # Check cities (from CITY_TO_REGION mapping if available)
    # This is a fallback in case city names are mentioned
    return None
