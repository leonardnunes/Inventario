import qrcode
import io
import base64

def gerar_qr_code_base64(url_data):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=6,
        border=2,
    )
    qr.add_data(url_data)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")

    buffer = io.BytesIO()
    qr_img.save(buffer, format='PNG')
    return base64.b64encode(buffer.getvalue()).decode()