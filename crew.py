import os
from crewai import Agent, Task, Crew, Process, LLM
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv

# Erstellen des Output-Verzeichnisses, falls es nicht existiert

os.environ["CREWAI_TELEMETRY_ENABLED"] = "false"
if not os.path.exists("output"):
    os.makedirs("output")

load_dotenv()

gemini_api_key = os.getenv("GOOGLE_API_KEY")

if not gemini_api_key:
    raise ValueError("GOOGLE_API_KEY environment variable not set. Please set it in your .env file.")

# Konfiguration des LLM: Gemini 1.5 Flash
# Stellen Sie sicher, dass Ihr Google API Key in den Umgebungsvariablen gesetzt ist.
# z.B. os.environ["GOOGLE_API_KEY"] = "DEIN_API_KEY"
llm = LLM(
    model="gemini/gemini-2.5-flash",
    api_key=gemini_api_key,
    providers=["google"]
)

#================================================================================
# 1. Definition der Agenten
#================================================================================

manager = Agent(
    role="Crew-Manager",
    goal="Koordiniert alle Spezialagenten, plant den Ablauf und stellt sicher, dass am Ende ein validierter Markdown-GitHub-Issue vorliegt.",
    backstory="Erfahrener Agile Coach, vertraut mit Scrum-Flows und AI-Orchestration. Priorisiert Effizienz, Qualität und Risikominimierung.",
    allow_delegation=True,
    llm=llm,
    max_iter=3,
    verbose=True
)

product_owner = Agent(
    role="Product Owner",
    goal="Wandelt Rohtext-Anforderungen in ein StorySkeleton-JSON mit title, as_a, i_want, so_that.",
    backstory="Stellt die Business-Perspektive sicher und achtet auf verständliche Sprache ohne Fachjargon.",
    allow_delegation=False,
    llm=llm,
    max_iter=2,
    verbose=True
)

story_architect = Agent(
    role="Story Architect",
    goal="Erstellt die vollständige User Story inkl. Gherkin-Akzeptanzkriterien und vollständiger Definition of Done.",
    backstory="Senior Requirements Engineer mit Fokus auf klare, testbare Akzeptanzkriterien.",
    allow_delegation=False,
    llm=llm,
    verbose=True
)

sprint_planner = Agent(
    role="Sprint Planner",
    goal="Zerlegt die Story in Sub-Tasks, weist Story-Points zu und erstellt eine Ready-for-Dev-Checkliste.",
    backstory="Erfahrung in Scrum-Poker, Aufwandsschätzung und Task-Breakdown.",
    allow_delegation=False,
    llm=llm,
    verbose=True
)

qa_analyst = Agent(
    role="QA Analyst",
    goal="Prüft Klarheit, Gherkin-Syntax und Ambiguitäten; vergibt Score und Feedback.",
    backstory="Strenger Qualitätsprüfer mit Rubric-Katalog und Gherkin-Lint-Erfahrung.",
    allow_delegation=False,
    llm=llm,
    max_iter=2,
    verbose=True
)

issue_formatter = Agent(
    role="Issue Formatter",
    goal="Rendert den validierten Inhalt als GitHub-Markdown-Issue, bereit zum Copy-Paste.",
    backstory="Markdown-Guru, kennt GitHub-Flavour und Strukturkonventionen für User Stories.",
    allow_delegation=False,
    llm=llm,
    verbose=True
)


#================================================================================
# 2. Definition der Tasks
#================================================================================

# Task für den Product Owner: Extrahiert die Basis-Story aus dem Input.
product_owner_task = Task(
    description=(
        "Analysiere die folgende User-Story-Anforderung und extrahiere die Kernkomponenten. "
        "Formatiere das Ergebnis ausschließlich als JSON-Objekt mit den Schlüsseln 'title', 'as_a', 'i_want' und 'so_that'.\n\n"
        "User-Story-Anforderung:\n"
        "---_---_---\n"
        "{user_story_input}"
        "---_---_---"
    ),
    expected_output="Ein einzelnes JSON-Objekt, das die User Story strukturiert darstellt. Beispiel: {\"title\": \"...\", \"as_a\": \"...\", \"i_want\": \"...\", \"so_that\": \"...\"}",
    agent=product_owner,
    #output_json=True # Stellt sicher, dass der Output als JSON geparst wird
)

# Task für den Story Architect: Baut die Story mit Akzeptanzkriterien aus.
story_architect_task = Task(
    description=(
        "Erweitere das bereitgestellte Story-Skelett um detaillierte Akzeptanzkriterien im Gherkin-Format (Given/When/Then) "
        "und formuliere eine passende 'Definition of Done' (DoD). "
        "Gib das Ergebnis als JSON-Objekt mit den Schlüsseln 'story_markdown', 'acceptance_criteria' und 'definition_of_done' zurück."
    ),
    expected_output="Ein JSON-Objekt, das die formatierte Story, Gherkin-Kriterien und die DoD enthält.",
    context=[product_owner_task], # Nutzt den Output des PO-Tasks
    agent=story_architect,
    #output_json=True
)

