from django import forms
from django.conf import settings
from django.forms import BaseInlineFormSet, inlineformset_factory

from incidents.classifications import INVOLVE_GROUPS
from incidents.models import Incident, Severity, Witness
from incidents.scene_locations import (
    SCENE_LOCATION_CHOICES,
    SCENE_LOCATION_OTHER,
    SCENE_LOCATION_PRESET_VALUES,
)
from incidents.services.keycloak import KeycloakError, resolve_user
from incidents.services.workflow import is_late_at_submission


class IncidentForm(forms.ModelForm):
    confirm = forms.BooleanField(
        required=False,
        label="I confirm this report is accurate to the best of my knowledge",
        widget=forms.CheckboxInput(attrs={"class": "checkbox-field"}),
    )
    verifier_keycloak_id = forms.CharField(required=False, widget=forms.HiddenInput())
    verifier_name = forms.CharField(
        required=False,
        label="Person to verify (supervisor)",
        widget=forms.TextInput(
            attrs={
                "class": "input-field employee-search",
                "placeholder": "Search person to verify (supervisor)",
                "autocomplete": "off",
                "data-employee-target": "verifier",
            }
        ),
    )
    location_choice = forms.ChoiceField(
        required=False,
        label="Scene location",
        choices=SCENE_LOCATION_CHOICES,
        widget=forms.Select(attrs={"class": "input-field", "id": "location-choice"}),
    )
    scene_location_other = forms.CharField(
        required=False,
        label="Specify other location",
        max_length=70,
        widget=forms.TextInput(
            attrs={
                "class": "input-field",
                "id": "location-other",
                "maxlength": "70",
                "placeholder": "Type the location",
            }
        ),
    )

    class Meta:
        model = Incident
        fields = [
            "incident_date",
            "incident_time",
            "scene_location",
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
            "other_person_text",
            "other_premises",
            "other_premises_text",
            "other_product",
            "other_product_text",
            "other_property",
            "other_property_text",
            "description",
            "possible_causes",
            "corrective_actions_taken",
            "immediate_actions",
            "effect_on_process",
            "recommendations",
            "late_reason",
        ]
        widgets = {
            "incident_date": forms.DateInput(attrs={"type": "date", "class": "input-field"}),
            "incident_time": forms.TimeInput(attrs={"type": "time", "class": "input-field"}),
            "scene_location": forms.HiddenInput(),
            "description": forms.Textarea(attrs={"rows": 4, "class": "input-field"}),
            "possible_causes": forms.Textarea(attrs={"rows": 3, "class": "input-field"}),
            "corrective_actions_taken": forms.Textarea(attrs={"rows": 3, "class": "input-field"}),
            "immediate_actions": forms.Textarea(attrs={"rows": 3, "class": "input-field"}),
            "effect_on_process": forms.Textarea(attrs={"rows": 3, "class": "input-field"}),
            "recommendations": forms.Textarea(attrs={"rows": 3, "class": "input-field"}),
            "late_reason": forms.Textarea(attrs={"rows": 3, "class": "input-field"}),
            "other_person_text": forms.TextInput(
                attrs={"class": "input-field other-text", "placeholder": "Specify other (persons)"}
            ),
            "other_premises_text": forms.TextInput(
                attrs={"class": "input-field other-text", "placeholder": "Specify other (premises)"}
            ),
            "other_product_text": forms.TextInput(
                attrs={"class": "input-field other-text", "placeholder": "Specify other (products)"}
            ),
            "other_property_text": forms.TextInput(
                attrs={"class": "input-field other-text", "placeholder": "Specify other (property)"}
            ),
        }

    def __init__(self, *args, **kwargs):
        self.submitting = kwargs.pop("submitting", False)
        self.reporter = kwargs.pop("reporter", None)
        super().__init__(*args, **kwargs)
        checkbox_fields = [
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
        ]
        for name in checkbox_fields:
            self.fields[name].widget.attrs.update({"class": "checkbox-field"})

        required_text = [
            "incident_date",
            "incident_time",
            "description",
            "possible_causes",
            "immediate_actions",
            "effect_on_process",
            "recommendations",
        ]
        for field in required_text:
            self.fields[field].required = self.submitting

        if self.submitting:
            self.fields["location_choice"].required = True

        if self.instance and self.instance.pk and self.instance.scene_location:
            stored = self.instance.scene_location.strip()
            if stored in SCENE_LOCATION_PRESET_VALUES:
                self.fields["location_choice"].initial = stored
            else:
                self.fields["location_choice"].initial = SCENE_LOCATION_OTHER
                self.fields["scene_location_other"].initial = stored

        self.fields["corrective_actions_taken"].required = False
        self.fields["corrective_actions_taken"].label = "Corrective actions taken (optional)"
        self.fields["effect_on_process"].label = "Effect of the incident"

        self.fields["confirm"].required = False
        if self.instance and self.instance.pk and self.instance.verifier:
            self.fields["verifier_name"].initial = self.instance.verifier.full_name
            self.fields["verifier_keycloak_id"].initial = (
                self.instance.verifier.keycloak_id or str(self.instance.verifier.pk)
            )

    def clean_scene_location(self):
        value = (self.cleaned_data.get("scene_location") or "").strip()
        if value and len(value) > 70:
            raise forms.ValidationError("Location must be 70 characters or fewer.")
        return value

    def _resolve_scene_location(self, cleaned):
        choice = cleaned.get("location_choice")
        other = (cleaned.get("scene_location_other") or "").strip()
        if choice == SCENE_LOCATION_OTHER:
            if self.submitting and not other:
                self.add_error("scene_location_other", "Specify the location.")
                return None
            return other
        if choice:
            return choice
        return (cleaned.get("scene_location") or "").strip()

    def clean(self):
        cleaned = super().clean()
        resolved = self._resolve_scene_location(cleaned)
        if resolved is not None:
            cleaned["scene_location"] = resolved
        if self.submitting and not (cleaned.get("scene_location") or "").strip():
            if not self.errors.get("location_choice") and not self.errors.get("scene_location_other"):
                self.add_error("location_choice", "Select a scene location.")
            return cleaned

        if not self.submitting:
            return cleaned

        involves_selected = [
            key for key, group in INVOLVE_GROUPS.items() if cleaned.get(group["field"])
        ]
        if not involves_selected:
            raise forms.ValidationError("Select at least one option under Involves.")

        has_classification = False
        for key in involves_selected:
            group = INVOLVE_GROUPS[key]
            group_has = any(cleaned.get(field_name) for field_name, _ in group["classifications"])
            other_bool = cleaned.get(group["other_bool"])
            other_text = (cleaned.get(group["other_text"]) or "").strip()
            if other_bool and not other_text:
                self.add_error(
                    group["other_text"],
                    f"Please specify the other classification for {group['label']}.",
                )
            if group_has or other_bool:
                has_classification = True
            elif cleaned.get(group["field"]):
                raise forms.ValidationError(
                    f"Select at least one classification for {group['label']}."
                )

        if not has_classification:
            raise forms.ValidationError(
                "Select at least one classification for each Involves category you selected."
            )

        if not cleaned.get("confirm"):
            raise forms.ValidationError(
                "You must check the declaration box to confirm your report before submitting."
            )

        if is_late_at_submission(cleaned.get("incident_date"), cleaned.get("incident_time")):
            if not (cleaned.get("late_reason") or "").strip():
                self.add_error(
                    "late_reason",
                    f"Reason for delay is required when submitting more than "
                    f"{settings.INCIDENT_LATE_MINUTES} minutes after the incident time.",
                )

        verifier_id = (cleaned.get("verifier_keycloak_id") or "").strip()
        if not verifier_id:
            self.add_error("verifier_name", "Select a verifier from the search results.")
        else:
            try:
                verifier = resolve_user(verifier_id)
            except KeycloakError as exc:
                self.add_error("verifier_name", str(exc))
            else:
                if self.reporter and verifier.id == self.reporter.id:
                    self.add_error("verifier_name", "Verifier must be a different person from the reporter.")
                cleaned["selected_verifier"] = verifier

        return cleaned


