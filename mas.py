import os
from crewai import Agent, Task, Crew, Process, LLM # Process importiert für crew
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv
import time
import re
import datetime

load_dotenv()

gemini_api_key = os.getenv("GOOGLE_API_KEY")

if not gemini_api_key:
    raise ValueError("GOOGLE_API_KEY environment variable not set. Please set it in your .env file.")

gemini_llm_model = LLM(
    #model="gemini/gemini-2.5-flash-preview-04-17",
    model="gemini/gemini-2.5-flash-lite-preview-06-17",
    api_key=gemini_api_key,
    providers=["google"]
)

extractor = Agent(
    name="Requirement Analyst",
    role="Requirement Engineer",
    goal="Analysiere User Stories und extrahiere Rolle, Funktion und Nutzen. Identifiziere Unklarheiten und fehlende Informationen.",
    backstory="Ist ein erfahrener Requirement Engineer mit ausgeprägtem Gespür für fehlende Anforderungen und Lücken in Spezifikationen.",
    llm=gemini_llm_model
)

context_enricher = Agent(
    name="Context Enricher",
    role="Softwarearchitekt",
    goal="Füge auf Basis von Projektdokumentation und Architekturvorgaben relevante technische und geschäftliche Kontextinformationen hinzu.",
    backstory="Kennt das Projekt in- und auswendig und ergänzt Anforderungen mit relevantem Kontext.",
    llm=gemini_llm_model
)

solution_architect = Agent(
    name="Solution Architect",
    role="Full-Stack-Entwickler",
    goal="Erstelle auf Basis der Anforderung und des Kontexts eine technische Lösung mit API-Endpunkten, Datenmodellen und Bibliotheken.",
    backstory="Hat jahrelange Erfahrung in der Umsetzung technischer Anforderungen und in der Entwicklung robuster Architekturen.",
    llm=gemini_llm_model
)

qa_engineer = Agent(
    name="QA Engineer",
    role="Testingenieur",
    goal="Formuliere testbare Akzeptanzkriterien im Given-When-Then Format, die Erfolg und Fehlerfälle abdecken.",
    backstory="Spezialisiert auf QA und automatisierte Tests, stellt sicher, dass Anforderungen testbar und präzise sind.",
    llm=gemini_llm_model
)

prompt_synthesizer = Agent(
    name="Prompt Synthesizer",
    role="Prompt Engineer",
    goal="Füge alle gesammelten Informationen zu einem klaren und effektiven Prompt in Markdown-Struktur zusammen.",
    backstory="Hat Erfahrung mit der Optimierung von Prompts für LLMs, um bestmöglichen Code zu generieren.",
    llm=gemini_llm_model
)

def run_crew_with_retry(crew, retries=3, wait_sec=5):
    print("Starte CrewAI Prozess...")
    for i in range(retries):
        try:
            return crew.kickoff()
        except Exception as e:
            print(f"Fehler: {e}")
            if i < retries - 1:
                print(f"Nochmals versuchen in {wait_sec} Sekunden...")
                time.sleep(wait_sec)
    raise RuntimeError("Maximale Anzahl Versuche erreicht.")
print("CrewAI Agenten und Tasks initialisiert.")

def save_code_to_file(user_story, result):
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    filename = f"prompt_output_{timestamp}.txt"
    filename = os.path.join("output", filename)
    with open(filename, "w", encoding="utf-8") as f:
        f.write(str(result))
    print(f"Ergebnis gespeichert als {filename}")

