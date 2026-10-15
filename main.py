import json
import re
from urllib.parse import unquote, urlparse

import requests
import streamlit as st

API_URL = "https://www.googleapis.com/youtube/v3/channels"

st.set_page_config(page_title="유튜브 채널 API 조회", page_icon="📺", layout="wide")
st.title("📺 유튜브 채널 정보 조회")
st.write("채널 주소를 입력하면 YouTube Data API에서 받은 응답을 JSON 형식 그대로 보여줍니다.")


def parse_channel_url(raw_url: str) -> tuple[str, str]:
    """Return ('forHandle', '@handle') or ('id', 'UC...')."""
    value = raw_url.strip()
    if not value:
        raise ValueError("유튜브 채널 링크를 입력해 주세요.")
    if not re.match(r"^https?://", value, flags=re.IGNORECASE):
        value = "https://" + value

    parsed = urlparse(value)
    hostname = (parsed.hostname or "").lower()
    if hostname not in {"youtube.com", "www.youtube.com", "m.youtube.com"}:
        raise ValueError("youtube.com 채널 링크만 입력할 수 있습니다.")

    path = unquote(parsed.path).strip("/")
    parts = path.split("/") if path else []

    if len(parts) == 1 and parts[0].startswith("@") and len(parts[0]) > 1:
        return "forHandle", parts[0]
    if len(parts) == 2 and parts[0] == "channel" and re.fullmatch(r"UC[A-Za-z0-9_-]{22}", parts[1]):
        return "id", parts[1]

    raise ValueError("지원하는 주소 형식은 youtube.com/@핸들 또는 youtube.com/channel/UC… 입니다.")


def fetch_channel_data(key_type: str, key_value: str, api_key: str) -> dict:
    params = {
        "part": "snippet,statistics,contentDetails",
        key_type: key_value,
        "key": api_key,
    }
    try:
        response = requests.get(API_URL, params=params, timeout=20)
        payload = response.json()
    except requests.Timeout as exc:
        raise RuntimeError("요청 시간이 초과되었습니다. 잠시 후 다시 시도해 주세요.") from exc
    except requests.RequestException as exc:
        raise RuntimeError("유튜브 API에 연결하지 못했습니다.") from exc
    except ValueError as exc:
        raise RuntimeError("유튜브 API에서 JSON 형식이 아닌 응답을 받았습니다.") from exc

    if not response.ok:
        details = payload.get("error", {}) if isinstance(payload, dict) else {}
        message = details.get("message", "알 수 없는 API 오류")
        raise RuntimeError(f"유튜브 API 오류 (HTTP {response.status_code}): {message}")
    return payload


with st.form("channel_lookup"):
    channel_url = st.text_input(
        "유튜브 채널 링크",
        placeholder="https://www.youtube.com/@GoogleDevelopers",
    )
    submitted = st.form_submit_button("채널 정보 조회", type="primary")

if submitted:
    try:
        api_key = st.secrets.get("YOUTUBE_API_KEY")
        if not api_key:
            st.error("Secrets에 YOUTUBE_API_KEY가 설정되어 있지 않습니다.")
            st.stop()

        key_type, key_value = parse_channel_url(channel_url)
        with st.spinner("유튜브 API에서 채널 정보를 가져오는 중입니다..."):
            data = fetch_channel_data(key_type, key_value, api_key)

        if not data.get("items"):
            st.warning("해당 주소로 조회된 채널이 없습니다. 채널 링크를 확인해 주세요.")
        else:
            st.success("조회가 완료되었습니다.")
            st.subheader("API 원본 응답 (JSON)")
            st.json(data, expanded=2)
            st.download_button(
                "JSON 파일 저장",
                data=json.dumps(data, ensure_ascii=False, indent=2),
                file_name="youtube_channel_response.json",
                mime="application/json",
            )
    except ValueError as exc:
        st.warning(str(exc))
    except RuntimeError as exc:
        st.error(str(exc))
    except Exception as exc:
        st.error("설정 또는 요청 처리 중 오류가 발생했습니다. Secrets 설정을 확인해 주세요.")
