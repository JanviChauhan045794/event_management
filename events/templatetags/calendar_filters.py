from django import template
from datetime import datetime
import calendar
from django.utils import timezone
import re

register = template.Library()

@register.filter
def div(value, arg):
    """
    Divides the value by the argument
    """
    try:
        return float(value) / float(arg)
    except (ValueError, ZeroDivisionError):
        return 0

@register.filter
def get_range(value, start=0):
    """
    Returns a range of numbers from start to value
    """
    return range(int(start), int(value))

@register.filter
def get_item(dictionary, key):
    """
    Returns the value from a dictionary for the given key
    """
    return dictionary.get(str(key)) or dictionary.get(int(key), [])

@register.filter
def parse_month_first_day(month_str):
    """
    Parses a month string (e.g., 'January 2023') and returns the first day of that month
    """
    try:
        # Parse the month string to get the month and year
        month_match = re.match(r'(\w+)\s+(\d{4})', month_str)
        if month_match:
            month_name, year = month_match.groups()
            month_num = {
                'January': 1, 'February': 2, 'March': 3, 'April': 4,
                'May': 5, 'June': 6, 'July': 7, 'August': 8,
                'September': 9, 'October': 10, 'November': 11, 'December': 12
            }.get(month_name, 1)

            # Create a datetime object for the first day of the month
            return datetime(int(year), month_num, 1)
    except (ValueError, AttributeError):
        pass

    # Default to the first day of the current month
    now = timezone.now()
    return datetime(now.year, now.month, 1)

@register.filter
def days_in_month(month_str):
    """
    Returns the number of days in the given month string (e.g., 'January 2023')
    """
    try:
        # Parse the month string to get the month and year
        month_match = re.match(r'(\w+)\s+(\d{4})', month_str)
        if month_match:
            month_name, year = month_match.groups()
            month_num = {
                'January': 1, 'February': 2, 'March': 3, 'April': 4,
                'May': 5, 'June': 6, 'July': 7, 'August': 8,
                'September': 9, 'October': 10, 'November': 11, 'December': 12
            }.get(month_name, 1)

            # Get the number of days in the month
            return calendar.monthrange(int(year), month_num)[1]
    except (ValueError, AttributeError):
        pass

    # Default to the current month
    now = timezone.now()
    return calendar.monthrange(now.year, now.month)[1]

@register.filter
def filter_by_category(events, category_name):
    """
    Filters events by category name
    """
    return [event for event in events if event.category.name == category_name]
