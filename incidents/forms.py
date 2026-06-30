from django import forms
from django.conf import settings
from django.forms import BaseInlineFormSet, inlineformset_factory

from incidents.classifications import INVOLVE_GROUPS
from incidents.models import Incident, Severity, Witness
from incidents.services.workflow import is_late_at_submission


class IncidentForm(forms.ModelForm):
    confirm = forms.BooleanField(
        required=False,
        label="I confirm this report is accurate to the best of my knowledge",
        widget=forms.CheckboxInput(attrs={"class": "checkbox-field"}),
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
            "scene_location": forms.Select(attrs={"class": "input-field"}),
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
            "scene_location",
            "description",
            "possible_causes",
            "corrective_actions_taken",
            "immediate_actions",
            "effect_on_process",
            "recommendations",
        ]
        for field in required_text:
            self.fields[field].required = self.submitting

        self.fields["confirm"].required = False

    def clean(self):
        cleaned = super().clean()
        if not self.submitting:
            return cleaned

        involves_selected = [
            key
            for key, group in INVOLVE_GROUPS.items()
            if cleaned.get(group["field"])
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

        return cleaned


class VerifierSeverityForm(forms.Form):
    severity = forms.ChoiceField(
        choices=[("", "Select severity")] + list(Severity.choices),
        label="Severity",
        required=True,
        widget=forms.Select(attrs={"class": "input-field", "id": "verify-severity"}),
    )


class WitnessForm(forms.ModelForm):
    class Meta:
        model = Witness
        fields = ["name", "designation"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "input-field witness-name", "placeholder": "Witness name"}),
            "designation": forms.TextInput(
                attrs={"class": "input-field witness-designation", "placeholder": "Designation"}
            ),
        }


class BaseWitnessFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        active = 0
        for form in self.forms:
            if not form.cleaned_data or form.cleaned_data.get("DELETE"):
                continue
            name = (form.cleaned_data.get("name") or "").strip()
            designation = (form.cleaned_data.get("designation") or "").strip()
            if name or designation:
                if not name or not designation:
                    raise forms.ValidationError(
                        "Each witness must have both a name and a designation, or remove the empty row."
                    )
                active += 1
        if active < 1:
            raise forms.ValidationError(
                "At least one witness is required. Click Add witness and enter name and designation."
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


def witness_formset(instance=None, data=None):
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
        return Factory(data, instance=instance) if instance else Factory(data)
    return Factory(instance=instance) if instance else Factory()


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


class ReassignForm(forms.Form):
    role_kind = forms.ChoiceField(
        choices=[("verifier", "Verifier"), ("approver", "Approver")],
        widget=forms.RadioSelect,
    )
    new_assignee = forms.ModelChoiceField(queryset=None, label="New assignee")
    reason = forms.CharField(widget=forms.Textarea(attrs={"rows": 3, "class": "input-field"}), min_length=5)

    def __init__(self, incident, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.incident = incident
        self.fields["new_assignee"].queryset = incident.reporter.__class__.objects.none()

    def set_assignee_queryset(self, qs):
        self.fields["new_assignee"].queryset = qs


class UserAdminForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput(attrs={"class": "input-field"}), required=False)

    class Meta:
        from accounts.models import User

        model = User
        fields = [
            "username",
            "email",
            "first_name",
            "last_name",
            "designation",
            "role",
            "assigned_location",
            "is_active",
        ]

    def __init__(self, *args, **kwargs):
        from accounts.models import Role, User

        super().__init__(*args, **kwargs)
        self._meta.model = User
        for name, field in self.fields.items():
            if name == "is_active":
                continue
            if name in {"assigned_location", "role"}:
                field.widget.attrs["class"] = "input-field"
            elif name != "password":
                field.widget.attrs.setdefault("class", "input-field")

        role = self._selected_role()
        self.show_location_field = role in {Role.SUPERVISOR, Role.SHOP_FLOOR_MANAGER}
        if self.show_location_field:
            self.fields["assigned_location"].required = True
        else:
            self.fields["assigned_location"].required = False

    def _selected_role(self):
        from accounts.models import Role

        if self.data.get("role"):
            return self.data.get("role")
        if self.instance.pk:
            return self.instance.role
        return Role.WORKER

    def clean(self):
        cleaned = super().clean()
        from accounts.models import Role

        role = cleaned.get("role")
        loc = cleaned.get("assigned_location")
        if role in {Role.SUPERVISOR, Role.SHOP_FLOOR_MANAGER} and not loc:
            raise forms.ValidationError("Supervisor and Shop Floor Manager must have an assigned location.")
        if role not in {Role.SUPERVISOR, Role.SHOP_FLOOR_MANAGER}:
            cleaned["assigned_location"] = None
        if not self.instance.pk and not cleaned.get("password"):
            raise forms.ValidationError("Password is required when creating a new user.")
        return cleaned

    def save(self, commit=True):
        from accounts.models import Role

        user = super().save(commit=False)
        if user.role not in {Role.SUPERVISOR, Role.SHOP_FLOOR_MANAGER}:
            user.assigned_location = None
        password = self.cleaned_data.get("password")
        if password:
            user.set_password(password)
        if commit:
            user.save()
        return user


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
