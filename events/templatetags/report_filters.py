from django import template

register = template.Library()

@register.filter
def percentage(value, total):
    try:
        if total == 0:
            return 0
        return (value / total) * 100
    except (ValueError, ZeroDivisionError, TypeError):
        return 0 