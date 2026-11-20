"""Publicador YouTube Shorts via google-api-python-client (OAuth2)."""

from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def get_youtube_credentials(
    client_secret_path: Path, token_path: Path
) -> Credentials:
    """Carrega, atualiza ou executa OAuth2 local para gerar token.json."""
    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not client_secret_path.exists():
                raise FileNotFoundError(
                    f"Arquivo {client_secret_path} não encontrado. "
                    "Baixe o OAuth Client ID (Desktop) no Google Cloud Console."
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                str(client_secret_path), SCOPES
            )
            creds = flow.run_local_server(port=0)
        token_path.write_text(creds.to_json(), encoding="utf-8")

    return creds


def publish_youtube_short(
    video_path: Path,
    title: str,
    description: str,
    tags: list[str],
    client_secret_path: Path,
    token_path: Path,
) -> str:
    """Faz upload do vídeo no YouTube (privacyStatus='public', categoryId='22')."""
    creds = get_youtube_credentials(client_secret_path, token_path)
    youtube = build("youtube", "v3", credentials=creds)

    body = {
        "snippet": {
            "title": title[:100],
            "description": description,
            "tags": tags,
            "categoryId": "22",
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(
        str(video_path), chunksize=-1, resumable=True, mimetype="video/mp4"
    )
    request = youtube.videos().insert(
        part="snippet,status", body=body, media_body=media
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"[YouTube] Progresso upload: {int(status.progress() * 100)}%")

    video_id = response.get("id", "")
    print(f"[YouTube] Publicado! ID: {video_id}")
    return video_id
