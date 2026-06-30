from django import template

register = template.Library()


@register.filter
def get_item(mapping, key):
    if hasattr(mapping, "__getitem__"):
        return mapping[key]
    return getattr(mapping, key, "")
