const video = document.getElementById("video");
const canvas = document.getElementById("canvas");
const captureBtn = document.getElementById("captureBtn");
const ctx = canvas.getContext("2d");

// Start webcam
navigator.mediaDevices.getUserMedia({ video: true })
  .then(stream => {
    video.srcObject = stream;
  })
  .catch(err => {
    alert("Camera access denied: " + err);
  });

// Capture and send to Flask
captureBtn.addEventListener("click", async () => {
  ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
  const imageData = canvas.toDataURL("image/jpeg");

  const response = await fetch("/capture", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ image: imageData }),
  });

  const result = await response.json();
  if (result.success) {
    const data = result.data;
    document.getElementById("branch").value = data.get("Branch") || "";
    document.getElementById("bccd_name").value = data.get("BCCD Name") || "";
    document.getElementById("description").value = data.get("Product Description") || "";
    document.getElementById("product_sr").value = data.get("Product Sr No") || "";
    document.getElementById("purchase_date").value = data.get("Date of Purchase") || "";
    document.getElementById("complaint_no").value = data.get("Complaint No") || "";
    document.getElementById("spare_code").value = data.get("Spare Part Code") || "";
    document.getElementById("defect").value = data.get("Nature of Defect") || "";
    document.getElementById("technician").value = data.get("Technician Name") || "";
  } else {
    alert("Error: " + result.error);
  }
});
