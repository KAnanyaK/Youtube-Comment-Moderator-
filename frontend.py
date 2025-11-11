import streamlit as st
from google_auth_oauthlib.flow import Flow
import os
import json
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
CLIENT_SECRETS_FILE = os.getenv("CLIENT_SECRETS_FILE", "client_secret.json")
SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:5000")

# Initialize session state
if 'credentials' not in st.session_state:
    st.session_state.credentials = None

# App layout
st.set_page_config(page_title="YouTube Comment Moderator", page_icon="🎬", layout="centered")
st.title("🎬 **AI-Powered YouTube Comment Moderator**")

st.markdown("""
Welcome to your **AI Comment Moderation Dashboard**! 
Use this tool to automatically analyze and hide YouTube comments based on your custom moderation rules. 
---
""")

# OAuth Helper
def get_flow():
    return Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        redirect_uri="http://localhost:8501/"
    )

# Step 1: OAuth Login
st.header("🔑 Step 1: Google Account Authorization")

if st.session_state.credentials is None:
    flow = get_flow()
    
    # Check if the authorization code is in the query parameters
    query_params = st.query_params
    if "code" in query_params:
        try:
            # Exchange the code for credentials
            flow.fetch_token(code=query_params["code"])
            creds = flow.credentials
            creds_dict = {
                "token": creds.token,
                "refresh_token": creds.refresh_token,
                "token_uri": creds.token_uri,
                "client_id": creds.client_id,
                "client_secret": creds.client_secret,
                "scopes": creds.scopes
            }
            st.session_state.credentials = creds_dict
            
            # Clear the query parameters and rerun the script
            st.query_params.clear()
            st.success("✅ Authorization successful! You can now moderate your videos.")
            st.rerun()

        except Exception as e:
            st.error(f"❌ Failed to fetch token: {e}")
            st.stop()

    else:
        # Show the authorization link
        auth_url, _ = flow.authorization_url(prompt='consent')
        st.markdown(f"To get started, you need to authorize the application:")
        st.markdown(f"### [👉 Click here to authorize access via Google]({auth_url})")
        st.info("After authorizing, you will be redirected back to this page.")
    st.stop()

# Step 2: YouTube Setup
creds = Credentials(**st.session_state.credentials)
youtube = build("youtube", "v3", credentials=creds)

st.header("📺 Step 2: Choose Your YouTube Channel and Video")

channel_id = st.text_input("Enter your **Channel ID** (leave blank for your own uploads):")

if st.button("🔍 Fetch My Videos"):
    try:
        if not channel_id:
            me = youtube.channels().list(mine=True, part="id,snippet,contentDetails").execute()
            channel_id = me["items"][0]["id"]

        pl_req = youtube.channels().list(id=channel_id, part="contentDetails").execute()
        uploads_id = pl_req["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

        videos = []
        next_page = None
        while len(videos) < 10:
            v_req = youtube.playlistItems().list(
                playlistId=uploads_id,
                part="snippet",
                maxResults=10,
                pageToken=next_page
            ).execute()
            for item in v_req["items"]:
                videos.append({
                    "videoId": item["snippet"]["resourceId"]["videoId"],
                    "title": item["snippet"]["title"]
                })
            next_page = v_req.get("nextPageToken")
            if not next_page:
                break

        if not videos:
            st.error("😕 No videos found for this channel.")
            st.stop()

        options = {v["title"]: v["videoId"] for v in videos}
        video_title = st.selectbox("🎥 Select a video to moderate:", list(options.keys()))
        selected_video_id = options[video_title]

        st.session_state.selected_video_id = selected_video_id
        st.success(f"✅ Selected video: **{video_title}**")

    except Exception as e:
        st.error(f"❌ Error fetching channel/videos: {str(e)}")
        st.stop()

# Step 3: Moderation
selected_video_id = st.session_state.get("selected_video_id")
if selected_video_id:
    st.header("🧹 Step 3: Define Moderation Rules and Start Cleanup")

    st.markdown("""
    Enter your **moderation rules**, one per line (e.g. “No hate speech”, “No spam links”, etc). 
    The AI will check each comment against your rules and automatically hide violating ones.
    """)

    rules_text = st.text_area("✏️ Moderation Rules (one per line):", height=150, placeholder="Example:\nNo hate speech\nNo self-promotion links\nNo harassment or threats")

    if st.button("🚀 Start Moderation and Deletion"):
        data = {
            "video_id": selected_video_id,
            "rules": [r for r in rules_text.splitlines() if r.strip()],
            "oauth_token": st.session_state.credentials["token"],
            "refresh_token": st.session_state.credentials["refresh_token"]
        }

        with st.spinner("🤖 AI is analyzing comments and enforcing rules..."):
            response = requests.post(f"{BACKEND_URL}/moderate_and_delete", json=data)

        if response.ok:
            result = response.json()
            moderation_results = result.get("moderation_results", [])
            
            # --- FIX APPLIED HERE ---
            # Changed 'decision' to 'ai_decision' to match the backend response key
            flagged = [r for r in moderation_results if r.get("ai_decision", "").lower().startswith("yes")]

            st.markdown("---")
            st.subheader("🧾 Moderation Summary")

            if flagged:
                st.success(f"✅ **{len(flagged)} comments flagged and hidden.** Below are the details:")

                for entry in flagged:
                    # --- FIX APPLIED HERE ---
                    # Changed 'decision' to 'ai_decision' when displaying the reason
                    decision_text = entry.get("ai_decision", "YES: No explanation provided")
                    reason_text = decision_text[4:].strip() if len(decision_text) > 4 else 'Matched moderation rule'

                    st.markdown(
                        f"""
                        <div style='background-color:#f9f9f9; padding:15px; border-radius:10px; margin-bottom:10px; border-left: 4px solid #e74c3c;'>
                            <p><b>💬 Comment:</b> {entry['comment']}</p>
                            <p><b>🚫 Reason:</b> {reason_text}</p>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
            else:
                st.info("🎉 No problematic comments found — your video looks clean and positive!")

        else:
            st.error("⚠️ Backend Error: " + response.text)
