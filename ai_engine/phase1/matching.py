import re
import logging
from threading import Lock

from typing import Any

logger = logging.getLogger(__name__)

# --- Safe Dependency Imports ---
SEMANTIC_SEARCH_ENABLED = True
try:
    from sentence_transformers import SentenceTransformer
    from sklearn.metrics.pairwise import cosine_similarity
except ImportError:
    logger.warning("Lite Mode: sentence-transformers or scikit-learn not found. Falling back to keyword matching.")
    SEMANTIC_SEARCH_ENABLED = False

_MODEL: Any | None = None
_MODEL_LOCK = Lock()


def _get_model() -> Any | None:
    global _MODEL
    if not SEMANTIC_SEARCH_ENABLED:
        return None
    if _MODEL is not None:
        return _MODEL

    with _MODEL_LOCK:
        if _MODEL is None:
            try:
                _MODEL = SentenceTransformer("all-MiniLM-L6-v2")
            except Exception as exc:
                logger.error(f"Failed to load SentenceTransformer: {exc}")
                return None
    return _MODEL


# --------------------------------------------------
# TEXT EXTRACTION
# --------------------------------------------------
def extract_text_from_file(file_path):
    if not file_path:
        return ""
    try:
        # Convert to string if it's a Path object
        file_path = str(file_path)
        
        if file_path.endswith(".pdf"):
            # Use PyMuPDF (fitz) for robust PDF extraction
            try:
                import fitz  # PyMuPDF
                doc = fitz.open(file_path)
                text = "\n".join(page.get_text("text") for page in doc)
                text = re.sub(r'\n{3,}', '\n\n', text)  # Collapse excessive breaks
                text = re.sub(r'[\x00-\x1F\x7F]+', '', text)  # Remove control chars
                return text
            except Exception as e:
                # fallback to PyPDF2 if fitz fails
                try:
                    import PyPDF2
                    with open(file_path, "rb") as f:
                        reader = PyPDF2.PdfReader(f)
                        text = "\n".join(page.extract_text() or '' for page in reader.pages)
                        text = re.sub(r'\n{3,}', '\n\n', text)
                        text = re.sub(r'[\x00-\x1F\x7F]+', '', text)
                        return text
                except Exception as e2:
                    return ""

        elif file_path.endswith(".docx"):
            try:
                from docx import Document
                doc = Document(file_path)
                text = "\n".join(para.text for para in doc.paragraphs if para.text.strip())
                text = re.sub(r'\n{3,}', '\n\n', text)
                text = re.sub(r'[\x00-\x1F\x7F]+', '', text)
                return text
            except Exception as e:
                return ""

        elif file_path.endswith(".txt"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    text = f.read()
                    return text
            except Exception:
                return ""
    except Exception as e:
        logger.error(f"extract_text_from_file failed for {file_path}: {e}")
        return ""

    return ""


# --------------------------------------------------
# AUTO SKILL EXTRACTION FROM JD
# --------------------------------------------------
def extract_skills_from_jd(jd_path):
    jd_text = extract_text_from_file(jd_path).lower()

    TECH_SKILLS = [
        "python", "java", "c++", "c#", "javascript", "typescript",
        "react", "angular", "vue", "node", "django", "flask",
        "spring boot", "sql", "mysql", "postgresql", "mongodb",
        "machine learning", "deep learning", "nlp",
        "tensorflow", "pytorch",
        "aws", "azure", "gcp",
        "docker", "kubernetes",
        "git", "linux",
        "power bi", "tableau",
        "html", "css",
        "data analysis", "data science"
    ]

    return [skill for skill in TECH_SKILLS if skill in jd_text]


# --------------------------------------------------
# SEMANTIC MATCH SCORE
# --------------------------------------------------
def calculate_semantic_score(jd_text, resume_text):
    if not (jd_text or "").strip() or not (resume_text or "").strip():
        return 0.0

    if not SEMANTIC_SEARCH_ENABLED:
        # Fallback to Jaccard-like word overlap for "lite" mode
        jd_words = set(re.findall(r'\w+', jd_text.lower()))
        res_words = set(re.findall(r'\w+', resume_text.lower()))
        if not jd_words: return 0.0
        overlap = jd_words.intersection(res_words)
        return float(len(overlap) / len(jd_words))

    model = _get_model()
    if model is None:
        return 0.0
        
    try:
        jd_embedding = model.encode(jd_text)
        resume_embedding = model.encode(resume_text)

        similarity = cosine_similarity(
            [jd_embedding],
            [resume_embedding]
        )[0][0]

        return float(similarity)
    except Exception as exc:
        logger.error(f"Semantic scoring error: {exc}")
        return 0.0


# --------------------------------------------------
# SKILL MATCHING
# --------------------------------------------------
def calculate_skill_score(skill_scores_dict, resume_text):
    total_score = 0
    max_score = sum(skill_scores_dict.values())

    resume_text_lower = resume_text.lower()
    matched_skills = []

    for skill, score in skill_scores_dict.items():
        if skill.lower() in resume_text_lower:
            total_score += score
            matched_skills.append(skill)

    if max_score == 0:
        return 0, []

    normalized = total_score / max_score
    return normalized, matched_skills


# --------------------------------------------------
# EDUCATION EXTRACTION
# --------------------------------------------------
def extract_education(text):
    text = text.lower()

    education_map = {
        "phd": ["phd", "doctorate"],
        "master": ["master", "m.tech", "msc", "mba", "mca"],
        "bachelor": ["bachelor", "b.tech", "bsc", "be", "bca"]
    }

    for level, keywords in education_map.items():
        for keyword in keywords:
            if keyword in text:
                return level

    return None


def extract_education_llm(text, max_chars=3000):
    """LLM-based education extraction with fallback to regex."""
    text_sample = text[:max_chars]
    try:
        from services.llm.client import get_client, llm_model
        client = get_client()
        if client:
            prompt = f"""Extract the highest education level from this resume. Return JSON:
{{"education": "phd" | "master" | "bachelor" | "diploma" | "high_school" | null}}

Resume excerpt: {text_sample}"""
            resp = client.create(model=llm_model(), messages=[{"role": "user", "content": prompt}], temperature=0.1, max_tokens=100)
            import json
            result = json.loads(resp.choices[0].message.content)
            return result.get("education")
    except Exception:
        pass
    return extract_education(text)


# --------------------------------------------------
# EXPERIENCE EXTRACTION
# --------------------------------------------------
def extract_experience(text):
    text = text.lower()
    matches = re.findall(r'(\d+)\s*(?:years|year|yrs|yr)', text)

    if matches:
        return max([int(m) for m in matches])

    return 0


def extract_experience_llm(text, max_chars=3000):
    """LLM-based experience extraction with fallback to regex."""
    text_sample = text[:max_chars]
    try:
        from services.llm.client import get_client, llm_model
        client = get_client()
        if client:
            prompt = f"""Extract total years of work experience from this resume. Return JSON:
{{"experience_years": number}}

Resume excerpt: {text_sample}"""
            resp = client.create(model=llm_model(), messages=[{"role": "user", "content": prompt}], temperature=0.1, max_tokens=100)
            import json
            result = json.loads(resp.choices[0].message.content)
            years = result.get("experience_years")
            if years and isinstance(years, (int, float)) and years > 0:
                return int(years)
    except Exception:
        pass
    return extract_experience(text)


# --------------------------------------------------
# ACADEMIC PERCENTAGE EXTRACTION (FINAL ROBUST VERSION)
# --------------------------------------------------
def extract_academic_percentages(text):
    text = text.lower()
    text = re.sub(r"\s+", " ", text)  # normalize spaces

    academic_data = {
        "10th": None,
        "intermediate": None,
        "engineering": None
    }

    # -------------------------
    # 10th Detection
    # -------------------------
    tenth = re.search(r"(x boards|10th|ssc).*?(\d{2,3}(?:\.\d+)?)\s*%", text)
    if tenth:
        academic_data["10th"] = float(tenth.group(2))

    # -------------------------
    # Intermediate Detection
    # -------------------------
    inter = re.search(r"(xii boards|12th|intermediate|hsc).*?(\d{2,3}(?:\.\d+)?)\s*%", text)
    if inter:
        academic_data["intermediate"] = float(inter.group(2))

    # ------------------------------------------------
    # Engineering Detection
    # ------------------------------------------------
    eng_percent = re.search(
        r"(engineering|b\.?tech|b\.?e|bachelor).*?(\d{2,3}(?:\.\d+)?)\s*%",
        text
    )

    if eng_percent:
        academic_data["engineering"] = float(eng_percent.group(2))
        return academic_data

    cgpa_match = re.search(r"cgpa\s*[:\-]?\s*(\d+(?:\.\d+)?)", text)
    if cgpa_match:
        cgpa = float(cgpa_match.group(1))
        if cgpa <= 10:
            academic_data["engineering"] = round((cgpa / 10) * 100, 2)
        else:
            academic_data["engineering"] = cgpa
        return academic_data

    gpa_match = re.search(r"(\d+(?:\.\d+)?)\s*(cgpa|gpa)", text)
    if gpa_match:
        gpa = float(gpa_match.group(1))
        if gpa <= 10:
            academic_data["engineering"] = round((gpa / 10) * 100, 2)
        else:
            academic_data["engineering"] = gpa

    return academic_data


# --------------------------------------------------
# FINAL AI SCORING ENGINE
# --------------------------------------------------
def final_score(
    jd_path,
    resume_path,
    skill_scores_dict,
    education_requirement=None,
    experience_requirement=0
):
    jd_text = extract_text_from_file(jd_path)
    resume_text = extract_text_from_file(resume_path)

    academic_percentages = extract_academic_percentages(resume_text)
    semantic_score = calculate_semantic_score(jd_text, resume_text)
    skill_score, matched_skills = calculate_skill_score(skill_scores_dict, resume_text)

    candidate_education = extract_education(resume_text)
    education_score = 1.0
    education_reason = "Education requirement satisfied."

    if education_requirement:
        req = education_requirement.lower()
        resume_edu = (candidate_education or "").lower()
        bachelor_keywords = ["bachelor", "b.tech", "btech", "b.e", "be", "bsc", "bca"]
        master_keywords = ["master", "m.tech", "mtech", "m.e", "me", "msc", "mca"]
        matched = False
        if req in bachelor_keywords:
            matched = any(word in resume_edu for word in bachelor_keywords)
        elif req in master_keywords:
            matched = any(word in resume_edu for word in master_keywords)
        else:
            matched = req in resume_edu
        if not matched:
            education_score = 0.0
            education_reason = f"Required {education_requirement}, found {candidate_education or 'None'}"

    candidate_experience = extract_experience(resume_text)
    experience_score = 1.0
    experience_reason = "Experience requirement satisfied."
    if experience_requirement:
        if candidate_experience < experience_requirement:
            experience_score = 0.0
            experience_reason = f"Required {experience_requirement} years, found {candidate_experience}"

    percentage_score = 1.0
    percentage_reason = "Academic percentage criteria satisfied."
    for level, value in academic_percentages.items():
        if value is not None and value < 60:
            percentage_score = 0.0
            percentage_reason = f"{level} below 60%"
            break

    final = (
        semantic_score * 0.30 +
        skill_score * 0.25 +
        education_score * 0.15 +
        experience_score * 0.15 +
        percentage_score * 0.15
    )

    final_percentage = round(final * 100, 2)
    explanation = {
        "semantic_score": round(semantic_score * 100, 2),
        "skill_score": round(skill_score * 100, 2),
        "matched_skills": matched_skills,
        "education_reason": education_reason,
        "experience_reason": experience_reason,
        "total_experience_detected": candidate_experience,
        "academic_percentages": academic_percentages,
        "percentage_reason": percentage_reason,
        "analysis_mode": "lite (keyword)" if not SEMANTIC_SEARCH_ENABLED else "pro (semantic)"
    }

    return final_percentage, explanation
