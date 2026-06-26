"""
make_sample_pdf.py
-------------------
One-off helper script - NOT part of the DocShield app itself.

Generates a small sample PDF with clearly fake, made-up facts.
Why made-up facts? Because if Claude answers correctly using THESE
specific invented details (e.g. "DocShield was founded in the made-up
year 2019 by a fictional person"), we know FOR CERTAIN it's reading
the actual document and not just using general knowledge to guess.

Run this once with: python make_sample_pdf.py
It creates: sample_docs/company_handbook.pdf
"""

import os
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

os.makedirs("sample_docs", exist_ok=True)

doc = SimpleDocTemplate("sample_docs/company_handbook.pdf", pagesize=letter)
styles = getSampleStyleSheet()
content = []

title = "Nimbus Cloud Solutions — Employee Handbook (Sample)"
content.append(Paragraph(title, styles["Title"]))
content.append(Spacer(1, 20))

sections = [
    ("Company Overview",
     "Nimbus Cloud Solutions was founded in 2019 by Priya Okafor in Manchester, "
     "England. The company specializes in cloud migration consulting for "
     "mid-sized retail businesses. As of this handbook's writing, Nimbus "
     "employs 47 people across three offices: Manchester, Lisbon, and Nairobi."),

    ("Annual Leave Policy",
     "All full-time employees at Nimbus Cloud Solutions are entitled to 28 days "
     "of paid annual leave per year, in addition to public holidays. Leave "
     "requests must be submitted at least 10 working days in advance through "
     "the internal HR portal, codenamed 'CloudLeave'. Unused leave can carry "
     "over up to a maximum of 5 days into the following year."),

    ("Remote Work Policy",
     "Nimbus operates a hybrid working model. Employees are required to be "
     "in the office a minimum of 2 days per week, with Wednesdays being a "
     "mandatory in-office day company-wide, known internally as 'Nimbus "
     "Wednesday'. Fully remote work requires director-level approval."),

    ("Security Incident Reporting",
     "Any suspected security incident, including phishing attempts or lost "
     "devices, must be reported within 1 hour of discovery to the security "
     "team via the dedicated Slack channel #nimbus-security-alerts. The "
     "current Head of Security is Tomasz Kowalski."),

    ("Expense Reimbursement",
     "Employees can claim expenses up to £150 without prior manager approval. "
     "Expenses above this threshold require written approval before the cost "
     "is incurred. All claims must be submitted within 30 days via the "
     "finance tool 'NimbusExpense'."),
]

for heading, body in sections:
    content.append(Paragraph(heading, styles["Heading2"]))
    content.append(Spacer(1, 6))
    content.append(Paragraph(body, styles["BodyText"]))
    content.append(Spacer(1, 16))

doc.build(content)
print("Created: sample_docs/company_handbook.pdf")