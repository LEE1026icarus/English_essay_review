# app.py
# ------------------------------------------------------------
# 에세이 피드백 (폼/챗봇) 통합 앱 - 통합본
# - 사이드바에서 "폼 형식" / "챗봇 형식" 선택
# - 평문 공유 암호 로그인
# - OpenAI 응답 + Supabase 로깅
# - 루브릭 옵션 제거, "일반 에세이" 기준으로 고정
# - 가이드 패널: 사용자가 제공한 지침(Thesis/인용형식/문단 흐름) 중심으로 재작성
# ------------------------------------------------------------

import os, uuid, re, datetime, pytz
import streamlit as st
from dotenv import load_dotenv
from supabase import create_client, Client
from openai import OpenAI

# =========================
# SECTION 0. 환경 로드
# =========================
try:
    load_dotenv()
except Exception:
    pass

def get_secret(k, default=None):
    """secrets.toml 우선, 없으면 환경변수"""
    try:
        if k in st.secrets:
            return st.secrets[k]
    except Exception:
        pass
    return os.getenv(k, default)

OPENAI_API_KEY = get_secret("OPENAI_API_KEY")
SUPABASE_URL   = get_secret("SUPABASE_URL")
SUPABASE_KEY   = get_secret("SUPABASE_KEY")
PLAINTEXT_PW   = get_secret("PLAINTEXT_SHARED_PASSWORD")  # 평문 공유 암호
# --- (선택) 서버 전용 키: 브라우저/프론트로 절대 노출 금지 ---
SUPABASE_SERVICE_ROLE_KEY = get_secret("SUPABASE_SERVICE_ROLE_KEY")

# --- Supabase 클라이언트: anon + (선택) service role ---
supabase_anon: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
supabase_admin: Client = None
if SUPABASE_SERVICE_ROLE_KEY:
    supabase_admin = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

# 필수 키 확인
if not (OPENAI_API_KEY and SUPABASE_URL and SUPABASE_KEY and PLAINTEXT_PW):
    st.error("필수 키가 없습니다. OPENAI_API_KEY, SUPABASE_URL, SUPABASE_KEY, PLAINTEXT_SHARED_PASSWORD를 설정하세요.")
    st.stop()

# OpenAI/Supabase 클라이언트 준비
client = OpenAI(api_key=OPENAI_API_KEY)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# 타임존
KST = pytz.timezone("Asia/Seoul")

# =========================
# SECTION 1. 공통 프롬프트/헬퍼
# =========================

# --- 에세이 가이드(사용자 제공 텍스트 기반) ---
ESSAY_GUIDE = """
1. 기본 구조 이해하기
- 서론 (Introduction)
  Thesis statement(주제문): 글 전체의 중심 아이디어 또는 주장. 보통 서론 마지막 부분에 위치.
  길거나 모호하지 않게, 글 전체의 방향성을 제시해야 함.

- 본론 (Body)
  Topic sentence(주제문): 각 문단의 핵심 아이디어를 제시하며, 문단의 첫 부분에 위치.
  Supporting sentences(뒷받침 문장): 구체적 설명, 예시, 사실, 근거 등을 통해 topic sentence를 뒷받침.
  불필요하거나 관련 없는 문장은 제거하여 문단의 초점을 흐리지 않도록 주의.

- 결론 (Conclusion)
  전체 내용을 요약하면서, 자신의 의견을 간단히 정리.
  새로운 주제는 제시하지 않고, 앞서 다룬 내용을 종합해야 함.

2. Balanced Opinion Essay의 특징
- 양측 주장을 균형 있게 다루기 (찬성과 반대, 장점과 단점을 모두 제시).
- 객관적인 근거 제시: 각 입장에 대해 예시·사례·설명 등을 보충해야 설득력이 있음.
- 단순 주장만 나열하지 말고, 데이터를 뒷받침하는 문장을 포함할 것.

3. 글쓰기 과정에서 주의할 점
- 글을 시작할 때 반드시 **중심 주장(Thesis)**을 먼저 설정하고 나머지 문단을 구성.
- 문단별로 한 가지 핵심 아이디어만 유지.
- 연결성: Thesis ↔ Topic sentence ↔ Supporting sentences가 자연스럽게 이어져야 함.
- 관련 없는 문장은 삭제(예: ‘탄산음료 매일 마시기’처럼 글의 흐름을 깨는 문장).
- 결론에서는 균형 잡힌 시각을 보여주되, 최종적으로 본인의 의견을 명확히 밝힐 것.
"""

