# -*- coding: utf-8 -*-

"""
!!! PROJECT JANUS: GENESIS PROTOCOL v6.0 (Hardened Edition) !!!

CHANGELOG v6.0:
1. SECURITY: Migration to .env file (Environment Variables).
2. STABILITY: Regex-based JSON extraction & Fallback mechanisms.
3. CORE: Zero-dependency .env parser included.
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

# --- SYSTEM PROMPT ---
SYSTEM_PROMPT = """
YOU ARE JANUS, the Architect of a Cognitive Sandbox.
Your goal is to guide the Traveler through a surreal world based on their subconscious.

--- RESPONSE FORMAT (STRICT JSON) ---
You MUST return valid JSON. Do not wrap in markdown blocks like ```json ... ```.
{
  "narrative": "Atmospheric description...",
  "choices": ["Action 1", "Action 2", "Action 3"],
  "visual_clue": "emoji",
  "artifact_found": { "name": "Item", "ability": "Effect" } OR null,
  "lore_unlocked": "Story fragment" OR null,
  "reasoning": "Why you chose this outcome"
}

--- RULES ---
1. ADAPT: If User is Aggressive -> World is Hostile. If Curious -> World is Mysterious.
2. ENTROPY: 
   - <0.3: Realistic.
   - >0.7: Nightmare logic, glitches, abstraction.
3. FAIL-SAFE: Keep JSON structure simple to avoid parsing errors.
"""

# --- SECURITY: ENV LOADER ---
def load_env_variables():
    """
    Custom .env parser to avoid external dependencies like python-dotenv.
    Loads variables into os.environ.
    """
    if not os.path.exists(ENV_FILE):
        return False
    
    try:
        with open(ENV_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'): continue
                if '=' in line:
                    k, v = line.split('=', 1)
                    # Clean quotes if present
                    v = v.strip().strip("'").strip('"')
                    os.environ[k] = v
        return True
    except Exception as e:
        logging.error(f"Failed to load .env: {e}")
        return False

def setup_security():
    """Ensures API keys exist in environment or creates .env file."""
    load_env_variables()
    
    # Check if key exists in memory
    keys_raw = os.environ.get("GEMINI_API_KEYS")
    
    if keys_raw:
        return [k.strip() for k in keys_raw.split(',') if k.strip()]
    
    # If not, interactive setup
    print("\n\033[93m[SECURITY PROTOCOL]\033[0m Configuration not found.")
    print("Initializing secure storage (.env)...")
    
    new_keys = []
    print("Enter Google Gemini API Keys (one per line, empty line to finish):")
    while True:
        k = input(f"Key #{len(new_keys)+1}: ").strip()
        if not k:
            if new_keys: break
            continue
        new_keys.append(k)
    
    # Save to .env
    keys_str = ",".join(new_keys)
    try:
        with open(ENV_FILE, 'w', encoding='utf-8') as f:
            f.write(f"# Janus Genesis Configuration\n")
            f.write(f"GEMINI_API_KEYS=\"{keys_str}\"\n")
        print(f"✅ Secure config saved to {ENV_FILE}. Added to os.environ.")
        os.environ["GEMINI_API_KEYS"] = keys_str
        return new_keys
    except Exception as e:
        print(f"❌ Error saving .env: {e}")
        sys.exit(1)

# --- STABILITY: JSON REPAIR ---
def extract_and_validate_json(text):
    """
    Attempts to extract JSON from polluted LLM output using Regex.
    Returns parsed dict or None.
    """
    # 1. Try cleaning markdown wrappers
    clean_text = text.replace("```json", "").replace("```", "").strip()
    
    try:
        return json.loads(clean_text)
    except json.JSONDecodeError:
        pass # Continue to regex strategy

    # 2. Regex search for closest JSON object structure
    try:
        # Look for content between first { and last }
        match = re.search(r'(\{.*\})', text, re.DOTALL)
        if match:
            json_str = match.group(1)
            return json.loads(json_str)
    except:
        pass
        
    logging.warning(f"JSON Parse Failed. Raw text: {text[:50]}...")
    return None

def get_fallback_response():
    """Emergency response if AI fails completely."""
    return {
        "narrative": "⚡ [СБОЙ НЕЙРОСВЯЗИ] ⚡\nРеальность мигает белым шумом. Архитектор не отвечает. Вы чувствуете, как энтропия разрывает пакеты данных. Попробуйте сосредоточиться и восстановить связь.",
        "choices": ["Перезагрузить восприятие (Повторить)", "Осмотреть статические помехи"],
        "visual_clue": "⚠️",
        "reasoning": "Fallback Triggered"
    }

# --- ANALYTICS: FUZZY LOGIC ---
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
        f"DATA:\nDepth: {state.depth} | Entropy: {
