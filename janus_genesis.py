# -*- coding: utf-8 -*-

"""
!!! PROJECT JANUS: GENESIS PROTOCOL v7.0 (Dynamic Entropy) !!!

CHANGELOG v7.0:
1. CORE: Removed fixed entropy increment.
2. AI LOGIC: AI now decides 'entropy_shift' based on narrative intensity.
3. UI: Added delta visualization (e.g., ↑0.15 or ↓0.05).
4. SECURITY: Retained v6.0 hardening (Regex JSON, Fallback, .env).
"""

import json
import os
import random
import requests
import textwrap
import time
import sys
import logging
import re
from datetime import datetime

# --- CONFIGURATION ---
STATE_FILE = "janus_world_state.json"
ENV_FILE = ".env"
LOG_FILE = "janus_system.log"

# Setup Logging
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - [%(levelname)s] - %(message)s'
)

# --- SYSTEM PROMPT (UPDATED FOR v7.0) ---
SYSTEM_PROMPT = """
YOU ARE JANUS, the Architect of a Cognitive Sandbox.
Your goal is to guide the Traveler through a surreal world.

--- DYNAMIC ENTROPY RULES ---
You control the chaos level (Entropy) of the simulation.
1. If the scene is SCARY, CHAOTIC, or GLITCHY -> High positive shift (+0.10 to +0.20).
2. If the scene is NEUTRAL or EXPLORATORY -> Low positive shift (+0.01 to +0.05).
3. If the user RESTS, finds STABILITY, or HEALS -> NEGATIVE shift (-0.05 to -0.15).

--- RESPONSE FORMAT (STRICT JSON) ---
{
  "narrative": "Story text...",
  "choices": ["Option 1", "Option 2", "Option 3"],
  "visual_clue": "emoji",
  "artifact_found": { "name": "Item", "ability": "Effect" } OR null,
  "lore_unlocked": "Story fragment" OR null,
  "entropy_shift": 0.05,  <-- REQUIRED: Float between -0.2 and +0.3
  "reasoning": "Why you chose this outcome and entropy shift"
}
"""

# --- SECURITY: ENV LOADER ---
def load_env_variables():
    if not os.path.exists(ENV_FILE): return False
    try:
        with open(ENV_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'): continue
                if '=' in line:
                    k, v = line.split('=', 1)
                    v = v.strip().strip("'").strip('"')
                    os.environ[k] = v
        return True
    except Exception as e:
        logging.error(f"Failed to load .env: {e}")
        return False

def setup_security():
    load_env_variables()
    keys_raw = os.environ.get("GEMINI_API_KEYS")
    if keys_raw:
        return [k.strip() for k in keys_raw.split(',') if k.strip()]
    
    print("\n\033[93m[SECURITY PROTOCOL]\033[0m Configuration not found.")
    new_keys = []
    print("Enter Google Gemini API Keys (one per line, empty line to finish):")
    while True:
        k = input(f"Key #{len(new_keys)+1}: ").strip()
        if not k:
            if new_keys: break
            continue
        new_keys.append(k)
    
    keys_str = ",".join(new_keys)
    with open(ENV_FILE, 'w', encoding='utf-8') as f:
        f.write(f"GEMINI_API_KEYS=\"{keys_str}\"\n")
    os.environ["GEMINI_API_KEYS"] = keys_str
    return new_keys

# --- STABILITY: JSON REPAIR ---
def extract_and_validate_json(text):
    clean_text = text.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(clean_text)
    except json.JSONDecodeError:
        pass
    try:
        match = re.search(r'(\{.*\})', text, re.DOTALL)
        if match: return json.loads(match.group(1))
    except: pass
    logging.warning(f"JSON Parse Failed. Text: {text[:50]}...")
    return None

def get_fallback_response():
    return {
        "narrative": "⚡ [СБОЙ НЕЙРОСВЯЗИ] ⚡\nЭнтропийный шторм нарушил передачу данных. Попробуйте стабилизировать восприятие.",
        "choices": ["Повторить попытку", "Осмотреть помехи"],
        "visual_clue": "⚠️",
        "entropy_shift": 0.05,
        "reasoning": "Fallback Triggered"
    }

# --- ANALYTICS ---
def levenshtein_distance(s1, s2):
    if len(s1) < len(s2): return levenshtein_distance(s2, s1)
    if len(s2) == 0: return len(s1)
    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    return previous_row[-1]

def analyze_user_input(text, state):
    text_words = text.lower().split()
    keywords = {
        "aggressive": ["kill", "break", "hit", "punch", "destroy", "attack", "fight"],
        "anxious": ["hide", "run", "fear", "dark", "help", "scared", "wait"],
        "analytical": ["look", "scan", "read", "why", "examine", "analyze", "check"]
    }
    scores = {"aggressive": 0, "anxious": 0, "analytical": 0}
    for word in text_words:
        for category, k_list in keywords.items():
            for k in k_list:
                if levenshtein_distance(word, k) <= 1:
                    scores[category] += 1
    
    max_cat = max(scores, key=scores.get)
    if scores[max_cat] > 0:
        state.action_history[max_cat] += 1
        return f"{max_cat.capitalize()} (History: {state.action_history[max_cat]})"
    return state.psych_profile

# --- GAME STATE ---
class GameState:
    def __init__(self):
        self.depth = 1
        self.entropy = 0.1
        self.inventory = []
        self.lore = []
        self.last_context = ""
        self.psych_profile = "Neutral"
        self.action_history = {"aggressive": 0, "anxious": 0, "analytical": 0}

    def load(self):
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.__dict__.update(data)
            except Exception as e:
                logging.error(f"Save corruption: {e}")

    def save(self):
        data = self.__dict__.copy()
        data['timestamp'] = datetime.now().isoformat()
        with open(STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

# --- CORE LOGIC ---
def call_gemini(state, user_action, api_keys):
    inv_desc = ", ".join([f"{i['name']} ({i['ability']})" for i in state.inventory]) if state.inventory else "Empty"
    
    prompt = (
        f"{SYSTEM_PROMPT}\n\n"
        f"DATA:\nDepth: {state.depth} | Entropy: {state.entropy:.2f} | Profile: {state.psych_profile}\n"
        f"Inventory: {inv_desc}\nContext: {state.last_context}\n\n"
        f"USER INPUT: \"{user_action}\""
    )

    for attempt in range(3):
        key = random.choice(api_keys)
        # Using 1.5-flash for speed
        model = "gemini-1.5-flash"
        
        try:
            r = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}", 
                json={"contents": [{"parts": [{"text": prompt}]}]}, 
                headers={"Content-Type": "application/json"}, timeout=15
            )
            
            if r.status_code == 200:
                data = r.json()
                if 'candidates' in data:
                    raw_text = data['candidates'][0]['content']['parts'][0]['text']
                    parsed = extract_and_validate_json(raw_text)
                    if parsed: return parsed
            elif r.status_code == 429:
                logging.warning("Rate Limit.")
            
        except Exception as e:
            logging.error(f"Connection Error: {e}")
        
        time.sleep(2 ** (attempt + 1))

    return get_fallback_response()

