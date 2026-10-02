import json
from openai import OpenAI
from .config import OPENROUTER_API_KEY

def generate_script(topic, duration_minutes=2, language="English"):
    if not OPENROUTER_API_KEY or OPENROUTER_API_KEY == "your_openrouter_api_key_here":
        raise ValueError("Please set your OPENROUTER_API_KEY in the .env file")
        
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=OPENROUTER_API_KEY,
    )
    
    prompt = f"""
    You are an expert YouTube scriptwriter and director. 
    Create a highly engaging script for a video about: "{topic}"
    The video MUST be approximately {duration_minutes} minutes long.
    
    CRITICAL INSTRUCTION FOR LANGUAGE:
    The "voiceover" and "key_term" MUST be written entirely in {language}.
    However, the "search_query" MUST remain in English so the stock video API can find results.
    
    CRITICAL INSTRUCTION FOR PACING:
    To keep the video highly engaging, the visuals must change rapidly.
    Therefore, break the script down into very short segments. 
    Each segment should contain ONLY 1 short sentence (about 4 to 6 seconds of spoken time).
    To reach the {duration_minutes} minute mark, you MUST write enough segments (roughly {duration_minutes * 10} to {duration_minutes * 12} segments).
    
    CRITICAL INSTRUCTION FOR MOOD:
    For each segment, assign a "mood" that describes the emotional tone of that sentence.
    Choose from EXACTLY these options: "dramatic", "epic", "calm", "intense", "informative".
    The mood will control which visual effects are applied to that segment.
    Use variety — don't make every segment the same mood.
    
    Output the script as a raw JSON object with the following schema:
    {{
        "title": "A catchy YouTube title",
        "description": "An engaging YouTube description",
        "tags": ["tag1", "tag2"],
        "segments": [
            {{
                "voiceover": "1 short sentence the narrator will read.",
                "search_query": "A simple 1-3 word search term to find a matching stock video on Pexels.",
                "key_term": "1 to 2 words representing the main subject of this sentence.",
                "mood": "dramatic"
            }}
        ]
    }}
    
    IMPORTANT: Provide ONLY the raw JSON string. Do not include markdown code blocks like ```json.
    """
    
    print(f"Generating script for topic: {topic} (Target: {duration_minutes} min)...")
    response = client.chat.completions.create(
        model="openai/gpt-4o-mini",
        max_tokens=2000,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )
    
    response_text = response.choices[0].message.content
    try:
        data = json.loads(response_text.strip())
        return data
    except json.JSONDecodeError:
        # Fallback to cleaning up the response if the LLM adds markdown
        text = response_text.replace("```json", "").replace("```", "").strip()
        return json.loads(text)

if __name__ == "__main__":
    # Test
    print(generate_script("The History of the Internet"))