# --- 시스템 프롬프트(폼) ---
SYSTEM_PROMPT_FORM = (
    "너는 대학원 수준의 글쓰기 코치다. "
    "사용자가 작성한 일반 에세이를 아래 가이드라인에 따라 평가하고 피드백하라.\n\n"
    f"{ESSAY_GUIDE}\n\n"
    "출력 형식: 총평/강점/개선/문장별 제안/점수.\n"
    "허위 인용 금지, 단정 대신 권고 표현 사용."
)

# --- 시스템 프롬프트(챗봇) ---
SYSTEM_PROMPT_CHAT = (
    "너는 대학원 수준의 글쓰기 코치다. "
    "사용자가 입력한 에세이/문단/문장을 아래 가이드라인에 따라 피드백하라.\n\n"
    f"{ESSAY_GUIDE}\n\n"
    "출력 형식: "
    "1) 총평(2~3문장), "
    "2) 강점(불릿 3~5개), "
    "3) 개선 제안(Top5, 왜/어떻게 포함), "
    "4) 문장별 제안(필요한 문장만: 원문/제안/이유), "
    "5) 점수(구성·논리/논거/명료성·간결성/학문적 톤/전반). "
    "허위 인용 금지, 단정 대신 권고 표현 사용."
)

# --- 고정 루브릭(옵션 제거) ---
FIXED_RUBRIC = "일반 에세이"   # 항상 이 기준으로 피드백

def ok_pw(pw: str) -> bool:
    return pw == PLAINTEXT_PW

def slug(name: str) -> str:
    s = re.sub(r"\s+", "-", name.strip())
    s = re.sub(r"[^a-zA-Z0-9\-가-힣]", "", s)
    return (s or "user")[:24]

def supabase_log(user_id: str, user_name: str, question: str, answer: str, meta: dict):
    """공통 로깅: service_role 우선 사용 (없으면 anon)"""
    try:
        client_for_log = supabase_admin or supabase_anon  # RLS가 엄격하면 service role 권장(서버 전용)
        _ = client_for_log.table("essay_review").insert({
            "user_id": user_id,
            "user_name": user_name,
            "question": question,
            "answer": answer,
            "rubric": meta.get("rubric"),
            "length_hint": meta.get("length_hint"),
            "model": meta.get("model"),
            "meta": meta,
        }).execute()
        return True, None
    except Exception as e:
        return False, str(e)

def generate_feedback_once(essay: str, rubric: str, length: str, model: str, system_prompt: str) -> str:
    """단발성 생성(폼 형식)"""
    msg = f"[에세이]\n{essay}\n\n[루브릭]\n- 기준:{rubric}\n- 길이:{length}"
    r = client.chat.completions.create(
        model=model,
        temperature=0.8,
        messages=[
            {"role":"system","content":system_prompt},
            {"role":"user","content":msg}
        ]
    )
    return r.choices[0].message.content.strip()

def build_openai_messages(history, rubric, length_hint, system_prompt: str):
    """히스토리 + 힌트 포함(챗봇 형식)"""
    msgs = [{"role": "system", "content": system_prompt}]
    for m in history:
        msgs.append({"role": m["role"], "content": m["content"]})
    # 힌트(루브릭/길이) 부가
    hint = f"[루브릭] 기준={rubric or '일반 에세이'} / 길이={length_hint or '보통'}"
    msgs.append({"role": "user", "content": hint})
    return msgs

