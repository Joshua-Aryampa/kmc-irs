from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from incidents.forms import (
    CommentForm,
    ForwardCommentForm,
    IncidentForm,
    PhotoUploadForm,
    VerifierActionForm,
    witness_formset,
)
from incidents.models import Incident, IncidentPhoto, IncidentStatus, Severity, TimelineEntry, TimelineEntryType
from incidents.permissions import incidents_for_user, user_can_view_incident
from incidents.services.keycloak import search_employees
from incidents.services.workflow import (
    WorkflowError,
    add_comment,
    approve_incident,
    forward_to_reporter,
    reject_approval,
    reject_verification,
    submit_incident,
    verify_incident,
)
from incidents.services import pdf as pdf_service
from incidents.services import export as export_service
from incidents.utils import (
    apply_incident_filters,
    filter_form_values,
    incident_summary,
    incidents_by_location,
    paginate_queryset,
)


def _history_context(request, qs):
    qs = apply_incident_filters(qs, request.GET)
    if request.GET.get("export") == "csv":
        return export_service.incidents_csv(qs)

    page_obj = paginate_queryset(
        request, qs.select_related("reporter", "verifier", "approver")
    )
    filter_query = request.GET.copy()
    filter_query.pop("page", None)

    return render(
        request,
        "incidents/history.html",
        {
            "page_obj": page_obj,
            "incidents": page_obj.object_list,
            "summary": incident_summary(qs),
            "by_location": incidents_by_location(qs),
            "statuses": IncidentStatus.choices,
            "severities": Severity.choices,
            "filters": filter_form_values(request.GET),
            "filter_query": filter_query.urlencode(),
        },
    )


@login_required
def dashboard(request):
    base_qs = incidents_for_user(request.user)
    recent = base_qs.select_related("reporter", "verifier", "approver")[
        : settings.DASHBOARD_RECENT_COUNT
    ]

    return render(
        request,
        "incidents/dashboard.html",
        {
            "summary": incident_summary(base_qs),
            "recent_incidents": recent,
            "total_incidents": base_qs.count(),
        },
    )


@login_required
def history(request):
    qs = incidents_for_user(request.user)
    return _history_context(request, qs)


@login_required
def my_queue(request):
    user = request.user
    sections = [
        ("verify", Incident.objects.filter(verifier=user, status=IncidentStatus.PENDING_VERIFICATION)),
        ("approve", Incident.objects.filter(approver=user, status=IncidentStatus.PENDING_APPROVAL)),
        ("forward", Incident.objects.filter(verifier=user, status=IncidentStatus.RETURNED_TO_VERIFIER)),
        ("returned", Incident.objects.filter(reporter=user, status=IncidentStatus.RETURNED_TO_REPORTER)),
    ]
    queue_pages = {}
    filter_query = request.GET.copy()
    for key in ("page_verify", "page_approve", "page_forward", "page_returned"):
        filter_query.pop(key, None)
    shared_query = filter_query.urlencode()

    for key, queryset in sections:
        queue_pages[key] = paginate_queryset(
            request,
            queryset.select_related("reporter", "verifier", "approver"),
            page_param=f"page_{key}",
        )

    return render(
        request,
        "incidents/queue.html",
        {
            "verify_page": queue_pages["verify"],
            "approve_page": queue_pages["approve"],
            "forward_page": queue_pages["forward"],
            "returned_page": queue_pages["returned"],
            "verify_qs": queue_pages["verify"].object_list,
            "approve_qs": queue_pages["approve"].object_list,
            "forward_qs": queue_pages["forward"].object_list,
            "returned_qs": queue_pages["returned"].object_list,
            "filter_query": shared_query,
        },
    )


@login_required
@require_GET
def employee_search(request):
    query = request.GET.get("q", "")
    results = search_employees(query, limit=10)
    return JsonResponse({"results": results})


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


