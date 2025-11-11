from flask import Flask, request, jsonify
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
import groq
import os
from dotenv import load_dotenv
import traceback
from flask_cors import CORS
import time

# =======================
# Load Environment Variables
# =======================
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY") # Note: This API key is generally for read-only if not using OAuth

# =======================
# Flask Setup
# =======================
app = Flask(__name__)
CORS(app)
COLLECTION_NAME = "moderation_rules_demo"
MAX_COMMENTS = 50  # Adjust as needed

# =======================
# LLM Prompt Setup 🧠
# =======================
MODERATOR_SYSTEM_PROMPT = (
    "You are an expert YouTube Comment Moderator. Your sole task is to determine "
    "if a user comment strictly violates one of the provided channel moderation rules. "
    "Analyze the comment directly against the rule. "
    "Your response MUST start with 'YES' if the comment violates the rule, "
    "or 'NO' if it does not. After the YES/NO, provide a very brief, objective "
    "explanation (a single short sentence or phrase) for your decision. "
    "Do not include any conversational filler, greetings, or other text."
)

# =======================
# Main Route
# =======================
@app.route("/moderate_and_delete", methods=["POST"])
def moderate_and_delete():
    try:
        print("✅ Received moderation request.")
        data = request.get_json(force=True)

        video_id = data.get("video_id")
        rules_input = data.get("rules", [])
        token = data.get("oauth_token")
        refresh_token = data.get("refresh_token")

        if not video_id or not token:
            return jsonify({"status": "error", "message": "Missing video_id or OAuth token"}), 400

        # ✅ Build and refresh credentials if needed
        # SCOPE must include write access to moderate comments
        SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]
        creds = Credentials(
            token=token,
            refresh_token=refresh_token,
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            token_uri="https://oauth2.googleapis.com/token",
            scopes=SCOPES
        )

        if creds.expired and creds.refresh_token:
            print("🔄 Refreshing expired credentials...")
            creds.refresh(Request())

        youtube = build("youtube", "v3", credentials=creds)
        print("✅ YouTube API client built successfully.")

        # =======================
        # Initialize Chroma + Groq
        # =======================
        # Initialize ChromaDB persistent client
        chroma_client = chromadb.Client(Settings(persist_directory="./chroma_db"))
        # Initialize Sentence Transformer model
        embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
        # Get or create collection for rules
        collection = chroma_client.get_or_create_collection(COLLECTION_NAME)
        # Initialize Groq client
        groq_client = groq.Client(api_key=GROQ_API_KEY)

        # Store/update rules in ChromaDB
        if rules_input:
            embeddings = embedding_model.encode(rules_input)
            ids = [f"rule_{i+1}" for i in range(len(rules_input))]
            collection.add(
                embeddings=embeddings.tolist(),
                documents=rules_input,
                metadatas=[{"rule": r} for r in rules_input],
                ids=ids
            )
            print(f"✅ Stored {len(rules_input)} moderation rules in ChromaDB.")


        # =======================
        # Fetch Comments
        # =======================
        comments, comment_ids = [], []
        next_page_token = None
        fetched = 0

        print(f"📥 Fetching up to {MAX_COMMENTS} comments from video: {video_id}")
        while fetched < MAX_COMMENTS:
            request_y = youtube.commentThreads().list(
                part="snippet",
                videoId=video_id,
                # Fetch maximum 100 per page, limited by remaining MAX_COMMENTS
                maxResults=min(MAX_COMMENTS - fetched, 100), 
                pageToken=next_page_token,
                textFormat="plainText",
            )
            response_y = request_y.execute()

            for item in response_y.get("items", []):
                # The comment text from the top-level comment
                comment_text = item["snippet"]["topLevelComment"]["snippet"]["textDisplay"] 
                # The ID of the top-level comment
                comment_id = item["snippet"]["topLevelComment"]["id"] 
                comments.append(comment_text)
                comment_ids.append(comment_id)


            fetched += len(response_y.get("items", []))
            next_page_token = response_y.get("nextPageToken")
            if not next_page_token:
                break

        print(f"✅ Fetched {len(comments)} comments.")

        # =======================
        # Moderate Comments
        # =======================
        deleted_comments = []
        moderation_results = []

        for idx, (comment, comment_id) in enumerate(zip(comments, comment_ids)):
            # 1. Retrieve most relevant rule via RAG (Retrieval-Augmented Generation)
            comment_emb = embedding_model.encode(comment)
            result = collection.query(
                query_embeddings=[comment_emb.tolist()],
                n_results=1,
                include=["documents", "distances"]
            )
            top_rule = result['documents'][0][0]

            # 2. Build User Prompt
            user_prompt = (
                f"Moderation rule:\n{top_rule}\n\n"
                f"Comment:\n{comment}"
            )

            # 3. Call Groq API with System Message
            response = groq_client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    # **System Prompt sets the Moderator persona**
                    {"role": "system", "content": MODERATOR_SYSTEM_PROMPT}, 
                    # User content to be evaluated
                    {"role": "user", "content": user_prompt}
                ]
            )
            
            ai_decision = response.choices[0].message.content.strip()
            moderation_results.append({
                "comment": comment, 
                "rule_checked": top_rule,
                "ai_decision": ai_decision
            })

            # =======================
            # Deletion/Moderation Action
            # =======================
            # Check if the decision starts with "YES" (case-insensitive)
            if ai_decision.lower().startswith("yes"):
                try:
                    # Using setModerationStatus with "rejected" effectively hides the comment
                    # This is the correct action for comments made by OTHER users.
                    delete_request = youtube.comments().setModerationStatus(
                    id=comment_id,
                    moderationStatus="rejected"
                    )
                    delete_request.execute()
                    deleted_comments.append(comment)
                    print(f"✅ HIDDEN comment: {comment_id} - '{comment}'")
                except Exception as e:
                    # Log YouTube API errors (e.g., comment already deleted, permission issues)
                    print(f"❌ Failed to hide comment {comment_id}: {e}")

        print(f"✅ Moderation complete. Hidden {len(deleted_comments)} comments.")

        return jsonify({
            "status": "success",
            "total_comments_checked": len(comments),
            "hidden_comments_count": len(deleted_comments),
            "moderation_results": moderation_results
        })

    except Exception as e:
        # Catch and print full stack trace for better debugging
        print("❌ Error during moderation:", traceback.format_exc()) 
        return jsonify({"status": "error", "message": str(e)}), 500


# =======================
# Flask App Run
# =======================
if __name__ == "__main__":
    # Ensure you set host='0.0.0.0' if running in a container/server environment
    app.run(debug=True, port=5000)
