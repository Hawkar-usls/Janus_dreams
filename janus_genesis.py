# -*- coding: utf-8 -*-

"""
!!! PROJECT JANUS: GENESIS PROTOCOL v5.0 (Junior Dev Edition) !!!

CHANGELOG v5.0:
1. AI: Added Few-Shot prompting & Action History Feedback Loop.
2. ANALYTICS: Added Fuzzy Matching (Levenshtein) for keyword detection.
3. MECHANICS: Artifacts now have active abilities.
4. SYSTEM: Exponential Backoff for API calls & File Logging.
5. UI: Dynamic Entropy Status Bar (Green -> Red).
"""

import json
import os
import random
import requests
import textwrap
import time
import sys
import logging
from datetime import datetime

# --- CONFIGURATION ---
STATE_FILE = "janus_world_state.json"
KEYS_FILE = "janus_keys.json"
LOG_FILE = "janus_log.txt"

# Настройка логирования
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# --- SYSTEM PROMPT (ENHANCED) ---
# Добавлены Few-Shot примеры и Chain-of-Thought
SYSTEM_PROMPT = """
YOU ARE JANUS, the Architect of a Cognitive Sandbox.
Your goal is to guide the Traveler through a surreal world based on their subconscious.

--- CHAIN OF THOUGHT GUIDANCE ---
1. ANALYZE: First, consider the user's input and their current psych profile.
2. EVALUATE: Is the user attacking? Exploring? Scared?
3. GENERATE: Create a narrative that reflects the current Entropy level.

--- FEW-SHOT EXAMPLES ---
Input: "I smash the mirror with a rock." (Aggressive)
Response Tone: Dark, resistant. The world fights back. "The mirror screams as it shatters..."

Input: "I look closely at the symbols." (Analytical)
Response Tone: Mysterious, detailed. " The symbols shift, revealing a mathematical formula..."

--- INSTRUCTIONS ---
1. ADAPT: Use the provided 'Action History' to subtlely shift the narrative style.
2. ENTROPY: 
   - Low (0.0-0.3): Realistic.
   - High (0.7+): Abstract, glitchy, non-Euclidean.
3. LOOT: 
   - Rarely provide 'artifact_found' (Object with Ability).
   - Rarely provide 'lore_unlocked' (Story fragment).

--- JSON RESPONSE FORMAT ---
Strictly return JSON:
{
  "narrative": "Story text...",
  "choices": ["Option 1", "Option 2", "Option 3"],
  "visual_clue": "emoji",
  "artifact_found": { "name": "Item Name", "ability": "Short description of use" } OR null,
  "lore_unlocked": "Story text" OR null,
  "reasoning": "Brief explanation of why you chose this response"
}
"""

# --- UTILS: LEVENSHTEIN DISTANCE ---
def levenshtein_distance(s1, s2):
    """Вычисляет дистанцию редактирования для нечеткого поиска."""
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)
    
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

def is_fuzzy_match(word, target, tolerance=1):
    return levenshtein_distance(word, target) <= tolerance

# --- KEY MANAGEMENT ---
def get_api_keys():
    if os.path.exists(KEYS_FILE):
        try:
            with open(KEYS_FILE, 'r', encoding='utf-8') as f:
                keys = json.load(f)
                if keys and isinstance(keys, list): return keys
        except: pass

    print("\n\033[93m[SETUP]\033[0m Enter Google Gemini API Keys (one per line, empty line to finish):")
    new_keys = []
    while True:
        k = input(f"Key #{len(new_keys)+1}: ").strip()
        if not k: 
            if new_keys: break
            continue
        new_keys.append(k)
    
    with open(KEYS_FILE, 'w', encoding='utf-8') as f:
        json.dump(new_keys, f)
    return new_keys

