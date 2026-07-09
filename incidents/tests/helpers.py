from datetime import date, time, timedelta
from io import BytesIO

from django.utils import timezone

from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from accounts.models import Role, User
from incidents.models import Incident, IncidentPhoto, IncidentStatus, Witness


def make_user(username, role=Role.WORKER, **extra):
    keycloak_id = extra.pop("keycloak_id", f"kc-{username}")
    email = extra.pop("email", f"{username}@test.local")
    return User.objects.create_user(
        username=username,
        email=email,
        password="testpass123",
        first_name=username.title(),
        last_name="User",
        role=role,
        keycloak_id=keycloak_id,
        designation=extra.pop("designation", "Operator"),
        **extra,
    )


def make_test_image(name="photo.jpg"):
    buffer = BytesIO()
    Image.new("RGB", (8, 8), color="red").save(buffer, format="JPEG")
    buffer.seek(0)
    return SimpleUploadedFile(name, buffer.read(), content_type="image/jpeg")


def future_incident_schedule():
    incident_date = timezone.localdate() + timedelta(days=1)
    return incident_date, time(9, 0)


def base_incident_fields():
    incident_date, incident_time = future_incident_schedule()
    return {
        "incident_date": incident_date,
        "incident_time": incident_time,
        "location_choice": "Body Shop",
        "involves_person": True,
        "classification_injury": True,
        "description": "Test incident description.",
        "possible_causes": "Test causes.",
        "immediate_actions": "Test immediate actions.",
        "effect_on_process": "Test effect.",
        "recommendations": "Test recommendations.",
    }


def base_incident_post_data():
    data = base_incident_fields()
    data["incident_date"] = data["incident_date"].isoformat()
    data["incident_time"] = data["incident_time"].strftime("%H:%M")
    for key in (
        "involves_person",
        "involves_product",
        "involves_premises",
        "involves_property",
        "classification_injury",
        "classification_breakdown",
        "classification_damage",
        "classification_accident",
        "classification_fault",
        "classification_fire",
        "classification_assault",
        "classification_power_outage",
        "classification_theft_vandalism",
        "classification_loss",
        "classification_water_shortage",
        "other_person",
        "other_premises",
        "other_product",
        "other_property",
    ):
        if data.get(key):
            data[key] = "on"
    return data


def make_incident(reporter, **overrides):
    incident_date, incident_time = future_incident_schedule()
    data = {
        "incident_date": incident_date,
        "incident_time": incident_time,
        "scene_location": "Body Shop",
        "involves_person": True,
        "classification_injury": True,
        "description": "Stored incident.",
        "possible_causes": "Causes.",
        "immediate_actions": "Actions.",
        "effect_on_process": "Effect.",
        "recommendations": "Recommendations.",
        "status": IncidentStatus.DRAFT,
        "reporter": reporter,
    }
    data.update(overrides)
    return Incident.objects.create(**data)


def add_witness(incident, name="Witness One", keycloak_id="kc-witness"):
    return Witness.objects.create(incident=incident, name=name, designation="Operator")


def add_photo(incident):
    image = make_test_image()
    return IncidentPhoto.objects.create(
        incident=incident,
        image=image,
        original_filename=image.name,
        file_size_bytes=image.size,
        mime_type="image/jpeg",
        sort_order=0,
    )


def witness_formset_management(total_forms=1):
    return {
        "witnesses-TOTAL_FORMS": str(total_forms),
        "witnesses-INITIAL_FORMS": "0",
        "witnesses-MIN_NUM_FORMS": "0",
        "witnesses-MAX_NUM_FORMS": "1000",
    }


def witness_row(index=0, keycloak_id="kc-supervisor", name="Supervisor User"):
    return {
        f"witnesses-{index}-keycloak_id": keycloak_id,
        f"witnesses-{index}-name": name,
        f"witnesses-{index}-designation": "Supervisor",
        f"witnesses-{index}-id": "",
        f"witnesses-{index}-DELETE": "",
    }
