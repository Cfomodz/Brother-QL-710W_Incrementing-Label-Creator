from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from brother_ql.conversion import convert
from brother_ql.backends.helpers import send
from brother_ql.raster import BrotherQLRaster
import datetime
import json
import os
from PIL import Image, ImageDraw, ImageFont
from barcode import Code128
from barcode.writer import ImageWriter

app = Flask(__name__)
CORS(app)  # Enable CORS

# Persistent counter storage
COUNTER_FILE = 'counters.json'

# Printer settings
PRINTER_IP = '10.0.0.13'  # Replace with your printer's IP
PRINTER_MODEL = 'QL-700'  # QL-710W uses the QL-700 driver
LABEL_SIZE = '62'  # For 2.4 inch continuous roll (62mm width)

# Add a variable to track the most recent label type
MOST_RECENT_LABEL_TYPE = None

def load_counters():
    if os.path.exists(COUNTER_FILE):
        with open(COUNTER_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_counters(counters):
    with open(COUNTER_FILE, 'w') as f:
        json.dump(counters, f)

counters = load_counters()

def generate_barcode_data(label_type, number):
    today = datetime.datetime.now().strftime("%m%d%Y")  # MMDDYYYY format
    type_code = f"{hash(label_type) % 100:02d}"  # 2-digit type code
    padded_number = f"{number:04d}"  # 4-digit number with leading zeros
    return f"{today}{type_code}{padded_number}"

def print_label(label_type, number):
    today = datetime.datetime.now().strftime("%m/%d/%Y")
    barcode_data = generate_barcode_data(label_type, number)
    barcode = Code128(barcode_data, writer=ImageWriter())
    barcode_image_path = "barcode.png"
    barcode.save(barcode_image_path.split('.')[0])
    # Load the barcode image
    barcode_image = Image.open(barcode_image_path)

    # # Calculate barcode dimensions with proper aspect ratio
    # barcode_max_width = 696 - 20  # Fixed width for QL-700
    # barcode_aspect_ratio = barcode_image.height / barcode_image.width
    # barcode_width = barcode_max_width
    # barcode_height = int(barcode_width * barcode_aspect_ratio)
    
    # # Resize the barcode image first to maintain aspect ratio
    # barcode_image = barcode_image.resize(
    #     (barcode_width, barcode_height),
    #     getattr(Image, 'Resampling', Image).LANCZOS
    # )

    qlr = BrotherQLRaster(PRINTER_MODEL)
    
    try:
        font = ImageFont.truetype("arial.ttf", 60)
        bold_font = ImageFont.truetype("arialbd.ttf", 60)
    except IOError:
        font = ImageFont.load_default()
        bold_font = ImageFont.load_default()

    main_text = label_type
    emphasized_text = f" # {number}"
    image_width = 696  # Fixed width for QL-700
    
    # Calculate image height based on barcode and text
    # image_height = max(173, barcode_height + 50)  # Ensure minimum height and space for barcode
    image_height = 280 + 173
    background_color = 1

    image = Image.new('1', (image_width, image_height), background_color)
    draw = ImageDraw.Draw(image)
    
    # Set initial text positions
    text_x = (image_width - font.getlength(main_text + emphasized_text)) // 2
    text_y = 20

    # Draw the main part of the product name
    draw.text((text_x, text_y), main_text, font=font, fill="black")

    # Calculate the width of the main text to position the emphasized text
    main_text_width = font.getlength(main_text)

    # Draw the emphasized part of the product name
    draw.text((text_x + main_text_width, text_y), emphasized_text, font=bold_font, fill="black")

    # Calculate date position
    date_text = today
    date_x = (image_width - font.getlength(date_text)) // 2
    date_y = text_y + max(font.getbbox(main_text)[3], bold_font.getbbox(emphasized_text)[3]) + 20

    # Draw the date
    draw.text((date_x, date_y), date_text, font=font, fill="black")

    # Calculate barcode position
    barcode_x = (image_width - barcode_image.width) // 2
    barcode_y = date_y + font.getbbox(date_text)[3] + 20

    # Paste the barcode image onto the label
    image.paste(barcode_image, (barcode_x, barcode_y))

    # Save the final image
    date_string = today.replace('/','')
    image.save(f"{label_type}_{date_string}_product_label_{number}.png")
    
    instructions = convert(
        qlr=qlr,
        images=[image],
        label=LABEL_SIZE,
        cut=True,
    )

    try:
        send(
            instructions=instructions,
            printer_identifier=f'tcp://{PRINTER_IP}',
            blocking=True
        )
    except Exception as e:
        print(f"Print error: {e}")

@app.route('/print', methods=['POST'])
def handle_print():
    global MOST_RECENT_LABEL_TYPE
    print("Received request:", request.json)  # Log the request
    data = request.json
    label_type = data.get('label_type', MOST_RECENT_LABEL_TYPE or 'Coin').strip()
    
    # Update the most recent label type
    MOST_RECENT_LABEL_TYPE = label_type
    
    if label_type not in counters:
        counters[label_type] = 0
    counters[label_type] += 1
    save_counters(counters)
    
    print_label(label_type, counters[label_type])
    return jsonify({
        "status": "success",
        "label_type": label_type,
        "number": counters[label_type]
    })

@app.route('/clear_counters', methods=['POST'])
def clear_counters():
    data = request.json
    label_type = data.get('label_type', 'all').strip().lower()
    
    if label_type == 'all':
        counters.clear()
    elif label_type in counters:
        del counters[label_type]
    else:
        return jsonify({
            "status": "error",
            "message": f"Label type '{label_type}' not found"
        }), 404
    
    save_counters(counters)
    return jsonify({
        "status": "success",
        "cleared": label_type,
        "counters": counters
    })

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)