from flask import Flask, render_template, request, jsonify
import cv2
import google.generativeai as genai
from PIL import Image
import base64
import pandas as pd
import os
from io import BytesIO

app = Flask(__name__)

# Configure Gemini
genai.configure(api_key="AIzaSyDnzVfNSeH_SPS4VIKPTcNcjg8fMSva0q8")
model = genai.GenerativeModel("models/gemini-2.0-flash-exp")

EXCEL_FILE = "extracted_labels.xlsx"
if not os.path.exists(EXCEL_FILE):
    df = pd.DataFrame(columns=["BCCD Name", "Branch", "Product Description", "Product Sr No", "Date of Purchase"])
    df.to_excel(EXCEL_FILE, index=False)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/extract', methods=['POST'])
def extract_text():
    try:
        file = request.files['image']
        img = Image.open(file.stream)

        prompt = """Extract the following fields from this label image:
        BCCD Name, Branch, Product Description, Product Sr No, Date of Purchase.
        Return only key-value pairs in plain text."""
        
        response = model.generate_content([prompt, img])
        extracted_text = response.text

        # parse key-value pairs
        data_dict = {}
        for line in extracted_text.splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                data_dict[key.strip()] = value.strip()

        # Save to Excel
        new_data = pd.DataFrame([data_dict])
        old_data = pd.read_excel(EXCEL_FILE)
        updated = pd.concat([old_data, new_data], ignore_index=True)
        updated.to_excel(EXCEL_FILE, index=False)

        return jsonify({"status": "success", "data": data_dict})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

if __name__ == '__main__':
    app.run(debug=True)
