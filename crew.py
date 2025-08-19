import os
import json

os.environ["CREWAI_TELEMETRY_ENABLED"] = "false"  # hard opt-out
os.environ["OTEL_SDK_DISABLED"] = "true"          # disable OpenTelemetry globally

from typing import List, Dict
from crewai import Agent, Task, Crew, Process, LLM
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv
from datetime import date, datetime

timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

# -----------------------------------------------------------------------------
# Environment & output setup
# -----------------------------------------------------------------------------

os.environ["CREWAI_TELEMETRY_ENABLED"] = "false"
if not os.path.exists("output"):
    os.makedirs("output")

load_dotenv()
GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError(
        "GOOGLE_API_KEY environment variable not set. Please set it in your .env file."
    )

# Primary LLM for CrewAI agents (Gemini 2.5 Flash via CrewAI provider spec)
llm = LLM(
    model="gemini/gemini-2.5-flash",
    api_key=GEMINI_API_KEY,
    providers=["google"],
)

# -----------------------------------------------------------------------------
# Helper utilities
# -----------------------------------------------------------------------------

def extract_json(text: str) -> Dict:
    """Robustly extract the first JSON object from a string."""
    try:
        return json.loads(text)
    except Exception:
        # Try to snip the outermost JSON block
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            snippet = text[start : end + 1]
            try:
                return json.loads(snippet)
            except Exception:
                pass
    return {}


def interactive_clarification_round(initial_story: str, max_questions: int = 6) -> str:
    """
    Runs a pre-crew clarification step:
    1) A Clarifier Agent proposes targeted questions as JSON.
    2) We ask the user for answers in the CLI.
    3) We append Q&A to the original input and return the enriched prompt.
    """
    # ---------------------------------------------------------------------
    # Build a minimal one-task crew that proposes clarification questions.
    # ---------------------------------------------------------------------
    clarifier = Agent(
        role="Requirements Clarifier",
        goal=(
            "Identify missing details, ambiguities, or risks in the user story and ask only the most \n"
            "impactful clarification questions. Always work and respond in English."
        ),
        backstory=(
            "Senior Business Analyst with strong requirements engineering background. \n"
            "You are concise and pragmatic. You never add assumptions; you ask. \n"
            "Language policy: Always think and respond in English."
        ),
        allow_delegation=False,
        llm=llm,
        verbose=False,
        max_iter=1,
    )

    clarification_task = Task(
        description=(
            "Analyze the following user story and only if necessary, propose clarification questions.\n"
            "Return STRICT JSON with this shape: {\"questions\": [\"...\"]}.\n"
            f"Limit to at most {max_questions} short, concrete questions.\n\n"
            "User Story:\n"
            "---\n{user_story_input}\n---\n\n"
            "Do not add explanations. If everything is clear, return {\"questions\": []}."
        ),
        expected_output=(
            "A single JSON object with a 'questions' array (possibly empty)."
        ),
        agent=clarifier,
    )

    clarification_crew = Crew(
        agents=[clarifier],
        tasks=[clarification_task],
        process=Process.sequential,
        manager_llm=llm,
        verbose=False,
    )

    result = clarification_crew.kickoff(inputs={"user_story_input": initial_story})
    data = extract_json(str(result)) or {"questions": []}
    questions: List[str] = data.get("questions") or []

    if not questions:
        return initial_story

    print("\n— Clarification needed — Please answer the following:")
    answers: List[Dict[str, str]] = []
    for idx, q in enumerate(questions, start=1):
        print(f"Q{idx}: {q}")
        a = input("Your answer: ").strip()
        answers.append({"question": q, "answer": a})

    clarifications_md = ["\n\nAdditional Clarifications (from interactive Q&A):\n"]
    for pair in answers:
        clarifications_md.append(f"- Q: {pair['question']}\n  A: {pair['answer']}")

    return initial_story + "\n" + "\n".join(clarifications_md)


