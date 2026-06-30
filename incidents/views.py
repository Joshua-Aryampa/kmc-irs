from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.models import Role, User
from incidents.forms import (
    CommentForm,
    ForwardCommentForm,
    IncidentForm,
    PhotoUploadForm,
    ReassignForm,
    UserAdminForm,
    VerifierSeverityForm,
    witness_formset,
)
from incidents.models import Incident, IncidentPhoto, IncidentStatus, Severity, TimelineEntryType
from incidents.permissions import incidents_for_user, queue_visibility, user_can_view_incident
from incidents.services.routing import eligible_reassignments
from incidents.services.workflow import (
    WorkflowError,
    add_comment,
    approve_incident,
    forward_to_reporter,
    reassign,
    reject_approval,
    reject_verification,
    submit_incident,
    verify_incident,
)
from incidents.services import pdf as pdf_service
from incidents.services import export as export_service


def _forbidden_if_not(view_fn):
    def wrapper(request, *args, **kwargs):
        incident = get_object_or_404(Incident, pk=kwargs.get("pk") or args[0])
        if not user_can_view_incident(request.user, incident):
            return HttpResponseForbidden("You do not have permission to view this incident.")
        return view_fn(request, incident, *args[1:], **kwargs)

    return wrapper


@login_required
def dashboard(request):
    qs = incidents_for_user(request.user)
    status = request.GET.get("status")
    location = request.GET.get("location")
    severity = request.GET.get("severity")
    late = request.GET.get("late")
    date_from = request.GET.get("date_from")
    date_to = request.GET.get("date_to")

    if status:
        qs = qs.filter(status=status)
    if location:
        qs = qs.filter(scene_location_id=location)
    if severity:
        qs = qs.filter(severity=severity)
    if late == "1":
        qs = qs.filter(is_late_submission=True)
    if date_from:
        qs = qs.filter(incident_date__gte=date_from)
    if date_to:
        qs = qs.filter(incident_date__lte=date_to)

    summary = {
        "open": qs.exclude(status=IncidentStatus.CLOSED).count(),
        "closed": qs.filter(status=IncidentStatus.CLOSED).count(),
        "pending_verification": qs.filter(status=IncidentStatus.PENDING_VERIFICATION).count(),
        "pending_approval": qs.filter(status=IncidentStatus.PENDING_APPROVAL).count(),
        "late": qs.filter(is_late_submission=True).count(),
    }
    by_location = (
        qs.values("scene_location__name").annotate(c=Count("id")).order_by("scene_location__name")
    )

    if request.GET.get("export") == "csv":
        return export_service.incidents_csv(qs)

    from incidents.models import Location

    return render(
        request,
        "incidents/dashboard.html",
        {
            "incidents": qs[:200],
            "summary": summary,
            "by_location": by_location,
            "locations": Location.objects.filter(is_active=True),
            "statuses": IncidentStatus.choices,
            "severities": Severity.choices,
            "filters": request.GET,
        },
    )


@login_required
def my_queue(request):
    user = request.user
    visibility = queue_visibility(user)
    verify_qs = Incident.objects.filter(verifier=user, status=IncidentStatus.PENDING_VERIFICATION)
    approve_qs = Incident.objects.filter(approver=user, status=IncidentStatus.PENDING_APPROVAL)
    forward_qs = Incident.objects.filter(verifier=user, status=IncidentStatus.RETURNED_TO_VERIFIER)
    returned_qs = Incident.objects.filter(reporter=user, status=IncidentStatus.RETURNED_TO_REPORTER)

    return render(
        request,
        "incidents/queue.html",
        {
            "verify_qs": verify_qs,
            "approve_qs": approve_qs,
            "forward_qs": forward_qs,
            "returned_qs": returned_qs,
            "queue_visibility": visibility,
        },
    )