class VerifierActionForm(forms.Form):
    severity = forms.ChoiceField(
        choices=[("", "Select severity")] + list(Severity.choices),
        label="Severity",
        required=True,
        widget=forms.Select(attrs={"class": "input-field", "id": "verify-severity"}),
    )
    approver_keycloak_id = forms.CharField(required=False, widget=forms.HiddenInput())
    approver_name = forms.CharField(
        required=False,
        label="Person to approve (supervisor)",
        widget=forms.TextInput(
            attrs={
                "class": "input-field employee-search",
                "placeholder": "Search person to approve (supervisor)",
                "autocomplete": "off",
                "data-employee-target": "approver",
            }
        ),
    )

    def __init__(self, *args, incident=None, **kwargs):
        self.incident = incident
        super().__init__(*args, **kwargs)
        if incident and incident.approver:
            self.fields["approver_name"].initial = incident.approver.full_name
            self.fields["approver_keycloak_id"].initial = (
                incident.approver.keycloak_id or str(incident.approver.pk)
            )
        if incident and incident.severity:
            self.fields["severity"].initial = incident.severity

    def clean(self):
        cleaned = super().clean()
        approver_id = (cleaned.get("approver_keycloak_id") or "").strip()
        if not approver_id:
            self.add_error("approver_name", "Select an approver from the search results.")
            return cleaned
        try:
            approver = resolve_user(approver_id)
        except KeycloakError as exc:
            self.add_error("approver_name", str(exc))
            return cleaned

        if self.incident:
            ids = {self.incident.reporter_id, self.incident.verifier_id, approver.id}
            if len(ids) != 3:
                self.add_error("approver_name", "Approver must be different from the reporter and verifier.")
        cleaned["selected_approver"] = approver
        return cleaned