# -----------------------------------------------------------------------------
# Agent definitions (English-only policy)
# -----------------------------------------------------------------------------

manager = Agent(
    role="Crew Manager",
    goal=(
        "Coordinate all specialist agents, plan the flow, and ensure that the final output is a validated,\n"
        "well-structured GitHub Issue in Markdown. Always produce content in English."
    ),
    backstory=(
        "An experienced Agile Coach familiar with Scrum flows and AI orchestration. \n"
        "You prioritize efficiency, quality, and risk mitigation. \n"
        "Language policy: Always think and respond in English."
    ),
    allow_delegation=True,
    llm=llm,
    max_iter=3,
    verbose=True,
)

product_owner = Agent(
    role="Product Owner",
    goal=(
        "Transform raw requirements into a Story Skeleton JSON with keys: title, as_a, i_want, so_that. \n"
        "Always answer in English."
    ),
    backstory=(
        "Ensures the business perspective and uses clear, jargon-free language. \n"
        "Language policy: Always think and respond in English."
    ),
    allow_delegation=False,
    llm=llm,
    max_iter=2,
    verbose=True,
)

story_architect = Agent(
    role="Story Architect",
    goal=(
        "Create the complete user story with Gherkin acceptance criteria (Given/When/Then) and a comprehensive Definition of Done."
    ),
    backstory=(
        "Senior Requirements Engineer focused on clear, testable acceptance criteria. \n"
        "Language policy: Always think and respond in English."
    ),
    allow_delegation=False,
    llm=llm,
    verbose=True,
)

sprint_planner = Agent(
    role="Sprint Planner",
    goal=(
        "Break down the story into sub-tasks, estimate Story Points, and create a Ready-for-Dev checklist."
    ),
    backstory=(
        "Experienced in Scrum Poker, effort estimation, and task breakdown. \n"
        "Language policy: Always think and respond in English."
    ),
    allow_delegation=False,
    llm=llm,
    verbose=True,
)

qa_analyst = Agent(
    role="QA Analyst",
    goal=(
        "Check clarity, Gherkin syntax, completeness, and ambiguities; assign a quality score and provide feedback."
    ),
    backstory=(
        "Strict quality reviewer with a rubric catalog and Gherkin lint experience. \n"
        "Language policy: Always think and respond in English."
    ),
    allow_delegation=False,
    llm=llm,
    max_iter=2,
    verbose=True,
)

issue_formatter = Agent(
    role="Issue Formatter",
    goal=(
        "Render the validated content as a copy-paste ready GitHub Issue in Markdown with suggested labels."
    ),
    backstory=(
        "Markdown expert, proficient in GitHub Flavored Markdown and common user story structures. \n"
        "Language policy: Always think and respond in English."
    ),
    allow_delegation=False,
    llm=llm,
    verbose=True,
)

# -----------------------------------------------------------------------------
# Task definitions (English-only prompts)
# -----------------------------------------------------------------------------

product_owner_task = Task(
    description=(
        "Analyze the following user story requirement and extract its core components.\n"
        "Output ONLY a JSON object with the keys 'title', 'as_a', 'i_want', 'so_that'.\n\n"
        "User Story Requirement:\n"
        "---\n{user_story_input}\n---"
    ),
    expected_output=(
        "A single JSON object representing the user story skeleton, e.g. {\"title\": \"...\", \"as_a\": \"...\", \"i_want\": \"...\", \"so_that\": \"...\"}"
    ),
    agent=product_owner,
)

story_architect_task = Task(
    description=(
        "Extend the provided story skeleton with detailed Gherkin acceptance criteria (Given/When/Then) and a suitable \n"
        "Definition of Done (DoD). Return a JSON object with keys: 'story_markdown', 'acceptance_criteria', 'definition_of_done'."
    ),
    expected_output=(
        "A JSON object containing the formatted story, acceptance criteria, and DoD."
    ),
    context=[product_owner_task],
    agent=story_architect,
)