def process_user_story(user_story):

    extract_task = Task(
        description=f"Du bist ein erfahrener Requirement Engineer. Analysiere die folgende User Story. Extrahiere die Rolle, die gewünschte Funktion und den Nutzen. Identifiziere offensichtliche Unklarheiten und fehlende Informationen, die für die technische Umsetzung notwendig sind:\n\n{user_story}",
        expected_output="Strukturierte Liste mit Rolle, Funktion, Nutzen und offenen Fragen.",
        agent=extractor
    )

    context_task = Task(
        description="Du bist ein Softwarearchitekt mit Zugriff auf alle Projektdokumentationen. Ergänze die analysierte User Story mit relevanten technischen und geschäftlichen Kontextinformationen.",
        expected_output="Erweiterte Version der Anforderung mit Kontextinformationen wie Tech-Stack, bestehende Architektur, Konventionen.",
        agent=context_enricher,
        context=[extract_task]
    )

    architecture_task = Task(
        description="Du bist ein erfahrener Full-Stack-Entwickler. Entwirf auf Basis der Anforderung und des Kontexts eine technische Lösung mit API-Endpunkten, Datenmodellen und verwendeten Bibliotheken.",
        expected_output="Technische Spezifikation mit klaren API-Endpunkten, Datenmodellen und zu verwendenden Technologien.",
        agent=solution_architect,
        context=[context_task]
    )

    qa_task = Task(
        description="Du bist ein QA-Automatisierungsingenieur. Formuliere auf Basis der technischen Spezifikation testbare Akzeptanzkriterien im BDD-Stil (Given-When-Then). Decke Erfolgs- und Fehlerfälle ab.",
        expected_output="Liste von Akzeptanzkriterien im Given-When-Then-Format.",
        agent=qa_engineer,
        context=[architecture_task]
    )

    prompt_task = Task(
        description=(
            "Du bist ein Prompt Engineer. Formatiere die User Story, den Kontext, die technische Spezifikation und die Akzeptanzkriterien "
            "zu einem einzigen Markdown-Prompt, der an ein Coding-LLM übergeben werden kann. "
            "WICHTIG: Generiere KEINEN Code. Der Prompt soll den Input für ein LLM sein, das daraus später Code generiert. "
            "Füge eine klare Anweisung am Ende hinzu wie: "
            "'Bitte generiere basierend auf diesen Informationen den vollständigen Code.'"
        ),
        expected_output="Ein gut strukturierter Markdown-Prompt ohne Beispielcode oder Klassen, nur Text.",
        agent=prompt_synthesizer,
        context=[extract_task, context_task, architecture_task, qa_task]
    )

    crew = Crew(
        agents=[extractor, context_enricher, solution_architect, qa_engineer, prompt_synthesizer],
        tasks=[extract_task, context_task, architecture_task, qa_task, prompt_task]
    )

    result = run_crew_with_retry(crew)
    final_prompt = result[4].output if isinstance(result, list) and len(result) >= 5 else result
    save_code_to_file(user_story, final_prompt)

if __name__ == "__main__":
    #user_story = input("Bitte gib eine User Story ein:\n> ")
    print("Start")
    user_story = ("Im Rahmen der bestehenden Anwendung soll eine Funktion zur Verwaltung von Produkten eingeführt "
                  "werden. Nutzer sollen die Möglichkeit haben, Produkte anzulegen, anzuzeigen, zu bearbeiten und "
                  "zu löschen (CRUD-Operationen). Jedes Produkt besitzt mindestens die Attribute id, name, preis "
                  "und beschreibung. Die Produktverwaltung wird als eigener REST-Controller mit entsprechenden "
                  "Endpunkten umgesetzt und ist unabhängig von der bestehenden User-CRUD-Funktionalität. Eingaben "
                  "werden validiert, zum Beispiel dürfen Produktnamen nicht leer sein und der Preis darf nicht negativ "
                  "sein. Fehlerhafte Eingaben führen zu einer klaren Fehlermeldung. Zusätzlich werden für alle "
                  "Produkt-Endpunkte Integrationstests erstellt, die sowohl die Funktionalität als auch die Validierung "
                  "abdecken. Eine Dokumentation der Endpunkte rundet die Implementierung ab.")
    print("start process_user_story")
    process_user_story(user_story)