@login_required
def incident_create(request):
    if not request.user.can_report():
        messages.error(request, "Your role cannot create incident reports.")
        return redirect("dashboard")

    from incidents.classifications import INVOLVE_GROUPS
    from incidents.models import TimelineEntry, TimelineEntryType

    if request.method == "POST":
        submitting = request.POST.get("action") == "submit"
        draft_form = IncidentForm(request.POST, submitting=False)
        submit_form = IncidentForm(request.POST, submitting=True) if submitting else draft_form
        form = submit_form if submitting else draft_form
        photo_form = PhotoUploadForm(request.POST, request.FILES)
        incident = None
        photo_errors = []

        draft_valid = draft_form.is_valid()
        if draft_valid:
            incident = draft_form.save(commit=False)
            incident.reporter = request.user
            incident.status = IncidentStatus.DRAFT
            incident.save()
            if not incident.timeline_entries.filter(entry_type=TimelineEntryType.CREATED).exists():
                TimelineEntry.objects.create(
                    incident=incident,
                    entry_type=TimelineEntryType.CREATED,
                    actor=request.user,
                    actor_role=request.user.role,
                )
            formset = witness_formset(instance=incident, data=request.POST)
        else:
            formset = witness_formset(data=request.POST)

        formset_valid = formset.is_valid() if draft_valid else False

        if draft_valid:
            if formset_valid:
                formset.save()
            new_photos = request.FILES.getlist("photos")
            if new_photos:
                try:
                    photos = photo_form.validate_photos(existing_count=incident.photos.count())
                    _save_photos(incident, photos)
                except Exception as exc:
                    photo_errors.append(str(exc))

            if submitting:
                if not submit_form.is_valid():
                    form = submit_form
                elif not formset_valid:
                    pass
                elif not photo_errors and incident.photos.count() == 0:
                    photo_errors.append("At least one photo is required before you can submit the report.")
                elif not photo_errors:
                    try:
                        submit_incident(incident, request.user)
                        messages.success(
                            request, f"Incident {incident.incident_id} submitted for verification."
                        )
                        return redirect("incident_detail", pk=incident.pk)
                    except Exception as exc:
                        messages.error(request, str(exc))
            elif not photo_errors:
                messages.success(request, "Draft saved.")
                return redirect("incident_edit", pk=incident.pk)

            for msg in photo_errors:
                messages.error(request, msg)

        return render(
            request,
            "incidents/form.html",
            {
                "form": form,
                "formset": formset,
                "photo_form": photo_form,
                "incident": incident,
                "is_create": incident is None,
                "involve_groups": INVOLVE_GROUPS,
                "late_minutes": settings.INCIDENT_LATE_MINUTES,
            },
        )
    else:
        form = IncidentForm()
        formset = witness_formset()
        photo_form = PhotoUploadForm()
        incident = None

    return render(
        request,
        "incidents/form.html",
        {
            "form": form,
            "formset": formset,
            "photo_form": photo_form,
            "incident": incident,
            "is_create": True,
            "involve_groups": INVOLVE_GROUPS,
            "late_minutes": settings.INCIDENT_LATE_MINUTES,
        },
    )


@login_required
def incident_edit(request, pk):
    from incidents.classifications import INVOLVE_GROUPS

    incident = get_object_or_404(Incident, pk=pk)
    if incident.reporter_id != request.user.id or not incident.is_editable_by_reporter:
        return HttpResponseForbidden("You cannot edit this incident.")

    if request.method == "POST":
        submitting = request.POST.get("action") == "submit"
        draft_form = IncidentForm(request.POST, instance=incident, submitting=False)
        submit_form = IncidentForm(request.POST, instance=incident, submitting=True) if submitting else draft_form
        form = submit_form if submitting else draft_form
        formset = witness_formset(instance=incident, data=request.POST)
        photo_form = PhotoUploadForm(request.POST, request.FILES)
        photo_errors = []

        draft_valid = draft_form.is_valid()
        formset_valid = formset.is_valid() if draft_valid else False

        if draft_valid:
            incident = draft_form.save()
            if formset_valid:
                formset.save()
            new_photos = request.FILES.getlist("photos")
            if new_photos:
                try:
                    photos = photo_form.validate_photos(existing_count=incident.photos.count())
                    _save_photos(incident, photos)
                except Exception as exc:
                    photo_errors.append(str(exc))

            if submitting:
                if not submit_form.is_valid():
                    form = submit_form
                elif not formset_valid:
                    pass
                elif not photo_errors and incident.photos.count() == 0:
                    photo_errors.append("At least one photo is required before you can submit the report.")
                elif not photo_errors:
                    try:
                        submit_incident(incident, request.user)
                        messages.success(request, f"Incident {incident.incident_id} submitted.")
                        return redirect("incident_detail", pk=incident.pk)
                    except Exception as exc:
                        messages.error(request, str(exc))
            elif not photo_errors:
                messages.success(request, "Draft saved.")
                return redirect("incident_edit", pk=incident.pk)

            for msg in photo_errors:
                messages.error(request, msg)

        return render(
            request,
            "incidents/form.html",
            {
                "form": form,
                "formset": formset,
                "photo_form": photo_form,
                "incident": incident,
                "is_create": False,
                "involve_groups": INVOLVE_GROUPS,
                "late_minutes": settings.INCIDENT_LATE_MINUTES,
            },
        )
    else:
        form = IncidentForm(instance=incident)
        formset = witness_formset(instance=incident)
        photo_form = PhotoUploadForm()

    return render(
        request,
        "incidents/form.html",
        {
            "form": form,
            "formset": formset,
            "photo_form": photo_form,
            "incident": incident,
            "is_create": False,
            "involve_groups": INVOLVE_GROUPS,
            "late_minutes": settings.INCIDENT_LATE_MINUTES,
        },
    )


