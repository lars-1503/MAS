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
    name="Extractor",
    role="Fachanalyst",
    goal="Analysiere die User Story und extrahiere die wichtigsten fachlichen Anforderungen als kurze, klare Liste.",
    backstory="Hat langjährige Erfahrung in der Anforderungsanalyse und filtert effizient die Kernpunkte aus komplexen User Stories.",
    llm=gemini_llm_model
)

developer = Agent(
    name="Developer",
    role="Softwareentwickler",
    goal="Erstelle anhand der extrahierten Anforderungen sauberen Programmcode.",
    backstory="Ist erfahren im Programmieren und setzt Anforderungen schnell in lauffähigen Code um.",
    llm=gemini_llm_model
)

def run_crew_with_retry(crew, retries=3, wait_sec=5):
    for i in range(retries):
        try:
            return crew.kickoff()
        except Exception as e:
            print(f"Fehler: {e}")
            if i < retries - 1:
                print(f"Nochmals versuchen in {wait_sec} Sekunden...")
                time.sleep(wait_sec)
    raise RuntimeError("Maximale Anzahl Versuche erreicht.")

def save_code_to_file(user_story, result):
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    if "html" in user_story.lower():
        filename = f"output_{timestamp}.html"
    elif "python" in user_story.lower():
        filename = f"output_{timestamp}.py"
    elif "sql" in user_story.lower():
        filename = f"output_{timestamp}.sql"
    else:
        match = re.search(r"```(\w+)", str(result))
        if match:
            extension = match.group(1)
            filename = f"output_{timestamp}.{extension}"
        else:
            filename = f"output_{timestamp}.txt"
    filename = os.path.join("output", filename)
    with open(filename, "w", encoding="utf-8") as f:
        f.write(str(result))
    print(f"Ergebnis gespeichert als {filename}")

def process_user_story(user_story):

    extract_task = Task(
        description=f"Extrahiere die wichtigsten fachlichen Anforderungen aus folgender User Story und fasse sie in einer kurzen, nummerierten Liste zusammen:\n\n{user_story}",
        expected_output="Eine kurze, nummerierte Liste mit den wichtigsten Anforderungen in jeweils einem Satz.",
        agent=extractor
    )

    dev_task = Task(
        description="Schreibe auf Basis der extrahierten Anforderungen sauberen, kommentierten Programmcode, der die Funktionalität abbildet.",
        expected_output="Lauffähiger, kommentierter Programmcode, der die gewünschten Anforderungen umsetzt.",
        agent=developer,
        context=[extract_task]
    )

    crew = Crew(
        agents=[extractor, developer],
        tasks=[extract_task, dev_task]
    )

    result = run_crew_with_retry(crew)
    save_code_to_file(user_story, result)
    print("\n==== CrewAI Ergebnis ====\n")
    print(result)

if __name__ == "__main__":
    #user_story = input("Bitte gib eine User Story ein:\n> ")
    user_story = ("Als Nutzer möchte ich auf der Webseite ein einfaches Anmeldefeld haben, "
                  "in das ich meinen Benutzernamen und mein Passwort eingeben kann, damit "
                  "ich mich anmelden kann. Die Umsetzung soll ausschließlich mit einfachem "
                  "HTML erfolgen, ohne Frameworks und ohne CSS.")
    process_user_story(user_story)

#