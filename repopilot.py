import os
import sys
import subprocess
# हम मुख्य OpenAI लाइब्रेरी का ही इस्तेमाल करेंगे
from openai import OpenAI

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

    system_instruction = (
        "You are RepoPilot, an elite autonomous DevOps engineer tool. "
        "Analyze the project files provided. Determine the environment requirements. "
        "Provide a clean list of the exact local terminal commands required to install dependencies. "
        "Output ONLY the raw executable commands, one per line. Do not include bullet points (-), "
        "do not include numbers (1., 2.), and do not write markdown blocks like ```bash."
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
            model="llama3", # यह आपके लोकल डाउनलोड किए गए मॉडल का नाम है
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": f"Here are my project files:\n{context}"}
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"❌ Connection Failed. Please make sure the Ollama app is running in your taskbar! Error: {e}")
        return None

def execute_commands(commands_text):
    """Executes the generated instructions directly in the local terminal."""
    if not commands_text:
        return

    print("\n📋 --- LOCAL AI GENERATED SETUP STEPS ---")
    commands = [line.strip() for line in commands_text.split('\n') if line.strip()]
    
    for i, cmd in enumerate(commands, 1):
        print(f"Step {i}: {cmd}")

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