def _save_photos(incident, photos):
    order = incident.photos.count()
    for photo in photos:
        IncidentPhoto.objects.create(
            incident=incident,
            image=photo,
            original_filename=photo.name,
            file_size_bytes=photo.size,
            mime_type=photo.content_type or "application/octet-stream",
            sort_order=order,
        )
        order += 1


@login_required
def incident_detail(request, pk):
    incident = get_object_or_404(Incident, pk=pk)
    if not user_can_view_incident(request.user, incident):
        return HttpResponseForbidden("You do not have permission to view this incident.")

    ctx = {
        "incident": incident,
        "timeline": incident.timeline_entries.select_related("actor"),
        "comment_form": CommentForm(),
        "forward_form": ForwardCommentForm(
            initial={"comment": incident.pending_approver_comment or incident.return_comment}
        ),
        "reassign_form": (
            ReassignForm(incident)
            if request.user.role == Role.ADMIN and not incident.is_closed
            else None
        ),
        "can_edit": incident.reporter_id == request.user.id and incident.is_editable_by_reporter,
        "can_verify": request.user.id == incident.verifier_id
        and incident.status == IncidentStatus.PENDING_VERIFICATION,
        "can_approve": request.user.id == incident.approver_id
        and incident.status == IncidentStatus.PENDING_APPROVAL,
        "can_forward": request.user.id == incident.verifier_id
        and incident.status == IncidentStatus.RETURNED_TO_VERIFIER,
    }
    if ctx["can_verify"]:
        ctx["severity_form"] = VerifierSeverityForm(initial={"severity": incident.severity or None})
    return render(request, "incidents/detail.html", ctx)


@login_required
def incident_verify(request, pk):
    incident = get_object_or_404(Incident, pk=pk)
    form = VerifierSeverityForm(request.POST)
    if form.is_valid():
        try:
            verify_incident(incident, request.user, form.cleaned_data["severity"])
            messages.success(request, "Incident verified and sent for approval.")
        except WorkflowError as exc:
            messages.error(request, str(exc))
    else:
        messages.error(request, "Select a severity before verifying.")
    return redirect("incident_detail", pk=pk)


@login_required
def incident_reject_verify(request, pk):
    incident = get_object_or_404(Incident, pk=pk)
    form = CommentForm(request.POST)
    if form.is_valid():
        try:
            reject_verification(incident, request.user, form.cleaned_data["comment"])
            messages.success(request, "Incident returned to reporter.")
        except WorkflowError as exc:
            messages.error(request, str(exc))
    else:
        messages.error(request, "A comment of at least 10 characters is required.")
    return redirect("incident_detail", pk=pk)


@login_required
def incident_approve(request, pk):
    incident = get_object_or_404(Incident, pk=pk)
    try:
        approve_incident(incident, request.user)
        messages.success(request, "Incident approved and closed.")
    except WorkflowError as exc:
        messages.error(request, str(exc))
    return redirect("incident_detail", pk=pk)


@login_required
def incident_reject_approve(request, pk):
    incident = get_object_or_404(Incident, pk=pk)
    form = CommentForm(request.POST)
    if form.is_valid():
        try:
            reject_approval(incident, request.user, form.cleaned_data["comment"])
            messages.success(request, "Incident returned to verifier.")
        except WorkflowError as exc:
            messages.error(request, str(exc))
    else:
        messages.error(request, "A comment of at least 10 characters is required.")
    return redirect("incident_detail", pk=pk)