class WitnessForm(forms.ModelForm):
    keycloak_id = forms.CharField(required=False, widget=forms.HiddenInput())

    class Meta:
        model = Witness
        fields = ["name", "designation"]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "input-field employee-search witness-name",
                    "placeholder": "Search witness name",
                    "autocomplete": "off",
                    "data-employee-target": "witness",
                }
            ),
            "designation": forms.HiddenInput(),
        }

    def __init__(self, *args, submitting=False, **kwargs):
        self.submitting = submitting
        super().__init__(*args, **kwargs)
        self.fields["designation"].required = False

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("DELETE"):
            return cleaned

        keycloak_id = (cleaned.get("keycloak_id") or "").strip()
        name = (cleaned.get("name") or "").strip()

        if not name and not keycloak_id:
            return cleaned

        if keycloak_id:
            try:
                user = resolve_user(keycloak_id)
            except KeycloakError as exc:
                self.add_error("name", str(exc))
            else:
                cleaned["name"] = user.full_name
            return cleaned

        if self.submitting:
            stored_name = (self.instance.name or "").strip() if self.instance.pk else ""
            if self.instance.pk and name == stored_name:
                cleaned["name"] = stored_name
            else:
                self.add_error("name", "Select a witness from the search results.")
            return cleaned

        cleaned["name"] = name
        return cleaned


class BaseWitnessFormSet(BaseInlineFormSet):
    def __init__(self, *args, submitting=False, **kwargs):
        self.submitting = submitting
        super().__init__(*args, **kwargs)

    def _construct_form(self, i, **kwargs):
        kwargs["submitting"] = self.submitting
        return super()._construct_form(i, **kwargs)

    def clean(self):
        super().clean()
        if any(self.errors):
            return
        active = 0
        for form in self.forms:
            if not form.cleaned_data or form.cleaned_data.get("DELETE"):
                continue
            name = (form.cleaned_data.get("name") or "").strip()
            if name:
                active += 1
        if active < 1:
            raise forms.ValidationError(
                "At least one witness is required. Click Add witness and select a person."
            )


WitnessFormSet = inlineformset_factory(
    Incident,
    Witness,
    form=WitnessForm,
    formset=BaseWitnessFormSet,
    extra=0,
    can_delete=True,
    min_num=0,
    validate_min=False,
)


def witness_formset(instance=None, data=None, submitting=False):
    extra = 0 if instance and instance.pk else 1
    Factory = inlineformset_factory(
        Incident,
        Witness,
        form=WitnessForm,
        formset=BaseWitnessFormSet,
        extra=extra,
        can_delete=True,
        min_num=0,
        validate_min=False,
    )
    if data is not None:
        if instance:
            return Factory(data, instance=instance, submitting=submitting)
        return Factory(data, submitting=submitting)
    if instance:
        return Factory(instance=instance, submitting=submitting)
    return Factory(submitting=submitting)


class CommentForm(forms.Form):
    comment = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "rows": 4,
                "class": "input-field",
                "placeholder": "Explain why this report is being returned (required)...",
            }
        ),
        min_length=10,
        label="Return comment",
    )


class ForwardCommentForm(forms.Form):
    comment = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 4, "class": "input-field"}),
        min_length=10,
        label="Comment to reporter",
    )


class PhotoUploadForm(forms.Form):
    def validate_photos(self, existing_count=0):
        return validate_photo_uploads(self.files.getlist("photos"), existing_count=existing_count)


def validate_photo_uploads(files, existing_count=0):
    photos = files
    if existing_count + len(photos) == 0:
        raise forms.ValidationError("At least one photo is required before you can submit the report.")
    if existing_count + len(photos) > settings.INCIDENT_MAX_PHOTOS:
        raise forms.ValidationError(f"Maximum {settings.INCIDENT_MAX_PHOTOS} photos allowed.")
    for photo in photos:
        if photo.size > settings.INCIDENT_MAX_PHOTO_BYTES:
            raise forms.ValidationError(f'"{photo.name}" exceeds the 5 MB size limit.')
        if photo.content_type not in settings.ALLOWED_PHOTO_TYPES:
            raise forms.ValidationError(f'"{photo.name}" must be a JPEG, PNG, or WEBP image.')
    return photos