# Task für den Sprint Planner: Bricht die Story in technische Tasks herunter.
sprint_planner_task = Task(
    description=(
        "Basierend auf der User Story und den Akzeptanzkriterien, erstelle eine Liste von technischen Sub-Tasks. "
        "Schätze für jeden Task die Komplexität in Story Points (z.B. 1, 2, 3, 5). "
        "Erstelle zusätzlich eine 'Ready for Dev'-Checkliste. "
        "Formatiere das Ergebnis als JSON-Objekt mit den Schlüsseln 'tasks' (eine Liste von Objekten mit 'desc' und 'points') und 'checklist' (eine Liste von Strings)."
    ),
    expected_output="Ein JSON-Objekt mit einer Liste von Sub-Tasks inkl. Story Points und einer Checkliste.",
    context=[story_architect_task], # Nutzt den Output des Architect-Tasks
    agent=sprint_planner,
    #output_json=True
)

# Task für den QA Analyst: Überprüft die bisherigen Ergebnisse auf Qualität.
qa_analyst_task = Task(
    description=(
        "Überprüfe die erstellte User Story, die Akzeptanzkriterien und die Sub-Tasks auf Klarheit, Vollständigkeit und potentielle Widersprüche. "
        "Bewerte die Qualität auf einer Skala von 0-100. Identifiziere alle Probleme und gib an, ob diese 'blocking' für die Entwicklung sind. "
        "Formatiere das Ergebnis als JSON-Objekt mit den Schlüsseln 'score', 'findings' und 'blocking'."
    ),
    expected_output="Ein JSON-Objekt mit einem Qualitätsscore, einer Liste von Findings und einem Blocking-Status.",
    context=[story_architect_task, sprint_planner_task], # Nutzt mehrere vorherige Outputs
    agent=qa_analyst,
    #output_json=True
)


# Task für den Issue Formatter: Erstellt das finale Markdown-Dokument.
issue_formatter_task = Task(
    description=(
        "Kombiniere alle vorherigen Informationen (User Story, Akzeptanzkriterien, Sub-Tasks, DoD) zu einem finalen GitHub-Issue im Markdown-Format. "
        "Stelle sicher, dass die Formatierung exakt den GitHub-Konventionen entspricht und übersichtlich ist. "
        "Füge am Ende einen Vorschlag für passende Labels hinzu."
    ),
    expected_output="Ein einzelner, sauber formatierter Markdown-Textblock, der das gesamte GitHub-Issue darstellt.",
    context=[product_owner_task, story_architect_task, sprint_planner_task, qa_analyst_task], # Nutzt alle relevanten Outputs
    agent=issue_formatter,
    #output_file="output/github_issue.txt" # Speichert das Ergebnis direkt in eine Datei
)


#================================================================================
# 3. Zusammenstellung und Ausführung der Crew
#================================================================================

# Erstellen des Crew-Objekts mit den Agenten und Tasks
github_issue_crew = Crew(
    agents=[manager, product_owner, story_architect, sprint_planner, qa_analyst, issue_formatter],
    tasks=[product_owner_task, story_architect_task, sprint_planner_task, qa_analyst_task, issue_formatter_task],
    process=Process.sequential,  # Die Aufgaben werden nacheinander ausgeführt
    manager_llm=llm, # Der Manager nutzt ebenfalls Gemini
    verbose=True
)

user_story_input = """
As an administrator,
I want the user entity to include a date of birth and occupation field,
so that I can store and view additional personal information about each user.

Acceptance Criteria:

The user model includes a dateOfBirth field (date format, e.g., yyyy-MM-dd).
The user model includes an occupation field (string).
Both fields are displayed when retrieving user details via API.
It is possible to set both fields when creating or updating a user.
"""


result = github_issue_crew.kickoff(inputs={'user_story_input': user_story_input})

def save_output_to_file(filename, content):
    """Speichert den gegebenen Inhalt in der angegebenen Datei."""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"\nInhalt erfolgreich in '{filename}' gespeichert.")
    except Exception as e:
        print(f"\nFehler beim Speichern der Datei: {e}")

save_output_to_file("output/final_kickoff_result1.md", str(result))



print("\n\n##################################################")
print("Crew-Prozess erfolgreich abgeschlossen!")
print(f"Das finale GitHub-Issue wurde in der Datei 'output/github_issue.txt' gespeichert.")
print("##################################################")
print("\nInhalt des erstellten Issues:")
print(result)