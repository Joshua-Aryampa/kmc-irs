from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET

from incidents.forms import (
    CommentForm,
    ForwardCommentForm,
    IncidentForm,
    PhotoUploadForm,
    VerifierActionForm,
    witness_formset,
)
from incidents.models import Incident, IncidentPhoto, IncidentStatus, Severity, TimelineEntryType
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
from incidents.utils import paginate_queryset


@login_required
def dashboard(request):
    qs = incidents_for_user(request.user)
    status = request.GET.get("status")
    severity = request.GET.get("severity")
    late = request.GET.get("late")
    date_from = request.GET.get("date_from")
    date_to = request.GET.get("date_to")

    if status:
        qs = qs.filter(status=status)
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
        qs.exclude(scene_location="")
        .values("scene_location")
        .annotate(c=Count("id"))
        .order_by("scene_location")
    )

    if request.GET.get("export") == "csv":
        return export_service.incidents_csv(qs)

    page_obj = paginate_queryset(request, qs.select_related("reporter", "verifier", "approver"))

    filter_query = request.GET.copy()
    filter_query.pop("page", None)

    return render(
        request,
        "incidents/dashboard.html",
        {
            "page_obj": page_obj,
            "incidents": page_obj.object_list,
            "summary": summary,
            "by_location": by_location,
            "statuses": IncidentStatus.choices,
            "severities": Severity.choices,
            "filters": request.GET,
            "filter_query": filter_query.urlencode(),
        },
    )


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


@login_required
def incident_create(request):
    if not request.user.can_report():
        messages.error(request, "Your account cannot create incident reports.")
        return redirect("dashboard")

    from incidents.classifications import INVOLVE_GROUPS
    from incidents.models import TimelineEntry, TimelineEntryType

    if request.method == "POST":
        submitting = request.POST.get("action") == "submit"
        draft_form = IncidentForm(request.POST, submitting=False, reporter=request.user)
        submit_form = (
            IncidentForm(request.POST, submitting=True, reporter=request.user) if submitting else draft_form
        )
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
                        verifier = submit_form.cleaned_data["selected_verifier"]
                        submit_incident(incident, request.user, verifier)
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
        submit_form = (
            IncidentForm(request.POST, instance=incident, submitting=True, reporter=request.user)
            if submitting
            else draft_form
        )
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
                        verifier = submit_form.cleaned_data["selected_verifier"]
                        submit_incident(incident, request.user, verifier)
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
