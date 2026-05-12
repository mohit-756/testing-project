from database import engine
from sqlalchemy import text

with engine.connect() as conn:
    # Update candidate with test LinkedIn and GitHub URLs
    conn.execute(text("""
        UPDATE candidates
        SET linkedin_url = 'https://linkedin.com/in/testcandidate',
            github_url = 'https://github.com/testcandidate'
        WHERE candidate_uid = 'CAND-20260423-E46589'
    """))
    conn.commit()
    print("Updated candidate with test LinkedIn/GitHub URLs")

    # Verify
    result = conn.execute(text("""
        SELECT id, name, candidate_uid, linkedin_url, github_url
        FROM candidates
        WHERE candidate_uid = 'CAND-20260423-E46589'
    """))
    c = result.fetchone()
    if c:
        print(f"Verified: {c[1]} ({c[2]})")
        print(f"  LinkedIn: {c[3]}")
        print(f"  GitHub: {c[4]}")