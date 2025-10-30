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
    "BCCD Name",
    "Branch",
    "Product Description",
    "Product Sr No",
    "Date of Purchase",
    "Complaint No",
    "Spare Part Code",
    "Nature of Defect",
    "Technician Name",
    "Manufactured Date"
]

# Create Excel file if not exists
if not os.path.exists(EXCEL_FILE):
    pd.DataFrame(columns=COLUMNS).to_excel(EXCEL_FILE, index=False)

# ===================== STREAMLIT UI =====================
st.set_page_config(page_title="Label Extractor", layout="wide")

st.markdown("""
<style>
body, .stApp {
    background-color: white !important;
    color: black !important;
}

/* Global text styles */
.stMarkdown, .stText, .stTextInput label, .stSelectbox label, label, p, span {
    color: black !important;
    opacity: 1 !important;
    font-weight: 500 !important;
}

/* Text and select inputs */
.stTextInput input, .stSelectbox div[data-baseweb="select"] {
    background-color: white !important;
    color: black !important;
    border: 1px solid #ccc !important;
}

/* Buttons */
.stButton > button, .stDownloadButton > button {
    background-color: white !important;
    color: black !important;
    border: 1px solid #ccc !important;
    font-weight: 600 !important;
    opacity: 1 !important;
}
.stButton > button:hover, .stDownloadButton > button:hover {
    background-color: #f5f5f5 !important;
}

/* Radio buttons */
.stRadio label, .stRadio div[role="radiogroup"] > label, .stRadio p {
    color: black !important;
}

/* ===== Fix for file uploader visibility ===== */
[data-testid="stFileUploader"] section {
    background-color: #f9f9f9 !important;  /* Light gray background */
    border: 1px dashed #999 !important;
    border-radius: 10px !important;
    padding: 20px !important;
    color: #333 !important;
}
[data-testid="stFileUploader"] section:hover {
    background-color: #f0f0f0 !important;
}
[data-testid="stFileUploader"] div {
    color: #333 !important;
    font-weight: 500 !important;
}
[data-testid="stFileUploader"] button {
    background-color: #ffffff !important;
    color: #000 !important;
    border: 1px solid #888 !important;
    font-weight: 600 !important;
}
[data-testid="stFileUploader"] button:hover {
    background-color: #f2f2f2 !important;
}

/* Upload text contrast */
[data-testid="stFileUploader"] small {
    color: #555 !important;
}
</style>
""", unsafe_allow_html=True)

# ===================== APP TITLE =====================
st.title("NexScan")

col1, col2 = st.columns(2)

# ---- IMAGE INPUT SECTION ----
with col1:
    st.subheader("Capture or Upload Label Image")
    option = st.radio("Choose input method:", [" Capture from Webcam", " Upload Image"])

    picture = None
    if option == " Capture from Webcam":
        picture = st.camera_input("Take a picture using your webcam")
    else:
        uploaded_file = st.file_uploader("Upload an image", type=["jpg", "jpeg", "png"])
        if uploaded_file is not None:
            picture = uploaded_file

    # ---- HANDLE IMAGE INPUT SAFELY ----
    image_path = None
    if picture is not None:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp_file:
            temp_file.write(picture.getbuffer())
            image_path = temp_file.name
    else:
        st.info("Please capture or upload an image to proceed.")

# ---- PROCESS IMAGE ----
if image_path is not None:
    with open(image_path, "rb") as img_file:
        img = Image.open(img_file)
        prompt = """Extract all visible text exactly as it appears in the image.
Do NOT translate, summarize, or interpret.
Return the text exactly in the original language."""
        
        response = model.generate_content([prompt, img])
        extracted_text = response.text.strip() if response.text else "No text detected."
        st.text_area("Extracted Text (Raw):", extracted_text, height=150)

    # ---- AUTO MAP EXTRACTED TEXT TO FIELDS ----
    data_dict = {}
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

with col2:
    st.subheader("Verify and Save Extracted Data")

    # Load spare parts mapping
    try:
        spare_df = pd.read_excel("spare_parts.xlsx")
    except FileNotFoundError:
        spare_df = pd.DataFrame(columns=["Material", "Material Description"])

    spare_part_codes = spare_df["Material"].astype(str).tolist()
    spare_part_dict = dict(zip(spare_df["Material"].astype(str), spare_df["Material Description"].astype(str)))

    # Use unique key for selectbox
    selected_spare = st.selectbox(
        "Spare Part Code",
        options=[""] + spare_part_codes,
        index=spare_part_codes.index(data_dict.get("Spare Part Code", "")) + 1
        if data_dict.get("Spare Part Code", "") in spare_part_codes else 0,
        key="Spare Part Code Select"
    )

    # Sync value back into the field
    data_dict["Spare Part Code"] = selected_spare
    if selected_spare:
        data_dict["Product Description"] = spare_part_dict.get(selected_spare, "")

    # ---- Input fields ----
    inputs = {}
    for col in COLUMNS:
        # skip spare part code because it's handled by dropdown
        if col == "Spare Part Code":
            inputs[col] = data_dict["Spare Part Code"]
        else:
            inputs[col] = st.text_input(col, data_dict.get(col, ""), key=f"{col}_input")

    # ---- SAVE TO EXCEL FUNCTION ----
    def save_to_excel():
        new_data = pd.DataFrame([inputs])
        try:
            old_data = pd.read_excel(EXCEL_FILE)
        except FileNotFoundError:
            old_data = pd.DataFrame(columns=COLUMNS)

        updated = pd.concat([old_data, new_data], ignore_index=True)
        try:
            updated.to_excel(EXCEL_FILE, index=False)
            st.success(f"✅ Data saved to {EXCEL_FILE}")
            st.dataframe(updated.tail(5))
        except PermissionError:
            st.error("❌ Please close the Excel file before saving new entries.")

    if st.button("💾 Save to Excel"):
        save_to_excel()

    # ---- DOWNLOAD BUTTON ----
    if os.path.exists(EXCEL_FILE):
        with open(EXCEL_FILE, "rb") as f:
            st.download_button(
                label="⬇ Download Excel File",
                data=f,
                file_name=EXCEL_FILE,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
