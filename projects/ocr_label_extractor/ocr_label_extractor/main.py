import os
import tempfile
import pandas as pd
from PIL import Image
import google.generativeai as genai
from dotenv import load_dotenv
import streamlit as st

# ===================== SETUP =====================
load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
model = genai.GenerativeModel("models/gemini-2.5-flash")

EXCEL_FILE = "labels_extended.xlsx"
COLUMNS = [
    "BCCD Name", "Branch", "Product Description", "Product Sr No", "Date of Purchase",
    "Complaint No", "Spare Part Code", "Nature of Defect", "Technician Name", "Manufactured Date"
]

# Create Excel file if not exists
if not os.path.exists(EXCEL_FILE):
    pd.DataFrame(columns=COLUMNS).to_excel(EXCEL_FILE, index=False)

# ===================== STREAMLIT CONFIG =====================
st.set_page_config(
    page_title="NexScan Label Extractor",
    layout="wide",
    page_icon="🧾"
)

# ===== Custom CSS =====
st.markdown("""
<style>
body, .stApp {
    background: linear-gradient(135deg, #f8f9ff, #eef2ff);
    font-family: 'Segoe UI', sans-serif;
    color: #1a1a1a;
}

/* Headings */
h1, h2, h3 {
    color: #1a1a1a;
    font-weight: 700;
}

/* Buttons */
.stButton > button {
    background: linear-gradient(90deg, #0052cc, #007bff);
    color: white !important;
    border: none !important;
    border-radius: 8px;
    font-weight: 600;
    padding: 0.5em 1.2em;
    transition: all 0.2s ease-in-out;
}
.stButton > button:hover {
    background: linear-gradient(90deg, #0041a8, #0060e0);
    transform: scale(1.03);
}

/* Inputs */
.stTextInput input {
    border: 1px solid #ccc !important;
    border-radius: 6px;
    background-color: white !important;
    padding: 0.4em !important;
}

/* File uploader */
[data-testid="stFileUploader"] section {
    background-color: #ffffff;
    border: 2px dashed #007bff;
    border-radius: 10px;
    padding: 1.5em;
    color: #333;
}
[data-testid="stFileUploader"] section:hover {
    background-color: #f0f6ff;
}

/* Hide full traceback errors */
.stAlert {
    display: none !important;
}

/* Text area */
textarea {
    border-radius: 8px !important;
    border-color: #ccc !important;
}

/* Subtle divider */
hr {
    border: 0;
    height: 1px;
    background: #ccc;
    margin: 1em 0;
}
</style>
""", unsafe_allow_html=True)

# ===================== APP UI =====================
st.title("🧾 NexScan – Smart Label Extractor")
st.caption("Extract, verify, and save product label details with AI-powered precision.")

col1, col2 = st.columns(2)

# ---- IMAGE INPUT ----
with col1:
    st.subheader("📸 Capture or Upload Label Image")
    option = st.radio("Choose input method:", ["Capture from Webcam", "Upload Image"])
    picture = None

    if option == "Capture from Webcam":
        picture = st.camera_input("Take a picture")
    else:
        uploaded_file = st.file_uploader("Upload an image", type=["jpg", "jpeg", "png"])
        if uploaded_file is not None:
            picture = uploaded_file

    image_path = None
    if picture is not None:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp_file:
            temp_file.write(picture.getbuffer())
            image_path = temp_file.name
    else:
        st.info("Please capture or upload an image to proceed.")

# ---- PROCESS IMAGE ----
extracted_text = ""
data_dict = {}

if image_path is not None:
    try:
        with open(image_path, "rb") as img_file:
            img = Image.open(img_file)
            with st.spinner("🔍 Extracting text from image... Please wait"):
                prompt = """Extract all visible text exactly as it appears in the image.
                Do NOT translate or interpret. Return only the raw text."""
                response = model.generate_content([prompt, img])
                extracted_text = response.text.strip() if response.text else "No text detected."
            st.text_area("📝 Extracted Text:", extracted_text, height=150)
    except Exception:
        st.warning("⚠️ Something went wrong while processing the image. Please try again.")
        extracted_text = ""

# ---- MAP EXTRACTED TEXT ----
if extracted_text:
    lines = [line.strip() for line in extracted_text.splitlines() if line.strip()]
    for col in COLUMNS:
        found_line = next((line for line in lines if col.lower() in line.lower()), None)
        if found_line:
            if ":" in found_line:
                data_dict[col] = found_line.split(":", 1)[1].strip()
            else:
                data_dict[col] = found_line.replace(col, "").strip()
        else:
            data_dict[col] = ""

# ---- RIGHT COLUMN ----
with col2:
    st.subheader("🧮 Verify & Save Extracted Data")

    # Load spare part mapping
    try:
        spare_df = pd.read_excel("spare_parts.xlsx")
    except FileNotFoundError:
        spare_df = pd.DataFrame(columns=["Material", "Material Description"])

    spare_part_codes = spare_df["Material"].astype(str).tolist()
    spare_part_dict = dict(zip(spare_df["Material"].astype(str), spare_df["Material Description"].astype(str)))

    selected_spare = st.selectbox(
        "Spare Part Code",
        options=[""] + spare_part_codes,
        index=spare_part_codes.index(data_dict.get("Spare Part Code", "")) + 1
        if data_dict.get("Spare Part Code", "") in spare_part_codes else 0,
        key="Spare Part Code Select"
    )

    data_dict["Spare Part Code"] = selected_spare
    if selected_spare:
        data_dict["Product Description"] = spare_part_dict.get(selected_spare, "")

    inputs = {}
    for col in COLUMNS:
        if col == "Spare Part Code":
            inputs[col] = data_dict["Spare Part Code"]
        else:
            inputs[col] = st.text_input(col, data_dict.get(col, ""), key=f"{col}_input")

    # ---- SAVE FUNCTION ----
    def save_to_excel():
        try:
            new_data = pd.DataFrame([inputs])
            old_data = pd.read_excel(EXCEL_FILE) if os.path.exists(EXCEL_FILE) else pd.DataFrame(columns=COLUMNS)
            updated = pd.concat([old_data, new_data], ignore_index=True)
            updated.to_excel(EXCEL_FILE, index=False)
            st.success("✅ Data saved successfully!")
            st.dataframe(updated.tail(5))
        except PermissionError:
            st.error("❌ Please close the Excel file before saving.")
        except Exception:
            st.warning("⚠️ Could not save data. Please try again.")

    if st.button("💾 Save to Excel"):
        save_to_excel()

    if os.path.exists(EXCEL_FILE):
        with open(EXCEL_FILE, "rb") as f:
            st.download_button(
                label="⬇ Download Excel File",
                data=f,
                file_name=EXCEL_FILE,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
