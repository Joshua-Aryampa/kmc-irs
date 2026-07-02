from django.conf import settings
from django.core.paginator import Paginator


def paginate_queryset(request, queryset, page_param="page", per_page=None):
    per_page = per_page or settings.INCIDENT_LIST_PAGE_SIZE
    paginator = Paginator(queryset, per_page)
    page_number = request.GET.get(page_param) or 1
    return paginator.get_page(page_number)