def _ensure_created_timeline(incident, user):
    if not incident.timeline_entries.filter(entry_type=TimelineEntryType.CREATED).exists():
        TimelineEntry.objects.create(
            incident=incident,
            entry_type=TimelineEntryType.CREATED,
            actor=user,
            actor_role=user.role,
        )


def _submit_photo_errors(photo_form, request, incident=None):
    errors = []
    new_photos = request.FILES.getlist("photos")
    existing_count = incident.photos.count() if incident else 0
    if new_photos:
        try:
            photo_form.validate_photos(existing_count=existing_count)
        except Exception as exc:
            errors.append(str(exc))
    elif existing_count == 0:
        errors.append("At least one photo is required before you can submit the report.")
    return errors, new_photos


def _persist_new_photos(incident, photo_form, new_photos):
    if not new_photos:
        return
    photos = photo_form.validate_photos(existing_count=incident.photos.count())
    _save_photos(incident, photos)


@login_required
def incident_create(request):
    if not request.user.can_report():
        messages.error(request, "Your account cannot create incident reports.")
        return redirect("dashboard")

    from incidents.classifications import INVOLVE_GROUPS

    if request.method == "POST":
        submitting = request.POST.get("action") == "submit"
        draft_form = IncidentForm(request.POST, submitting=False, reporter=request.user)
        submit_form = IncidentForm(request.POST, submitting=True, reporter=request.user)
        photo_form = PhotoUploadForm(request.POST, request.FILES)
        incident = None
        photo_errors = []

        if submitting:
            form = submit_form
            formset = witness_formset(data=request.POST, submitting=True)
            submit_valid = submit_form.is_valid()
            formset_valid = formset.is_valid() if submit_valid else False
            if submit_valid and formset_valid:
                photo_errors, new_photos = _submit_photo_errors(photo_form, request)

            if submit_valid and formset_valid and not photo_errors:
                try:
                    with transaction.atomic():
                        incident = submit_form.save(commit=False)
                        incident.reporter = request.user
                        incident.status = IncidentStatus.DRAFT
                        incident.save()
                        _ensure_created_timeline(incident, request.user)
                        bound_formset = witness_formset(
                            instance=incident, data=request.POST, submitting=True
                        )
                        bound_formset.is_valid()
                        bound_formset.save()
                        _persist_new_photos(incident, photo_form, new_photos)
                        verifier = submit_form.cleaned_data["selected_verifier"]
                        submit_incident(incident, request.user, verifier)
                    messages.success(
                        request, f"Incident {incident.incident_id} submitted for verification."
                    )
                    return redirect("incident_detail", pk=incident.pk)
                except Exception as exc:
                    messages.error(request, str(exc))
        else:
            form = draft_form
            formset = witness_formset(data=request.POST, submitting=False)
            if draft_form.is_valid() and formset.is_valid():
                incident = draft_form.save(commit=False)
                incident.reporter = request.user
                incident.status = IncidentStatus.DRAFT
                incident.save()
                _ensure_created_timeline(incident, request.user)
                bound_formset = witness_formset(
                    instance=incident, data=request.POST, submitting=False
                )
                bound_formset.is_valid()
                bound_formset.save()
                new_photos = request.FILES.getlist("photos")
                if new_photos:
                    try:
                        _persist_new_photos(incident, photo_form, new_photos)
                    except Exception as exc:
                        photo_errors.append(str(exc))
                if not photo_errors:
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
                "show_verifier_search": True,
            },
        )

    form = IncidentForm(reporter=request.user)
    formset = witness_formset()
    photo_form = PhotoUploadForm()

    return render(
        request,
        "incidents/form.html",
        {
            "form": form,
            "formset": formset,
            "photo_form": photo_form,
            "incident": None,
            "is_create": True,
            "involve_groups": INVOLVE_GROUPS,
            "late_minutes": settings.INCIDENT_LATE_MINUTES,
            "show_verifier_search": True,
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
        draft_form = IncidentForm(
            request.POST, instance=incident, submitting=False, reporter=request.user
        )
        submit_form = IncidentForm(
            request.POST, instance=incident, submitting=True, reporter=request.user
        )
        photo_form = PhotoUploadForm(request.POST, request.FILES)
        photo_errors = []

        if submitting:
            form = submit_form
            formset = witness_formset(instance=incident, data=request.POST, submitting=True)
            submit_valid = submit_form.is_valid()
            formset_valid = formset.is_valid() if submit_valid else False
            if submit_valid and formset_valid:
                photo_errors, new_photos = _submit_photo_errors(photo_form, request, incident)

            if submit_valid and formset_valid and not photo_errors:
                try:
                    with transaction.atomic():
                        submit_form.save()
                        formset.save()
                        _persist_new_photos(incident, photo_form, new_photos)
                        verifier = submit_form.cleaned_data["selected_verifier"]
                        submit_incident(incident, request.user, verifier)
                    messages.success(request, f"Incident {incident.incident_id} submitted.")
                    return redirect("incident_detail", pk=incident.pk)
                except Exception as exc:
                    messages.error(request, str(exc))
        else:
            form = draft_form
            formset = witness_formset(instance=incident, data=request.POST, submitting=False)
            if draft_form.is_valid() and formset.is_valid():
                draft_form.save()
                formset.save()
                new_photos = request.FILES.getlist("photos")
                if new_photos:
                    try:
                        _persist_new_photos(incident, photo_form, new_photos)
                    except Exception as exc:
                        photo_errors.append(str(exc))
                if not photo_errors:
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
                "show_verifier_search": True,
            },
        )

    form = IncidentForm(instance=incident, reporter=request.user)
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
            "show_verifier_search": True,
        },
    )


