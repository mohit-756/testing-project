import { apiClient } from "../services/api";

const S3_UPLOAD_API = import.meta.env.VITE_S3_UPLOAD_API;
const API_BASE = import.meta.env.VITE_API_BASE_URL || "/api";

const ALLOWED_FILE_TYPES = [
  "application/pdf",
  "application/msword",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
];

const MAX_FILE_SIZE = 5 * 1024 * 1024;

const isProduction = API_BASE.includes("cloudfront.net") || API_BASE.includes("elasticbeanstalk.com") || API_BASE.includes("aws.amazon.com");

export const uploadFileToS3 = async (file, onProgress) => {
  if (!file) throw new Error("No file provided");

  if (file.size > MAX_FILE_SIZE) {
    throw new Error("File exceeds 5MB limit");
  }

  if (!ALLOWED_FILE_TYPES.includes(file.type)) {
    throw new Error("Invalid file type");
  }

  if (isProduction && S3_UPLOAD_API) {
    console.log("[UPLOAD] Production mode - using S3 upload");
    const res = await fetch(
      `${S3_UPLOAD_API}?fileName=${encodeURIComponent(file.name)}&fileType=${encodeURIComponent(file.type)}`
    );

    if (!res.ok) throw new Error("Failed to get upload URL");

    const { uploadUrl, fileUrl } = await res.json();

    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open("PUT", uploadUrl, true);
      xhr.setRequestHeader("Content-Type", file.type);

      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          resolve(fileUrl);
        } else {
          reject(new Error(`Upload failed: ${xhr.status} - ${xhr.statusText}`));
        }
      };

      xhr.onerror = () => reject(new Error("Upload failed - network error"));

      if (onProgress) {
        xhr.upload.onprogress = (e) => {
          if (e.lengthComputable) {
            onProgress(Math.round((e.loaded / e.total) * 100));
          }
        };
      }

      xhr.send(file);
    });
  }

  console.log("[UPLOAD] Development/Local mode - using direct backend upload");
  const formData = new FormData();
  formData.append("resume", file);
  
  const response = await apiClient.post("/candidate/upload-resume", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return response.uploaded_resume || response.candidate?.resume_path || "uploaded";
};