@login_required
def incident_forward(request, pk):
    incident = get_object_or_404(Incident, pk=pk)
    form = ForwardCommentForm(request.POST)
    if form.is_valid():
        try:
            forward_to_reporter(incident, request.user, form.cleaned_data["comment"])
            messages.success(request, "Incident returned to reporter with your comment.")
        except WorkflowError as exc:
            messages.error(request, str(exc))
    else:
        messages.error(request, "Comment is required.")
    return redirect("incident_detail", pk=pk)


@login_required
def incident_comment(request, pk):
    incident = get_object_or_404(Incident, pk=pk)
    form = CommentForm(request.POST)
    if form.is_valid():
        try:
            add_comment(incident, request.user, form.cleaned_data["comment"])
            messages.success(request, "Comment added to timeline.")
        except WorkflowError as exc:
            messages.error(request, str(exc))
    return redirect("incident_detail", pk=pk)


@login_required
def incident_pdf(request, pk):
    incident = get_object_or_404(Incident, pk=pk)
    if not user_can_view_incident(request.user, incident):
        return HttpResponseForbidden()
    if not incident.is_closed:
        messages.error(request, "PDF export is only available for closed incidents.")
        return redirect("incident_detail", pk=pk)
    pdf_bytes = pdf_service.render_incident_pdf(request, incident)
    filename = (incident.incident_id or "incident").replace("/", "-") + ".pdf"
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@login_required
def photo_delete(request, pk, photo_pk):
    incident = get_object_or_404(Incident, pk=pk)
    if incident.reporter_id != request.user.id or not incident.is_editable_by_reporter:
        return HttpResponseForbidden()
    photo = get_object_or_404(IncidentPhoto, pk=photo_pk, incident=incident)
    if incident.photos.count() <= 1:
        messages.error(request, "At least one photo must remain.")
    else:
        photo.image.delete(save=False)
        photo.delete()
        messages.success(request, "Photo removed.")
    return redirect("incident_edit", pk=pk)


# --- Admin user management ---


@login_required
def admin_users(request):
    if request.user.role != Role.ADMIN:
        return HttpResponseForbidden()
    return render(request, "incidents/admin/users_list.html", {"users": User.objects.all().select_related("assigned_location")})


@login_required
def admin_user_create(request):
    if request.user.role != Role.ADMIN:
        return HttpResponseForbidden()
    if request.method == "POST":
        form = UserAdminForm(request.POST)
        if form.is_valid():
            user = form.save()
            if not form.cleaned_data.get("password"):
                messages.warning(request, "User created without password change — set password if needed.")
            messages.success(request, f"User {user.username} created.")
            return redirect("admin_users")
    else:
        form = UserAdminForm()
    return render(request, "incidents/admin/user_form.html", {"form": form, "title": "Create user"})


@login_required
def admin_user_edit(request, user_pk):
    if request.user.role != Role.ADMIN:
        return HttpResponseForbidden()
    user = get_object_or_404(User, pk=user_pk)
    if request.method == "POST":
        form = UserAdminForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, "User updated.")
            return redirect("admin_users")
    else:
        form = UserAdminForm(instance=user)
    return render(request, "incidents/admin/user_form.html", {"form": form, "title": f"Edit {user.username}"})


@login_required
def admin_reassign(request, pk):
    if request.user.role != Role.ADMIN:
        return HttpResponseForbidden()
    incident = get_object_or_404(Incident, pk=pk)
    role_kind = (request.POST.get("role_kind") if request.method == "POST" else request.GET.get("role_kind")) or "verifier"
    form = ReassignForm(incident, request.POST or None)
    form.set_assignee_queryset(eligible_reassignments(incident, role_kind))
    if request.method == "POST" and form.is_valid():
        try:
            reassign(
                incident,
                request.user,
                form.cleaned_data["role_kind"],
                form.cleaned_data["new_assignee"],
                form.cleaned_data["reason"],
            )
            messages.success(request, "Assignment updated.")
            return redirect("incident_detail", pk=pk)
        except WorkflowError as exc:
            messages.error(request, str(exc))
    return render(request, "incidents/admin/reassign.html", {"incident": incident, "form": form})
