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
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

# =======================
# Flask Setup
# =======================
app = Flask(__name__)
CORS(app)
COLLECTION_NAME = "moderation_rules_demo"
MAX_COMMENTS = 50  # Adjust as needed

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
        creds = Credentials(
            token=token,
            refresh_token=refresh_token,
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            token_uri="https://oauth2.googleapis.com/token",
            scopes=["https://www.googleapis.com/auth/youtube.force-ssl"]
        )

        if creds.expired and creds.refresh_token:
            print("🔄 Refreshing expired credentials...")
            creds.refresh(Request())

        youtube = build("youtube", "v3", credentials=creds)
        print("✅ YouTube API client built successfully.")

        # =======================
        # Initialize Chroma + Groq
        # =======================
        chroma_client = chromadb.Client(Settings(persist_directory="./chroma_db"))
        embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
        collection = chroma_client.get_or_create_collection(COLLECTION_NAME)
        groq_client = groq.Client(api_key=GROQ_API_KEY)

        # Store/update rules in ChromaDB
        embeddings = embedding_model.encode(rules_input)
        ids = [f"rule_{i+1}" for i in range(len(rules_input))]
        collection.add(
            embeddings=embeddings.tolist(),
            documents=rules_input,
            metadatas=[{"rule": r} for r in rules_input],
            ids=ids
        )

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
                maxResults=min(MAX_COMMENTS - fetched, 100),
                pageToken=next_page_token,
                textFormat="plainText",
            )
            response_y = request_y.execute()

            for item in response_y.get("items", []):
                comment_text = item["snippet"]["topLevelComment"]["snippet"]["textDisplay"]
                comment_id = item["snippet"]["topLevelComment"]["id"]  # ✅ This is the correct comment ID
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
            comment_emb = embedding_model.encode(comment)
            result = collection.query(
                query_embeddings=[comment_emb.tolist()],
                n_results=1,
                include=["documents", "distances"]
            )
            top_rule = result['documents'][0][0]

            prompt = (
                f"Moderation rule:\n{top_rule}\n\n"
                f"Comment:\n{comment}\n\n"
                "Does this comment violate the rule? Reply ONLY YES or NO and a very short reason."
            )

            response = groq_client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": prompt}]
            )
            ai_decision = response.choices[0].message.content.strip()
            moderation_results.append({"comment": comment, "decision": ai_decision})

            # =======================
            # Deletion
            # =======================
            if ai_decision.lower().startswith("yes"):
                try:
                    delete_request = youtube.comments().setModerationStatus(
                    id=comment_id,
                    moderationStatus="rejected"
                    )
                    delete_request.execute()
                    deleted_comments.append(comment)
                    print(f"✅ Deleted comment: {comment_id}")
                except Exception as e:
                    print(f"❌ Failed to delete comment {comment_id}: {e}")

            print(f"✅ Moderation complete. Deleted {len(deleted_comments)} comments.")

        return jsonify({
            "status": "success",
            "deleted_comments": deleted_comments,
            "moderation_results": moderation_results
        })

    except Exception as e:
        print("❌ Error during moderation:", traceback.format_exc())
        return jsonify({"status": "error", "message": str(e)}), 500


# =======================
# Flask App Run
# =======================
if __name__ == "__main__":
    app.run(port=5000)
