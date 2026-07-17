import os
import re
import subprocess
# हम मुख्य OpenAI लाइब्रेरी का ही इस्तेमाल करेंगे
from openai import OpenAI

# Commands ke known prefixes — fallback whitelist filter ke liye
KNOWN_COMMAND_PREFIXES = (
    'pip', 'pip3', 'npm', 'yarn', 'pnpm', 'python', 'python3',
    'conda', 'docker', 'poetry', 'go', 'cargo', 'brew', 'apt',
    'apt-get', 'sudo', 'export', 'set', 'source', 'virtualenv',
    'mkdir', 'touch', 'node', 'npx', 'bundle', 'gem', 'composer',
    'dotnet', 'mvn', 'gradle'
)


def scan_repository():
    """Scans the current folder for setup configuration files."""
    important_files = {}
    target_files = ['package.json', 'requirements.txt', 'Dockerfile', '.env.example', 'README.md']

    print("🔍 Scanning current directory for blueprints...")
    for filename in os.listdir('.'):
        if filename in target_files:
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    important_files[filename] = f.read(2000)
            except Exception as e:
                print(f"⚠️ Could not read {filename}: {e}")

    return important_files


def ask_local_ai_for_commands(repo_blueprint):
    """Bypasses online API keys completely and uses local Ollama engine via OpenAI SDK."""
    if not repo_blueprint:
        print("❌ No standard setup files found in this directory!")
        return None

    context = ""
    for filename, content in repo_blueprint.items():
        context += f"\n--- FILE: {filename} ---\n{content}\n"

    # Strict delimiter-based instruction — ye parsing ko deterministic banata hai
    system_instruction = (
        "You are RepoPilot, an elite autonomous DevOps engineer tool. "
        "Analyze the project files provided. Determine the environment requirements. "
        "CRITICAL: Respond with ONLY a block wrapped exactly like this, nothing before or after it:\n"
        "<<<COMMANDS>>>\n"
        "command1\n"
        "command2\n"
        "<<<END>>>\n"
        "Write exactly ONE terminal command per line inside that block, one for EACH individual "
        "package or dependency. Do NOT combine multiple packages into a single install command. "
        "Do NOT include explanations, markdown, numbering, or bullets — ONLY raw executable commands "
        "between the markers."
    )

    print("🦙 Connecting to Free Local Ollama Engine via OpenAI Blueprint...")
    try:
        # यहाँ पर मुख्य जादू है:
        # base_url को हम लोकल कंप्यूटर (localhost) पर सेट कर रहे हैं और api_key में कुछ भी डमी नाम लिख सकते हैं।
        local_client = OpenAI(
            base_url="http://localhost:11434/v1",
            api_key="ollama-free-hackathon"
        )

        response = local_client.chat.completions.create(
            model="llama3",  # यह आपके लोकल डाउनलोड किए गए मॉडल का नाम है
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": f"Here are my project files:\n{context}"}
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"❌ Connection Failed. Please make sure the Ollama app is running in your taskbar! Error: {e}")
        return None


def looks_like_command(line):
    """Heuristic fallback check: kya ye line actually ek terminal command jaisi dikhti hai?"""
    if not line:
        return False
    # Sentences aksar punctuation pe end hoti hain
    if line.endswith(('.', ':', '!', '?')):
        return False
    first_word = line.split()[0].lower() if line.split() else ""
    return first_word in KNOWN_COMMAND_PREFIXES


def extract_commands_block(commands_text):
    """Primary extraction: delimiter markers ke beech ka content nikalta hai."""
    match = re.search(r"<<<COMMANDS>>>(.*?)<<<END>>>", commands_text, re.DOTALL)
    if match:
        return match.group(1).strip().split('\n')
    # Fallback: agar model delimiter bhool gaya, to poore text pe line-by-line filtering try karo
    print("⚠️ Delimiter markers nahi mile — fallback filtering use kar rahe hain.")
    return commands_text.strip().split('\n')


def execute_commands(commands_text):
    """Executes the generated instructions directly in the local terminal, filtering non-commands."""
    if not commands_text:
        return

    raw_lines = extract_commands_block(commands_text)
    commands = []

    for line in raw_lines:
        clean_line = line.strip()
        if not clean_line:
            continue

        # Skip conversational text
        if (clean_line.lower().startswith("here is") or
                clean_line.lower().startswith("step") or
                "dependencies:" in clean_line.lower() or
                clean_line.startswith("```")):
            continue

        # Skip navigation commands since we are already inside the folder!
        if (clean_line.lower().startswith("cd ") or
                clean_line.lower().startswith("git clone") or
                "ollama run" in clean_line.lower()):
            continue

        # Clean up accidental numbering or bullets remaining on valid command lines
        if ". " in clean_line[:5]:
            clean_line = clean_line.split(". ", 1)[1]
        if clean_line.startswith("- ") or clean_line.startswith("* "):
            clean_line = clean_line[2:]

        clean_line = clean_line.strip()

        # Whitelist safety net — sirf tabhi add karo jab command jaisa lage
        if looks_like_command(clean_line):
            commands.append(clean_line)
        else:
            print(f"⚠️ Skipped (not a command): {clean_line}")

    if not commands:
        print("❌ No executable terminal commands were detected after filtering.")
        return

    print("\n📋 --- LOCAL AI GENERATED SETUP STEPS ---")
    for i, cmd in enumerate(commands, 1):
        print(f"Command {i}: {cmd}")

    confirm = input("\n🚀 Do you want RepoPilot to execute these commands automatically? (yes/no): ")
    if confirm.lower() in ['yes', 'y']:
        for cmd in commands:
            print(f"\n🏃 Running: {cmd}")
            try:
                subprocess.run(cmd, shell=True, check=True)
            except subprocess.CalledProcessError:
                print(f"❌ Command failed: {cmd}")
                break
    else:
        print("🛑 Execution cancelled by user.")


if __name__ == "__main__":
    blueprint = scan_repository()
    instructions = ask_local_ai_for_commands(blueprint)
    execute_commands(instructions)