def stream_response(messages, model_name: str = "gpt-4o-mini", temperature: float = 0.3):
    """스트리밍 생성기(챗봇 형식)"""
    stream = client.chat.completions.create(
        model=model_name,
        temperature=temperature,
        messages=messages,
        stream=True,
    )
    for chunk in stream:
        try:
            delta = chunk.choices[0].delta.content or ""
        except Exception:
            delta = ""
        if delta:
            yield delta

# =========================
# SECTION 2. 페이지/세션
# =========================
st.set_page_config(page_title="에세이 피드백 통합(폼/챗봇)", layout="wide")
st.title("✍️ 에세이 피드백 (통합 앱)")

# 세션 상태
if "auth" not in st.session_state: st.session_state.auth = False
if "user_id" not in st.session_state: st.session_state.user_id = None
if "user_name" not in st.session_state: st.session_state.user_name = ""
if "messages" not in st.session_state: st.session_state.messages = []  # 챗봇용

# 로그인 게이트
if not st.session_state.auth:
    with st.form("login"):
        st.subheader("로그인")
        name = st.text_input("학번")
        pw = st.text_input("수업 코드", type="password")
        submitted = st.form_submit_button("입장")
        if submitted:
            if not name.strip():
                st.error("학번을 입력하세요.")
            elif not ok_pw(pw):
                st.error("암호가 올바르지 않습니다.")
            else:
                st.session_state.user_name = name.strip()
                st.session_state.user_id = f"{slug(name)}-{uuid.uuid4().hex[:6]}"
                st.session_state.auth = True
                st.session_state.messages = []
                st.rerun()
    st.stop()

# =========================
# SECTION 3. 사이드바 공통
# =========================
mode = st.sidebar.radio("모드 선택", ["폼 형식", "챗봇 형식"], index=0)
st.sidebar.markdown(f"**사용자:** {st.session_state.user_name} ({st.session_state.user_id})")

# --- 루브릭 옵션 제거: 고정값 ---
rubric = FIXED_RUBRIC

# 모델 / 길이 옵션
model_options  = ["gpt-4o-mini", "gpt-4o"]

if mode == "폼 형식":
    length_hint = st.sidebar.select_slider("피드백 길이", options=["짧게", "보통", "길게"], value="보통")
    model_choice = st.sidebar.selectbox("모델", model_options, index=0)
    st.sidebar.info("입력/출력은 Supabase에 기록됩니다. 민감정보 입력 금지.")

elif mode == "챗봇 형식":
    length_hint = st.sidebar.select_slider("피드백 길이", options=["짧게", "보통", "길게"], value="보통")
    model_choice = st.sidebar.selectbox("모델", model_options, index=0)
    if st.sidebar.button("새 대화"):
        st.session_state.messages = []
        st.rerun()
    st.sidebar.info("모든 메시지(질문/답변)는 Supabase에 기록됩니다. 민감정보 입력 금지.")

