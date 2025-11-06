from googleapiclient.discovery import build

# ---- Set your YouTube API key below ----
API_KEY = "AIzaSyBHVjZjS_oBsjh2p7h52NG-vYP1zfbAvG0" #YOUTUBE_API_KEY
VIDEO_ID = "Reh0m9-TnD4"  # e.g., "https://www.youtube.com/watch?v=Reh0m9-TnD4"

# ==== Moderation Settings ====
MODERATION_RULES = """
- No hate speech
- No spam or promotional content
- No offensive language
- No personal attacks
"""

USE_GROQ = True  # Set to True if you have Groq API key

def fetch_comments(api_key, video_id, max_results=2):
    youtube = build("youtube", "v3", developerKey=api_key)
    comments = []
    next_page_token = None
    fetched = 0

    while fetched < max_results:
        request = youtube.commentThreads().list(
            part="snippet",
            videoId=video_id,
            maxResults=min(max_results - fetched, 100),
            pageToken=next_page_token,
            textFormat="plainText",
        )
        response = request.execute()
        for item in response.get("items", []):
            comment_text = item["snippet"]["topLevelComment"]["snippet"]["textDisplay"]
            comments.append(comment_text)
        fetched += len(response.get("items", []))
        next_page_token = response.get("nextPageToken")
        if not next_page_token or fetched >= max_results:
            break
    return comments

def moderate_comment(comment, moderation_rules):
    prompt = (
        f"Moderation rules:\n{moderation_rules}\n\n"
        f"Comment:\n{comment}\n\n"
        "Does this comment violate the rules? Answer YES or NO and provide a short reason."
    )

    if USE_GROQ:
        # Using Groq LLM
        import groq
        groq_client = groq.Client(api_key="GROK_API_KEY")
        response = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}]
        )
        result = response.choices[0].message.content
    else:
        # Using OpenAI (e.g., GPT-3.5-turbo)
        import openai
        openai.api_key = "YOUR_OPENAI_API_KEY"
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}]
        )
        result = response.choices[0].message.content

    return result

if __name__ == "__main__":
    comments = fetch_comments(API_KEY, VIDEO_ID, max_results=10)
    print(f"Fetched {len(comments)} comments.")
    print("\nModeration Results:")
    for comment in comments:
        moderation_result = moderate_comment(comment, MODERATION_RULES)
        print(f"- Comment: {comment}")
        print("  AI Decision:", moderation_result)
        print()