@login_required
@require_POST
def incident_delete(request, pk):
    incident = get_object_or_404(Incident, pk=pk)
    if incident.reporter_id != request.user.id:
        return HttpResponseForbidden("You cannot delete this incident.")
    if incident.status != IncidentStatus.DRAFT:
        messages.error(request, "Only draft incidents can be deleted.")
        return redirect("incident_detail", pk=pk)
    incident.delete()
    messages.success(request, "Draft incident deleted.")
    return redirect("dashboard")


@login_required
def incident_detail(request, pk):
    incident = get_object_or_404(
        Incident.objects.select_related("reporter", "verifier", "approver"),
        pk=pk,
    )
    if not user_can_view_incident(request.user, incident):
        return HttpResponseForbidden("You do not have permission to view this incident.")

    ctx = {
        "incident": incident,
        "timeline": incident.timeline_entries.select_related("actor"),
        "comment_form": CommentForm(),
        "forward_form": ForwardCommentForm(
            initial={"comment": incident.pending_approver_comment or incident.return_comment}
        ),
        "can_edit": incident.reporter_id == request.user.id and incident.is_editable_by_reporter,
        "can_delete": incident.reporter_id == request.user.id
        and incident.status == IncidentStatus.DRAFT,
        "can_verify": request.user.id == incident.verifier_id
        and incident.status == IncidentStatus.PENDING_VERIFICATION,
        "can_approve": request.user.id == incident.approver_id
        and incident.status == IncidentStatus.PENDING_APPROVAL,
        "can_forward": request.user.id == incident.verifier_id
        and incident.status == IncidentStatus.RETURNED_TO_VERIFIER,
    }
    if ctx["can_verify"]:
        ctx["verify_form"] = VerifierActionForm(incident=incident)
    return render(request, "incidents/detail.html", ctx)


@login_required
def incident_verify(request, pk):
    incident = get_object_or_404(Incident, pk=pk)
    form = VerifierActionForm(request.POST, incident=incident)
    if form.is_valid():
        try:
            verify_incident(
                incident,
                request.user,
                form.cleaned_data["severity"],
                form.cleaned_data["selected_approver"],
            )
            messages.success(request, "Incident verified and sent for approval.")
        except WorkflowError as exc:
            messages.error(request, str(exc))
    else:
        messages.error(request, "Select severity and approver before verifying.")
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
