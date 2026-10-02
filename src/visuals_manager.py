import os
import requests
import json
from openai import OpenAI
from .config import PEXELS_API_KEY, OPENROUTER_API_KEY

def download_video(query, voiceover_text, output_path):
    if not PEXELS_API_KEY or PEXELS_API_KEY == "your_pexels_api_key_here":
        raise ValueError("Please set your PEXELS_API_KEY in the .env file")

    print(f"Searching Pexels for video: {query}...")
    headers = {"Authorization": PEXELS_API_KEY}
    # Fetch 5 videos so the AI has options
    url = f"https://api.pexels.com/videos/search?query={query}&per_page=5&orientation=landscape&size=medium"
    
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    data = response.json()
    
    videos = data.get("videos", [])
    if not videos:
        print(f"No video found for query: {query}. Trying a fallback query...")
        fallback_url = f"https://api.pexels.com/videos/search?query=nature&per_page=1&orientation=landscape&size=medium"
        response = requests.get(fallback_url, headers=headers)
        videos = response.json().get("videos", [])
        if not videos:
            raise ValueError(f"Could not find any fallback videos either.")
            
    best_video = videos[0] # Default to first
    
    # If we have multiple videos, use AI to pick the best one based on the voiceover context
    if len(videos) > 1 and OPENROUTER_API_KEY:
        print("Asking AI to select the best video clip from the top 5 results...")
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=OPENROUTER_API_KEY,
        )
        
        # Build a list of video descriptions from their URLs (Pexels URLs contain descriptive slugs)
        options = []
        for i, v in enumerate(videos):
            # Extract the slug from the URL (e.g. "happy-dog-running-12345" -> "happy dog running")
            slug = v["url"].split("/")[-2].replace("-", " ")
            options.append(f"Option {i}: {slug} (Duration: {v['duration']}s)")
            
        options_text = "\n".join(options)
        
        prompt = f"""
        You are a professional video editor. 
        The narrator is saying this sentence: "{voiceover_text}"
        
        Which of the following stock video clips is the absolute best match for this sentence?
        {options_text}
        
        Respond with ONLY the integer number of the best option (e.g. 0, 1, 2, 3, or 4). Do not include any other text.
        """
        
        try:
            ai_response = client.chat.completions.create(
                model="openai/gpt-4o-mini",
                max_tokens=10,
                messages=[{"role": "user", "content": prompt}]
            )
            choice_str = ai_response.choices[0].message.content.strip()
            # Extract just the number
            import re
            numbers = re.findall(r'\d+', choice_str)
            if numbers:
                choice_idx = int(numbers[0])
                if 0 <= choice_idx < len(videos):
                    best_video = videos[choice_idx]
                    print(f"AI selected Option {choice_idx}!")
        except Exception as e:
            print(f"AI selection failed ({e}), falling back to Option 0.")
            
    video_files = best_video["video_files"]
    hd_file = next((f for f in video_files if f["quality"] == "hd"), video_files[0])
    download_url = hd_file["link"]
    
    print(f"Downloading video from {download_url} to {output_path}...")
    with requests.get(download_url, stream=True) as r:
        r.raise_for_status()
        with open(output_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
                
    return output_path
