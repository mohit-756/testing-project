import re

# We will remove the unused variable definitions
def fix_file(filename, to_remove):
    with open(filename, 'r') as f:
        content = f.read()

    for term in to_remove:
        content = re.sub(rf'const {term} =[^;]+;\n?', '', content)

    with open(filename, 'w') as f:
        f.write(content)

fix_file('interview-frontend/src/pages/HRCandidateDetailPage.jsx', ['parsedResume', 'availableJds', 'hasValidSkills', 'isRawResumeText'])
fix_file('interview-frontend/src/pages/CandidateDashboardPage.jsx', ['e'])