# =========================
# SECTION 4A. 폼 UI
# =========================
if mode == "폼 형식":
    c1, c2 = st.columns([2, 1])
    with c1:
        essay = st.text_area("에세이 원문", height=300)
        if st.button("피드백 받기"):
            if not essay.strip():
                st.warning("에세이를 입력하세요.")
            else:
                with st.spinner("생성 중..."):
                    try:
                        out = generate_feedback_once(
                            essay=essay,
                            rubric=rubric,               # 고정: 일반 에세이
                            length=length_hint,
                            model=model_choice,
                            system_prompt=SYSTEM_PROMPT_FORM,
                        )
                        st.markdown("### 결과")
                        st.markdown(out)
                    except Exception as e:
                        st.error(f"피드백 생성 오류: {e}")
                        st.stop()

                    # 로깅
                    meta = {
                        "rubric": rubric,
                        "length_hint": length_hint,
                        "model": model_choice,
                        "tz": "Asia/Seoul",
                        "ts": datetime.datetime.now(tz=KST).isoformat(),
                        "ui": "form",
                    }
                    ok, err = supabase_log(
                        user_id=st.session_state.user_id,
                        user_name=st.session_state.user_name,
                        question=essay,
                        answer=out,
                        meta=meta,
                    )
                    if ok:
                        st.success("로그 저장 완료")
                    else:
                        st.warning(f"로그 저장 실패: {err}")

    # --- 가이드 패널: 사용자 제공 지침 기반 재작성 ---
    with c2:
        st.markdown("✅ 구조 체크리스트")
        st.markdown(
                "- [ ] 서론 마지막에 명확한 Thesis가 있나요?\n"
                "- [ ] 각 문단 첫 문장에 Topic sentence가 있나요?\n"
                "- [ ] Topic을 뒷받침하는 구체적 **근거/예시/데이터**가 포함되었나요?\n"
                "- [ ] 관련 없는 문장(예: 일상적 잡담·주제 이탈)은 **삭제**했나요?\n"
                "- [ ] 결론에서 새로운 주제를 열지 않고 **요약+나의 최종 의견**으로 마무리했나요?"
        )

        with st.expander("⚖️ Balanced Opinion Essay 체크리스트"):
            st.markdown(
                "- [ ] **양쪽 입장**(찬성/반대 또는 장점/단점)을 균형 있게 소개했나요?\n"
                "- [ ] 각 입장에 **객관적 근거**(사례·설명·데이터)를 붙였나요?\n"
                "- [ ] 단순 주장 나열을 피하고, 논거 간 **논리적 연결**이 자연스러운가요?\n"
                "- [ ] 결론에서 균형적 관점을 요약하되 **최종 입장**을 명확히 밝혔나요?"
            )

        with st.expander("🛠 제출 전 5가지 점검"):
            st.markdown(
                "1) Thesis가 길거나 모호하지 않은가?\n"
                "2) 각 문단이 **한 가지 핵심 아이디어**만 다루는가?\n"
                "3) Topic ↔ 근거/예시 간 연결이 매끄러운가?\n"
                "4) 주제와 무관한 문장을 삭제했는가? (예: ‘탄산음료 매일 마시기’ 등)\n"
                "5) 결론에서 나의 입장이 명확하게 드러나는가?"
            )

# =========================
# SECTION 4B. 챗봇 UI
# =========================
else:
    st.markdown("💬 **에세이를 붙여넣거나, 문장을 입력해 피드백을 요청하세요.**")

    # 기록된 메시지 렌더
    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])

    # 입력
    user_input = st.chat_input("메시지를 입력하세요")
    if user_input:
        # 사용자 메시지 반영
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        # 어시스턴트 자리
        with st.chat_message("assistant"):
            placeholder = st.empty()
            assistant_text = ""
            try:
                # 이전 히스토리 + 힌트 + 현재 입력
                messages = build_openai_messages(
                    history=st.session_state.messages[:-1],
                    rubric=rubric,                 # 고정: 일반 에세이
                    length_hint=length_hint,
                    system_prompt=SYSTEM_PROMPT_CHAT,
                )
                messages.append({"role": "user", "content": user_input})

                for delta in stream_response(messages, model_name=model_choice, temperature=0.3):
                    assistant_text += delta
                    placeholder.markdown(assistant_text)
            except Exception as e:
                assistant_text = f"응답 생성 중 오류가 발생했습니다: {e}"
                placeholder.markdown(assistant_text)

        # 히스토리에 어시스턴트 메시지 저장
        st.session_state.messages.append({"role": "assistant", "content": assistant_text})

        # 로깅
        meta = {
            "rubric": rubric,
            "length_hint": length_hint,
            "model": model_choice,
            "tz": "Asia/Seoul",
            "ts": datetime.datetime.now(tz=KST).isoformat(),
            "ui": "chatbot",
        }
        ok, err = supabase_log(
            user_id=st.session_state.user_id,
            user_name=st.session_state.user_name,
            question=user_input,
            answer=assistant_text,
            meta=meta,
        )
        if not ok:
            st.toast(f"로그 저장 실패: {err}", icon="⚠️")


