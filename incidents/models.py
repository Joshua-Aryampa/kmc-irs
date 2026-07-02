from django.db import models


class IncidentStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    PENDING_VERIFICATION = "PENDING_VERIFICATION", "Pending verification"
    RETURNED_TO_VERIFIER = "RETURNED_TO_VERIFIER", "Returned to verifier"
    RETURNED_TO_REPORTER = "RETURNED_TO_REPORTER", "Returned to reporter"
    PENDING_APPROVAL = "PENDING_APPROVAL", "Pending approval"
    CLOSED = "CLOSED", "Closed"


class Severity(models.TextChoices):
    INSIGNIFICANT = "INSIGNIFICANT", "Insignificant"
    MINOR = "MINOR", "Minor"
    MODERATE = "MODERATE", "Moderate"
    MAJOR = "MAJOR", "Major"
    CATASTROPHIC = "CATASTROPHIC", "Catastrophic"


class Incident(models.Model):
    incident_id = models.CharField(max_length=32, unique=True, null=True, blank=True)
    status = models.CharField(
        max_length=32, choices=IncidentStatus.choices, default=IncidentStatus.DRAFT
    )
    incident_date = models.DateField(null=True, blank=True)
    incident_time = models.TimeField(null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    scene_location = models.CharField(max_length=70, blank=True)

    involves_person = models.BooleanField(default=False)
    involves_product = models.BooleanField(default=False)
    involves_premises = models.BooleanField(default=False)
    involves_property = models.BooleanField(default=False)

    classification_injury = models.BooleanField(default=False)
    classification_breakdown = models.BooleanField(default=False)
    classification_damage = models.BooleanField(default=False)
    classification_accident = models.BooleanField(default=False)
    classification_fault = models.BooleanField(default=False)
    classification_fire = models.BooleanField(default=False)
    classification_assault = models.BooleanField(default=False)
    classification_power_outage = models.BooleanField(default=False)
    classification_theft_vandalism = models.BooleanField(default=False)
    classification_loss = models.BooleanField(default=False)
    classification_water_shortage = models.BooleanField(default=False)
    classification_other = models.BooleanField(default=False)
    classification_other_text = models.CharField(max_length=255, blank=True)

    other_person = models.BooleanField(default=False)
    other_person_text = models.CharField(max_length=255, blank=True)
    other_premises = models.BooleanField(default=False)
    other_premises_text = models.CharField(max_length=255, blank=True)
    other_product = models.BooleanField(default=False)
    other_product_text = models.CharField(max_length=255, blank=True)
    other_property = models.BooleanField(default=False)
    other_property_text = models.CharField(max_length=255, blank=True)

    severity = models.CharField(max_length=16, choices=Severity.choices, blank=True)
    description = models.TextField(blank=True)
    possible_causes = models.TextField(blank=True)
    corrective_actions_taken = models.TextField(blank=True)
    immediate_actions = models.TextField(blank=True)
    effect_on_process = models.TextField(blank=True)
    recommendations = models.TextField(blank=True)

    is_late_submission = models.BooleanField(default=False)
    late_reason = models.TextField(blank=True)

    reporter = models.ForeignKey(
        "accounts.User", on_delete=models.PROTECT, related_name="reported_incidents"
    )
    verifier = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="verification_incidents",
        null=True,
        blank=True,
    )
    approver = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="approval_incidents",
        null=True,
        blank=True,
    )

    return_comment = models.TextField(blank=True)
    pending_approver_comment = models.TextField(blank=True)

    reporter_confirmed_at = models.DateTimeField(null=True, blank=True)
    verifier_confirmed_at = models.DateTimeField(null=True, blank=True)
    approver_confirmed_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    reporter_signature = models.ImageField(upload_to="signatures/%Y/%m/", null=True, blank=True)
    verifier_signature = models.ImageField(upload_to="signatures/%Y/%m/", null=True, blank=True)
    approver_signature = models.ImageField(upload_to="signatures/%Y/%m/", null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.incident_id or f"Draft #{self.pk}"

    @property
    def is_editable_by_reporter(self):
        return self.status in {
            IncidentStatus.DRAFT,
            IncidentStatus.RETURNED_TO_REPORTER,
        }

    @property
    def is_closed(self):
        return self.status == IncidentStatus.CLOSED

    def involves_labels(self):
        labels = []
        if self.involves_person:
            labels.append("Person(s)")
        if self.involves_product:
            labels.append("Product(s)")
        if self.involves_premises:
            labels.append("Premises")
        if self.involves_property:
            labels.append("Property")
        return labels

    def classification_labels(self):
        mapping = [
            (self.classification_injury, "Injury"),
            (self.classification_breakdown, "Breakdown"),
            (self.classification_damage, "Damage"),
            (self.classification_accident, "Accident"),
            (self.classification_fault, "Fault"),
            (self.classification_fire, "Fire"),
            (self.classification_assault, "Assault"),
            (self.classification_power_outage, "Power Outage"),
            (self.classification_theft_vandalism, "Theft/Vandalism"),
            (self.classification_loss, "Loss"),
            (self.classification_water_shortage, "Water Shortage"),
        ]
        labels = [label for flag, label in mapping if flag]
        for flag, text, prefix in [
            (self.other_person, self.other_person_text, "Person(s) Other"),
            (self.other_premises, self.other_premises_text, "Premises Other"),
            (self.other_product, self.other_product_text, "Product(s) Other"),
            (self.other_property, self.other_property_text, "Property Other"),
        ]:
            if flag:
                labels.append(f"{prefix} ({text or 'specified'})")
        if self.classification_other and self.classification_other_text:
            labels.append(f"Other ({self.classification_other_text})")
        return labels


class Witness(models.Model):
    incident = models.ForeignKey(Incident, on_delete=models.CASCADE, related_name="witnesses")
    name = models.CharField(max_length=255)
    designation = models.CharField(max_length=255, blank=True, default="")
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]