sprint_planner_task = Task(
    description=(
        "Based on the user story and acceptance criteria, create a list of technical sub-tasks. For each sub-task, estimate Story Points \n"
        "(e.g., 1, 2, 3, 5). Also provide a 'Ready for Dev' checklist. Output a JSON object with keys: \n"
        "'tasks' (list of objects with 'desc' and 'points') and 'checklist' (list of strings)."
    ),
    expected_output=(
        "A JSON object with sub-tasks including story points and a checklist."
    ),
    context=[story_architect_task],
    agent=sprint_planner,
)

qa_analyst_task = Task(
    description=(
        "Review the created user story, acceptance criteria, and sub-tasks for clarity, completeness, and potential contradictions. \n"
        "Score the overall quality on a 0-100 scale. Identify issues and specify whether each is 'blocking'. \n"
        "Return a JSON object with keys 'score', 'findings', and 'blocking'."
    ),
    expected_output=(
        "A JSON object with a quality score, a list of findings, and a blocking status."
    ),
    context=[story_architect_task, sprint_planner_task],
    agent=qa_analyst,
)

issue_formatter_task = Task(
    description=(
        "Combine all prior information (User Story, Acceptance Criteria, Sub-Tasks, DoD) into a final GitHub Issue in Markdown.\n"
        "Ensure the formatting matches GitHub conventions and is easy to read. Add suggested labels at the end."
    ),
    expected_output=(
        "A single, cleanly formatted Markdown block representing the entire GitHub Issue."
    ),
    context=[product_owner_task, story_architect_task, sprint_planner_task, qa_analyst_task],
    agent=issue_formatter,
    output_file=F"output/github_issue-{timestamp}.md",
)

# -----------------------------------------------------------------------------
# Crew assembly
# -----------------------------------------------------------------------------

github_issue_crew = Crew(
    agents=[
        manager,
        product_owner,
        story_architect,
        sprint_planner,
        qa_analyst,
        issue_formatter,
    ],
    tasks=[
        product_owner_task,
        story_architect_task,
        sprint_planner_task,
        qa_analyst_task,
        issue_formatter_task,
    ],
    process=Process.sequential,
    manager_llm=llm,
    verbose=True,
)

# -----------------------------------------------------------------------------
# Example usage (CLI-friendly)
# -----------------------------------------------------------------------------

def main():
    print("\n=== CrewAI: User Story to GitHub Issue (English-only, with CLI clarifications) ===\n")
    print("Paste your user story below. End input with a single line containing only END.\n")

    # Read multi-line user input (fallback to a default example if nothing is provided)
    lines: List[str] = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line.strip() == "END":
            break
        lines.append(line)

    if lines:
        user_story_input = "\n".join(lines).strip()
    else:
        user_story_input = (
            "As an administrator, I want the user entity to include a date of birth and occupation mandatory field, "
            "so that I can store and view additional personal information about each user.\n\n"
            "Acceptance Criteria:\n"
            "- The user model includes a dateOfBirth field (ISO date, e.g., yyyy-MM-dd).\n"
            "- The user model includes an occupation field (string).\n"
            "- Both fields are displayed when retrieving user details via API.\n"
            "- It is possible to set both fields when creating or updating a user.\n"
        )
        print("(Using default example. Provide your own next time to override.)\n")

    # Interactive clarification phase
    final_input = interactive_clarification_round(user_story_input)

    # Kick off the main crew
    result = github_issue_crew.kickoff(inputs={"user_story_input": final_input})

    # Persist full result as well (in addition to issue_formatter_task's output_file)
    with open(f"output/final_result-{timestamp}.md", "w", encoding="utf-8") as f:
        f.write(str(result))

    print("\n\n##################################################")
    print("Crew process finished successfully!")
    print("Primary issue saved to 'output/github_issue.md'.")
    print("Full run output saved to 'output/final_result.md'.")
    print("##################################################\n")


if __name__ == "__main__":
    main()
