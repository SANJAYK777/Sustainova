import qrcode
import io
import base64
import os


def generate_event_qr(event_token: str) -> str:
    """
    Generate a base64 PNG QR code that points to
    the event RSVP page using the event token.
    """

    frontend_base_url = os.getenv("FRONTEND_BASE_URL", "http://localhost:3000").rstrip("/")
    url = f"{frontend_base_url}/event/{event_token}"

    qr = qrcode.QRCode(
        version=1,
        box_size=10,
        border=5,
    )

    qr.add_data(url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")

    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()


def generate_guest_qr(guest_qr_token: str) -> str:
    """
    Generate a base64 PNG QR code for guest check-in path.
    """
    frontend_base_url = os.getenv("FRONTEND_BASE_URL", "http://localhost:3000").rstrip("/")
    url = f"{frontend_base_url}/checkin/{guest_qr_token}"

    qr = qrcode.QRCode(
        version=1,
        box_size=10,
        border=5,
    )

    qr.add_data(url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")

    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()