class IncidentPhoto(models.Model):
    incident = models.ForeignKey(Incident, on_delete=models.CASCADE, related_name="photos")
    image = models.ImageField(upload_to="incidents/%Y/%m/")
    original_filename = models.CharField(max_length=255)
    file_size_bytes = models.PositiveIntegerField()
    mime_type = models.CharField(max_length=64)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]


class TimelineEntryType(models.TextChoices):
    CREATED = "CREATED", "Created"
    SUBMITTED = "SUBMITTED", "Submitted"
    VERIFIED = "VERIFIED", "Verified"
    VERIFICATION_REJECTED = "VERIFICATION_REJECTED", "Verification rejected"
    APPROVED = "APPROVED", "Approved"
    APPROVAL_REJECTED = "APPROVAL_REJECTED", "Approval rejected"
    COMMENT = "COMMENT", "Comment"
    RETURNED_TO_REPORTER = "RETURNED_TO_REPORTER", "Returned to reporter"
    REASSIGNED_VERIFIER = "REASSIGNED_VERIFIER", "Verifier reassigned"
    REASSIGNED_APPROVER = "REASSIGNED_APPROVER", "Approver reassigned"
    LATE_FLAGGED = "LATE_FLAGGED", "Late submission flagged"


class TimelineEntry(models.Model):
    incident = models.ForeignKey(Incident, on_delete=models.CASCADE, related_name="timeline_entries")
    entry_type = models.CharField(max_length=32, choices=TimelineEntryType.choices)
    actor = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="timeline_entries"
    )
    actor_role = models.CharField(max_length=32, blank=True)
    message = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]


class IncidentSequence(models.Model):
    year = models.PositiveSmallIntegerField(primary_key=True)
    last_sequence = models.PositiveIntegerField(default=0)


class NotificationLog(models.Model):
    incident = models.ForeignKey(Incident, on_delete=models.CASCADE, related_name="notifications")
    recipient_email = models.EmailField()
    notification_type = models.CharField(max_length=32)
    status = models.CharField(max_length=16, default="PENDING")
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
