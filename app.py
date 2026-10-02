import json
import math
from pathlib import Path

from flask import Flask, render_template, request

app = Flask(__name__)
SITE_NAME = "RainHarvest Pro"
SITE_SLUG = "rainharvest-pro"

# Approximate annual rainfall values in mm
STATES = {
    "Andhra Pradesh": 940,
    "Arunachal Pradesh": 2782,
    "Assam": 2818,
    "Bihar": 1205,
    "Chhattisgarh": 1292,
    "Goa": 2932,
    "Gujarat": 803,
    "Haryana": 617,
    "Himachal Pradesh": 1265,
    "Jharkhand": 1400,
    "Karnataka": 1150,
    "Kerala": 3055,
    "Madhya Pradesh": 1100,
    "Maharashtra": 1100,
    "Manipur": 1900,
    "Meghalaya": 2500,
    "Mizoram": 2500,
    "Nagaland": 1800,
    "Odisha": 1451,
    "Punjab": 649,
    "Rajasthan": 575,
    "Sikkim": 2739,
    "Tamil Nadu": 998,
    "Telangana": 900,
    "Tripura": 2200,
    "Uttar Pradesh": 990,
    "Uttarakhand": 1550,
    "West Bengal": 1750
}

# Complete district names for all 28 supported states. District-specific
# rainfall overrides are approximate; all other districts use their state value.
with open(Path(__file__).with_name("districts.json"), encoding="utf-8-sig") as district_file:
    DISTRICT_NAMES = json.load(district_file)

RAINFALL_OVERRIDES = {
    "Punjab": {"Amritsar": 680, "Ludhiana": 730, "Patiala": 710, "Pathankot": 1100},
    "Maharashtra": {
        "Mumbai City": 2400,
        "Mumbai Suburban": 2400,
        "Pune": 720,
        "Nagpur": 1100,
        "Nashik": 700,
    },
    "Kerala": {
        "Thiruvananthapuram": 1800,
        "Ernakulam": 3000,
        "Kozhikode": 3200,
        "Idukki": 4000,
    },
    "Rajasthan": {"Jaipur": 550, "Jodhpur": 360, "Udaipur": 650, "Kota": 700},
    "Tamil Nadu": {"Chennai": 1400, "Coimbatore": 650, "Madurai": 850, "Kanyakumari": 1300},
    "West Bengal": {"Kolkata": 1800, "Darjeeling": 3100},
}

DISTRICTS = {
    state: {
        district.strip(): RAINFALL_OVERRIDES.get(state, {}).get(district.strip(), STATES[state])
        for district in district_names
    }
    for state, district_names in DISTRICT_NAMES.items()
    if state in STATES
}

# Roof type runoff coefficients
ROOF_COEFFICIENTS = {
    "RCC / Concrete": 0.80,
    "Metal Sheet": 0.90,
    "Tiles": 0.75,
    "Other": 0.70
}
COLLECTION_EFFICIENCY = 0.85
MAX_ROOF_AREA_M2 = 100000


def to_float(value, default=0.0):
    try:
        converted = float(value)
        if not math.isfinite(converted):
            return default
        return converted
    except (TypeError, ValueError):
        return default


def clamp(value, min_value, max_value):
    return max(min_value, min(value, max_value))


def get_rainfall_category(rainfall):
    if rainfall <= 0:
        return "No rainfall data"
    if rainfall < 600:
        return "Low"
    elif rainfall < 1000:
        return "Moderate"
    elif rainfall < 2000:
        return "High"
    else:
        return "Very High"


def get_recommendation(rainfall, water):
    category = get_rainfall_category(rainfall)

    if rainfall <= 0:
        method = "Feasibility check with a rain gauge and roof screening"
        storage = "Small tank or recharge pit"
        scale = "Site-specific feasibility check required"
        return category, method, storage, scale

    if rainfall < 600:
        method = "Rooftop Collection + Recharge Pit"
        storage = "Small / Medium Storage Tank"

    elif rainfall < 1000:
        method = "Rooftop Rainwater Harvesting"
        storage = "Medium Storage Tank + Recharge Pit"

    elif rainfall < 2000:
        method = "Rooftop Harvesting + Storage + Recharge"
        storage = "Large Storage Tank + Recharge Pit"

    else:
        method = "Large Storage + Recharge Well + Overflow System"
        storage = "Large Storage Tank / Recharge Well"

    if water >= 100000:
        scale = "Large-scale harvesting system"
    elif water >= 50000:
        scale = "Medium-scale harvesting system"
    else:
        scale = "Small / Medium-scale harvesting system"

    return category, method, storage, scale


