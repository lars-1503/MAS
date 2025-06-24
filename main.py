import os
from crewai import Agent, Task, Crew, Process # Process importiert
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv

load_dotenv()

# API Key (sollte als GOOGLE_API_KEY in .env stehen, nicht GEMINI_API_KEY)
gemini_key = os.getenv("GEMINI_API_KEY") # <<< WICHTIG: MEISTENS IST ES GOOGLE_API_KEY
print(gemini_key)

if not gemini_key:
    raise ValueError("GOOGLE_API_KEY environment variable not set. Please set it in your .env file.")


# Gemini-LLM (es ist das LLM, nicht ein Tool in diesem Kontext)
gemini_llm_model = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash", # Empfohlen: stabile Version
    api_key=gemini_key,
    temperature=0.2,
    verbose=True # Hilfreich zum Debuggen der LLM-Interaktionen
)

# Developer-Agent
developer = Agent(
    name="Developer",
    role="Software Engineer", # Eine klarere Rolle hilft dem LLM
    goal="Generate functional and syntactically correct Python code based on user stories.",
    backstory="You are an expert Python developer, known for writing clean, efficient, and robust code.",
    llm=gemini_llm_model, # <<< WICHTIG: HIER WIRD DAS LLM ZUGEWIESEN
    verbose=True,
    allow_delegation=False # Der Developer soll selbst coden
)

# Reviewer-Agent
reviewer = Agent(
    name="Reviewer",
    role="Senior Code Reviewer", # Eine klarere Rolle
    goal="Review generated Python code for functionality, best practices, and potential errors.",
    backstory="You are a meticulous and experienced code reviewer. Your eye for detail ensures high-quality code.",
    llm=gemini_llm_model, # <<< WICHTIG: HIER WIRD DAS LLM ZUGEWIESEN
    verbose=True,
    allow_delegation=False # Der Reviewer soll selbst reviewen
)

def process_user_story(user_story):
    # Task 1: Code generieren
    dev_task = Task(
        description=f"Schreibe vollständigen, funktionalen Python-Code für die folgende User Story: {user_story}. "
                    "Der Code sollte nur das Python-Code-Snippet enthalten, umschlossen von drei Backticks (```python ... ```). "
                    "Füge keine zusätzlichen Erklärungen oder Kommentare außerhalb der Code-Blöcke hinzu.",
        expected_output="Ein vollständiges, lauffähiges Python-Code-Snippet, umschlossen von ```python ... ```.",
        agent=developer
    )

    # Task 2: Code reviewen
    review_task = Task(
        description="Prüfe den folgenden Python-Code auf Syntaxfehler, logische Fehler, "
                    "potenzielle Laufzeitprobleme und die Einhaltung von Best Practices. "
                    "Gib präzise Verbesserungsvorschläge, falls Fehler gefunden werden. "
                    "Wenn der Code syntaktisch korrekt ist, funktional aussieht und der User Story entspricht, "
                    "antworte nur mit 'Code ist bereit zur Implementierung.'. "
                    "Analysiere diesen Code:\n\n{dev_task_output}", # <<< PLATZHALTER FÜR DEN VORHERIGEN OUTPUT
        expected_output="Ein detaillierter Bericht über Code-Probleme mit Verbesserungsvorschlägen, "
                        "oder die Bestätigung 'Code ist bereit zur Implementierung.' wenn alles in Ordnung ist.",
        agent=reviewer,
        context=[dev_task] # <<< KONTEXTÜBERGABE HIER
    )

    # Crew zusammenstellen
    crew = Crew(
        agents=[developer, reviewer],
        tasks=[dev_task, review_task],
        verbose=True, # Gibt mehr Details über den Crew-Lauf aus
        process=Process.sequential # Definiert den sequentiellen Ablauf
    )

    # Crew ausführen
    results = crew.kickoff()
    print("==== Ergebnisse der Crew ====")
    print(results)
    print("\n")

if __name__ == "__main__":
    while True:
        user_story = input("Bitte User Story eingeben (oder 'exit' zum Beenden):\n> ")
        if user_story.strip().lower() == 'exit':
            break
        process_user_story(user_story)