# --- GAME STATE ---
class GameState:
    def __init__(self):
        self.depth = 1
        self.entropy = 0.1
        self.inventory = [] # List of dicts {name, ability}
        self.lore = []
        self.last_context = ""
        self.psych_profile = "Neutral"
        # Feedback Loop Data
        self.action_history = {"aggressive": 0, "anxious": 0, "analytical": 0}

    def load(self):
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.depth = data.get('depth', 1)
                    self.entropy = data.get('entropy', 0.1)
                    self.inventory = data.get('inventory', [])
                    self.lore = data.get('lore', [])
                    self.last_context = data.get('last_context', "")
                    self.psych_profile = data.get('psych_profile', "Neutral")
                    self.action_history = data.get('action_history', {"aggressive": 0, "anxious": 0, "analytical": 0})
            except Exception as e:
                logging.error(f"Save load failed: {e}")

    def save(self):
        data = {
            "depth": self.depth,
            "entropy": self.entropy,
            "inventory": self.inventory,
            "lore": self.lore,
            "last_context": self.last_context,
            "psych_profile": self.psych_profile,
            "action_history": self.action_history,
            "timestamp": datetime.now().isoformat()
        }
        with open(STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

# --- ANALYTICS ENGINE ---
def analyze_user_input(text, state):
    """
    Анализ с нечетким поиском и весами.
    Обновляет статистику action_history.
    """
    text_words = text.lower().split()
    
    # Словари с весами (для простоты вес везде 1, можно усложнить)
    keywords = {
        "aggressive": ["kill", "break", "hit", "punch", "destroy", "attack", "fight", "убить", "ударить", "сломать", "бить"],
        "anxious": ["hide", "run", "fear", "dark", "help", "scared", "wait", "бежать", "прятаться", "страх", "помощь"],
        "analytical": ["look", "scan", "read", "why", "examine", "analyze", "check", "осмотреть", "читать", "почему", "анализ"]
    }

    scores = {"aggressive": 0, "anxious": 0, "analytical": 0}

    for word in text_words:
        for category, k_list in keywords.items():
            for k in k_list:
                if is_fuzzy_match(word, k, tolerance=1):
                    scores[category] += 1
    
    # Определяем победителя
    max_cat = max(scores, key=scores.get)
    if scores[max_cat] > 0:
        state.action_history[max_cat] += 1
        return f"{max_cat.capitalize()} (History: {state.action_history[max_cat]})"
    
    return state.psych_profile # Возвращаем старый, если нет совпадений

# --- API HANDLER (WITH BACKOFF) ---
def call_gemini(state, user_action, api_keys):
    inv_desc = ", ".join([f"{i['name']} ({i['ability']})" for i in state.inventory]) if state.inventory else "Empty"
    
    # Формируем тренд поведения для промпта
    top_habit = max(state.action_history, key=state.action_history.get)
    
    prompt = (
        f"{SYSTEM_PROMPT}\n\n"
        f"--- WORLD STATE ---\n"
        f"Depth: {state.depth}\n"
        f"Entropy: {state.entropy:.2f}\n"
        f"Player Inventory: {inv_desc}\n"
        f"Dominant Trait: {top_habit.upper()} (User tends to be {top_habit})\n"
        f"Current Psych Profile: {state.psych_profile}\n"
        f"Previous Context: {state.last_context}\n\n"
        f"--- USER INPUT ---\n"
        f"User Action: \"{user_action}\"\n"
    )

    # Retry Logic with Exponential Backoff
    for attempt in range(3):
        key = random.choice(api_keys)
        # Using gemini-1.5-flash as default for speed/cost, fallback to pro if needed
        model = "gemini-1.5-flash" 
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
        
        try:
            response = requests.post(
                url, 
                json={"contents": [{"parts": [{"text": prompt}]}]}, 
                headers={"Content-Type": "application/json"}, 
                timeout=15
            )
            
            # Log the attempt
            logging.info(f"API Call to {model} | Status: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                if 'candidates' in data:
                    raw = data['candidates'][0]['content']['parts'][0]['text']
                    clean = raw.replace("```json", "").replace("```", "").strip()
                    return json.loads(clean)
            elif response.status_code == 429:
                logging.warning("Rate limit hit. Retrying...")
            else:
                logging.error(f"API Error: {response.text}")

        except Exception as e:
            logging.error(f"Network Exception: {e}")
        
        # Exponential backoff: 2s, 4s, 8s
        wait_time = 2 ** (attempt + 1)
        print(f"\033[90m...connection unstable, retrying in {wait_time}s...\033[0m", end="\r")
        time.sleep(wait_time)

    return None

def print_slow(text):
    sys.stdout.write(text)
    sys.stdout.flush()
    print()

def get_status_color(entropy):
    if entropy < 0.3: return "\033[92m" # Green
    if entropy < 0.7: return "\033[93m" # Yellow
    return "\033[91m" # Red

# --- MAIN LOOP ---
def main():
    os.system('cls' if os.name == 'nt' else 'clear')
    print("\033[96m" + """
    ╔═══════════════════════════════════════╗
    ║   J A N U S   G E N E S I S   v5.0    ║
    ║   Junior Dev Refactor Edition         ║
    ╚═══════════════════════════════════════╝
    """ + "\033[0m")
    
    keys = get_api_keys()
    state = GameState()
    state.load()
    
    if state.depth == 1 and not state.last_context:
        intro = "Система перезагружена. Версия ядра обновлена. Вы чувствуете новый уровень осознанности."
        state.last_context = intro
        print(intro)

    while True:
        # UI: Status Bar with Dynamic Color
        color = get_status_color(state.entropy)
        print("\n" + "─"*40)
        print(f"{color}[DEPTH: {state.depth} | ENTROPY: {state.entropy:.2f} | PSYCH: {state.psych_profile}]\033[0m")
        
        user_input = input("\n\033[93m> \033[0m").strip()
        
        if not user_input: user_input = "wait"
        if user_input.lower() in ["exit", "save"]:
            state.save()
            print("Saved.")
            break
        
        # 1. Analyze (Update Profile)
        state.psych_profile = analyze_user_input(user_input, state)
        
        print("\033[90m(Thinking...)\033[0m", end="\r")
        
        # 2. Call AI
        resp = call_gemini(state, user_input, keys)
        
        if resp:
            # 3. Parse Response
            vis = resp.get('visual_clue', '●')
            nar = resp.get('narrative', '...')
            # Для отладки можно выводить reasoning, если нужно:
            # if 'reasoning' in resp: print(f"\033[90mDEBUG: {resp['reasoning']}\033[0m")

            print(f"\n{vis} \033[97m{textwrap.fill(nar, width=70)}\033[0m\n")
            
            # Artifacts (Active Ability)
            art = resp.get('artifact_found')
            if art and isinstance(art, dict):
                print(f"\033[92m[!] ARTIFACT: {art.get('name')} - {art.get('ability')}\033[0m")
                state.inventory.append(art)
            
            # Lore & Progression
            lore = resp.get('lore_unlocked')
            if lore:
                print(f"\033[95m[?] LORE UNLOCKED: {lore}\033[0m")
                state.lore.append(lore)
                state.depth += 1 # Progression tied to Lore
                print(f"\033[96m>>> DEPTH INCREASED TO {state.depth}\033[0m")
            
            # Choices
            choices = resp.get('choices', [])
            print("\033[94mPossibilities:\033[0m")
            for i, c in enumerate(choices, 1):
                print(f"{i}. {c}")
            
            # Fixed Entropy Increment
            state.entropy += 0.02 
            state.last_context = nar
            state.save()
        else:
            print("\033[91mCRITICAL ERROR: Neuro-link severed. Check logs.\033[0m")

if __name__ == "__main__":
    main()
