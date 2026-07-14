import os
import sys
import subprocess
from openai import OpenAI

# Initialize the OpenAI client (it automatically reads the key you set in step 2)
client = OpenAI()

def scan_repository():
    """Scans the current folder for setup configuration files."""
    important_files = {}
    target_files = ['package.json', 'requirements.txt', 'Dockerfile', '.env.example', 'README.md']
    
    print("🔍 Scanning current directory for setup blueprints...")
    for filename in os.listdir('.'):
        if filename in target_files:
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    # Read the first 2000 characters so we don't break token limits
                    important_files[filename] = f.read(2000)
            except Exception as e:
                print(f"⚠️ Could not read {filename}: {e}")
                
    return important_files

def ask_codex_for_commands(repo_blueprint):
    """Sends the file blueprints to Codex to get a step-by-step setup plan."""
    if not repo_blueprint:
        print("❌ No standard setup files found in this directory!")
        return None

    print("🤖 Sending blueprints to OpenAI Codex...")
    
    # Format the collected file data into a neat text block
    context = ""
    for filename, content in repo_blueprint.items():
        context += f"\n--- FILE: {filename} ---\n{content}\n"

    # Define the precise instructions for the AI
    system_instruction = (
        "You are RepoPilot, an elite autonomous DevOps engineer tool. "
        "Analyze the project files provided. Determine the language and setup requirements. "
        "Provide a clean, bulleted list of the exact terminal commands required to install dependencies "
        "and run this project on the user's current operating system. "
        "Output ONLY the commands, one per line. Do not write introductory or concluding explanations."
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini", # Perfect, low-cost model for hackathon testing
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": f"Here are my project files:\n{context}"}
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"❌ OpenAI API Error: {e}")
        return None

def execute_commands(commands_text):
   def execute_commands(commands_text):
    """Executes commands and automatically uses Codex to fix errors if they occur."""
    if not commands_text:
        return

    print("\n📋 --- CODEX GENERATED SETUP STEPS ---")
    commands = [line.strip() for line in commands_text.split('\n') if line.strip()]
    
    for i, cmd in enumerate(commands, 1):
        print(f"Step {i}: {cmd}")

    confirm = input("\n🚀 Do you want RepoPilot to execute these commands automatically? (yes/no): ")
    if confirm.lower() in ['yes', 'y']:
        for cmd in commands:
            print(f"\n🏃 Running: {cmd}")
            try:
                # Run command and capture output
                subprocess.run(cmd, shell=True, check=True)
            except subprocess.CalledProcessError as e:
                print(f"⚠️ Command failed! Activating Codex Self-Healing Mode...")
                
                # Ask Codex to solve the error
                fix_instruction = f"The terminal command '{cmd}' failed with an error. Provide a clean, alternative terminal command to bypass or fix this error. Output ONLY the raw command."
                try:
                    fix_response = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[{"role": "user", "content": fix_instruction}]
                    )
                    fixed_cmd = fix_response.choices.message.content.strip()
                    print(f"🔧 Codex suggested fix: {fixed_cmd}")
                    
                    # Try running the fixed version
                    print(f"🏃 Running Fix: {fixed_cmd}")
                    subprocess.run(fixed_cmd, shell=True, check=True)
                except Exception as api_err:
                    print(f"❌ Could not auto-heal: {api_err}")
                    break
    else:
        print("🛑 Execution cancelled by user.")

if __name__ == "__main__":
    # 1. Look at the files in the current folder
    blueprint = scan_repository()
    
    # 2. Get instructions from Codex
    instructions = ask_codex_for_commands(blueprint)
    
    # 3. Present and execute commands
    execute_commands(instructions)