# --- UI HELPERS ---
def format_entropy_delta(shift):
    if shift > 0: return f"\033[91m(↑{shift:.2f})\033[0m" # Red arrow up
    if shift < 0: return f"\033[92m(↓{abs(shift):.2f})\033[0m" # Green arrow down
    return "\033[90m(-)\033[0m"

# --- MAIN ---
def main():
    os.system('cls' if os.name == 'nt' else 'clear')
    print("\033[96m" + """
    ╔═══════════════════════════════════════╗
    ║   J A N U S   G E N E S I S   v7.0    ║
    ║   Dynamic Entropy Edition             ║
    ╚═══════════════════════════════════════╝
    """ + "\033[0m")
    
    api_keys = setup_security()
    state = GameState()
    state.load()
    
    if state.depth == 1 and not state.last_context:
        state.last_context = "Вы входите в систему. Уровень энтропии стабилен. Пока что."

    last_shift = 0.0

    while True:
        # UI
        color = "\033[92m" if state.entropy < 0.3 else ("\033[93m" if state.entropy < 0.7 else "\033[91m")
        delta_str = format_entropy_delta(last_shift)
        
        print("\n" + "─"*40)
        print(f"{color}[DEPTH: {state.depth} | ENTROPY: {state.entropy:.2f} {delta_str} | PSYCH: {state.psych_profile}]\033[0m")
        
        user_input = input("\n\033[93m> \033[0m").strip() or "wait"
        
        if user_input.lower() in ["exit", "quit"]:
            state.save()
            print("Сессия завершена.")
            break
            
        state.psych_profile = analyze_user_input(user_input, state)
        print("\033[90m(Neuro-link processing...)\033[0m", end="\r")
        
        resp = call_gemini(state, user_input, api_keys)
        
        # Output
        vis = resp.get('visual_clue', '●')
        nar = resp.get('narrative', 'System Offline')
        
        print(f"\n{vis} \033[97m{textwrap.fill(nar, width=70)}\033[0m\n")
        
        if resp.get('artifact_found'):
            art = resp['artifact_found']
            print(f"\033[92m[!] ARTIFACT: {art['name']} ({art['ability']})\033[0m")
            state.inventory.append(art)
            
        if resp.get('lore_unlocked'):
            print(f"\033[95m[?] LORE: {resp['lore_unlocked']}\033[0m")
            state.lore.append(resp['lore_unlocked'])
            state.depth += 1
            
        for i, c in enumerate(resp.get('choices', []), 1):
            print(f"{i}. {c}")
        
        # Apply Dynamic Entropy
        last_shift = resp.get('entropy_shift', 0.01)
        state.entropy += last_shift
        # Clamp entropy to reasonable bounds (0.0 to 1.5)
        state.entropy = max(0.0, min(1.5, state.entropy))
        
        state.last_context = nar
        state.save()

if __name__ == "__main__":
    main()