def calculate_water(rainfall, roof_area, roof_type):
    rainfall = max(0.0, to_float(rainfall, 0.0))
    roof_area = clamp(to_float(roof_area, 0.0), 0.0, MAX_ROOF_AREA_M2)
    if roof_type not in ROOF_COEFFICIENTS:
        raise ValueError("Unsupported roof type.")
    coefficient = ROOF_COEFFICIENTS[roof_type]
    water_litres = roof_area * rainfall * coefficient * COLLECTION_EFFICIENCY
    category, method, storage, scale = get_recommendation(rainfall, water_litres)

    return {
        "water": round(water_litres, 2),
        "water_m3": round(water_litres / 1000, 3),
        "rainfall": rainfall,
        "area": roof_area,
        "roof_type": roof_type,
        "coefficient": coefficient,
        "efficiency": COLLECTION_EFFICIENCY,
        "category": category,
        "method": method,
        "storage": storage,
        "scale": scale,
    }


def get_locality_values(state, district):
    state_districts = DISTRICTS.get(state, {})
    if district in state_districts:
        return district, state_districts[district]
    return "", 0


def process_calculator_form(form):
    selected_state = (form.get("state", "") or "").strip()
    selected_district, rainfall = get_locality_values(
        selected_state,
        (form.get("district", "") or "").strip(),
    )
    area_text = (form.get("roof_area", "") or "").strip()
    roof_area_display = to_float(area_text, None)
    area_unit = form.get("area_unit", "m2")
    water_unit = form.get("water_unit", "litres")
    roof_type = form.get("roof_type", "RCC / Concrete")
    error_message = None

    if selected_state not in STATES:
        error_message = "Please choose a valid state."
    elif not selected_district:
        error_message = "Please choose a district from the selected state's list."
    elif not area_text:
        error_message = "Enter your roof area to calculate a valid estimate."
    elif roof_area_display is None:
        error_message = "Enter a valid numeric roof area."
    elif area_unit not in {"m2", "ft2"}:
        error_message = "Choose a supported roof-area unit."
        area_unit = "m2"
    elif water_unit not in {"litres", "m3"}:
        error_message = "Choose a supported output unit."
        water_unit = "litres"
    elif roof_type not in ROOF_COEFFICIENTS:
        error_message = "Choose a supported roof type."
        roof_type = "RCC / Concrete"

    result = None
    roof_area = roof_area_display if roof_area_display is not None else 0
    if not error_message:
        if area_unit == "ft2":
            roof_area *= 0.092903

        if roof_area <= 0:
            error_message = "Roof area must be greater than zero."
        elif roof_area > MAX_ROOF_AREA_M2:
            error_message = "Roof area exceeds the supported maximum of 100,000 m²."
        elif rainfall <= 0:
            error_message = "No rainfall data is available for this district. Please choose another location."
        else:
            result = calculate_water(rainfall, roof_area, roof_type)

    return {
        "result": result,
        "selected_state": selected_state,
        "selected_district": selected_district,
        "rainfall": rainfall,
        "roof_area": roof_area_display if roof_area_display is not None else area_text,
        "area_unit": area_unit,
        "water_unit": water_unit,
        "roof_type": roof_type,
        "error_message": error_message,
    }


@app.route("/", methods=["GET", "POST"])
@app.route("/rainharvest-pro", methods=["GET", "POST"])
@app.route("/rainwater-harvesting", methods=["GET", "POST"])
def home():
    values = {
        "result": None,
        "selected_state": "",
        "selected_district": "",
        "rainfall": 0,
        "roof_area": 100,
        "area_unit": "m2",
        "water_unit": "litres",
        "roof_type": "RCC / Concrete",
        "error_message": None,
    }
    if request.method == "POST":
        values = process_calculator_form(request.form)

    return render_template(
        "index.html",
        site_name=SITE_NAME,
        site_slug=SITE_SLUG,
        states=STATES,
        **values,
        districts=DISTRICTS,
    )


@app.route("/calculator", methods=["GET", "POST"])
def calculator():
    values = {
        "result": None,
        "selected_state": "",
        "selected_district": "",
        "rainfall": 0,
        "roof_area": 100,
        "area_unit": "m2",
        "water_unit": "litres",
        "roof_type": "RCC / Concrete",
        "error_message": None,
    }
    if request.method == "POST":
        values = process_calculator_form(request.form)

    return render_template(
        "calculator.html",
        site_name=SITE_NAME,
        site_slug=SITE_SLUG,
        states=STATES,
        **values,
        districts=DISTRICTS,
    )


@app.route("/about")
@app.route("/benefits")
def about():
    return render_template(
        "about.html",
        site_name=SITE_NAME,
        site_slug=SITE_SLUG,
        states=STATES,
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
