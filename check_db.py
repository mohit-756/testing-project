from database import engine
from sqlalchemy import text

with engine.connect() as conn:
    result = conn.execute(text("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = 'candidates'
        AND column_name IN ('linkedin_url', 'github_url')
    """))
    columns = result.fetchall()
    if columns:
        print('Columns found:')
        for col in columns:
            print(f'  - {col[0]}: {col[1]}')
    else:
        print('ERROR: linkedin_url and github_url columns not found!')

    result2 = conn.execute(text("""
        SELECT id, name, linkedin_url, github_url
        FROM candidates
        LIMIT 3
    """))
    candidates = result2.fetchall()
    print('\nCandidate sample data:')
    for c in candidates:
        print(f'  ID: {c[0]}, Name: {c[1]}, LinkedIn: {c[2]}, GitHub: {c[3]}')