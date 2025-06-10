import qrcode
import base64
import re
from io import BytesIO
import json
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.platypus import Image
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from django.template.loader import get_template
from django.conf import settings
import os
from xhtml2pdf import pisa

def generate_qr_code_base64(data):
    """
    Generate a QR code and return it as a base64 encoded string.
    """
    qr = qrcode.QRCode(
        version=None,  # Auto-determine version based on data size
        error_correction=qrcode.constants.ERROR_CORRECT_H,  # Highest error correction
        box_size=10,
        border=4,
    )
    
    # If data is a dict or list, convert to JSON string
    if isinstance(data, (dict, list)):
        data = json.dumps(data)
    
    qr.add_data(data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    
    # Save image to bytes buffer
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    
    # Convert to base64
    img_str = base64.b64encode(buffer.getvalue()).decode()
    return f"data:image/png;base64,{img_str}"


def parse_location(location_string):
    """Parse a location string into components"""
    # Default structure
    location_data = {
        'location_name': location_string,
        'address': '',
        'city': '',
        'state': '',
        'zip': '',
        'country': ''
    }
    
    # Try to parse if there are commas
    parts = location_string.split(',')
    if len(parts) >= 3:
        location_data['location_name'] = parts[0].strip()
        location_data['address'] = parts[0].strip()
        location_data['city'] = parts[1].strip()
        # Try to parse state and zip from the last part
        last_part = parts[-1].strip()
        state_zip = last_part.split()
        if len(state_zip) >= 2:
            location_data['state'] = state_zip[0]
            location_data['zip'] = state_zip[1]
        else:
            location_data['state'] = last_part
    
    return location_data

def generate_event_qr(event, registration):
    """Generate QR code with event and registration details"""
    # Create QR code data with full details
    qr_data = {
        'event': {
            'id': str(event.event_id),
            'title': event.title,
            'category': event.category.name,
            'start_date': event.start_date.isoformat(),
            'end_date': event.end_date.isoformat(),
            'location': event.location
        },
        'attendee': {
            'id': str(registration.user.user_id),
            'name': f"{registration.user.first_name} {registration.user.last_name}",
            'email': registration.user.email,
            'type': registration.attendee_type.name if registration.attendee_type else 'Standard'
        },
        'registration': {
            'id': str(registration.registration_id),
            'status': registration.status,
            'registered_at': registration.registered_at.isoformat() if registration.registered_at else None,
            'is_checked_in': registration.checked_in if hasattr(registration, 'checked_in') else False
        },
        'verification': {
            'timestamp': datetime.now().isoformat(),
            'type': 'event_ticket'
        }
    }
    
    # Generate QR code with high error correction
    qr = qrcode.QRCode(
        version=None,  # Auto-determine version
        error_correction=qrcode.constants.ERROR_CORRECT_H,  # Highest error correction
        box_size=10,
        border=4,
    )
    qr.add_data(json.dumps(qr_data))
    qr.make(fit=True)
    
    # Create QR code image
    img_buffer = BytesIO()
    qr.make_image(fill_color="black", back_color="white").save(img_buffer)
    img_buffer.seek(0)
    
    return img_buffer

def generate_event_ticket(event, registration):
    """Generate a PDF ticket for an event"""
    # Generate QR code with detailed ticket information
    ticket_data = {
        'event': {
            'id': str(event.event_id),
            'title': event.title,
            'category': event.category.name,
            'start_date': event.start_date.isoformat(),
            'end_date': event.end_date.isoformat(),
            'location': event.location,
            'organizer': event.organizer.get_full_name()
        },
        'attendee': {
            'id': str(registration.user.user_id),
            'name': f"{registration.user.first_name} {registration.user.last_name}",
            'email': registration.user.email,
            'type': registration.attendee_type.name if registration.attendee_type else 'Standard'
        },
        'registration': {
            'id': str(registration.registration_id),
            'status': registration.status,
            'registered_at': registration.registered_at.isoformat() if registration.registered_at else None,
            'is_checked_in': registration.checked_in if hasattr(registration, 'checked_in') else False
        },
        'verification': {
            'timestamp': datetime.now().isoformat(),
            'type': 'event_ticket'
        }
    }
    
    qr_code_base64 = generate_qr_code_base64(json.dumps(ticket_data))

    # Get the template
    template = get_template('ticket_pdf.html')
    
    # Parse location data
    location_data = parse_location(event.location)
    
    # Prepare context
    context = {
        'event': event,
        'user': registration.user,
        'registration': registration,
        'qr_code': qr_code_base64,
        'location_data': location_data,
        'now': datetime.now(),
        'base_url': ''  # This will be handled by link_callback
    }
    
    # Render template
    html = template.render(context)
    
    # Create PDF
    def link_callback(uri, rel):
        """Convert HTML URIs to absolute system paths"""
        # use short variable names
        sUrl = settings.STATIC_URL or ''
        sRoot = settings.STATIC_ROOT or ''
        mUrl = settings.MEDIA_URL or ''
        mRoot = settings.MEDIA_ROOT or ''

        # convert URIs to absolute system paths
        if uri.startswith(mUrl):
            path = os.path.join(mRoot, uri.replace(mUrl, ""))
        elif uri.startswith(sUrl):
            path = os.path.join(sRoot, uri.replace(sUrl, ""))
        else:
            return uri  # handle absolute uri (ie: http://some.tld/foo.png)

        # make sure that file exists
        if not os.path.isfile(path):
            return uri

        return path
    
    # Create PDF with proper resource handling
    pdf_buffer = BytesIO()
    pisa_status = pisa.CreatePDF(
        html,
        dest=pdf_buffer,
        link_callback=link_callback
    )
    
    if pisa_status.err:
        return BytesIO(b'Error generating PDF')
    
    # Reset buffer position
    pdf_buffer.seek(0)
    return pdf_buffer
