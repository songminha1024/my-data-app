import streamlit as st
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


# --------------------------------------------------
# 기본 설정
# --------------------------------------------------

st.set_page_config(
    page_title="어제의 박스오피스",
    page_icon="🎬",
    layout="wide"
)

st.title("🎬 어제의 박스오피스")


# --------------------------------------------------
# 한국 시간 기준으로 '어제' 날짜 계산
# 배포 서버의 시간이 한국 시간이 아닐 수 있으므로
# 반드시 Asia/Seoul 시간대를 사용합니다.
# --------------------------------------------------

KST = ZoneInfo("Asia/Seoul")

now_kst = datetime.now(KST)
yesterday = now_kst.date() - timedelta(days=1)

# KOBIS API가 요구하는 YYYYMMDD 형식
target_dt = yesterday.strftime("%Y%m%d")

st.caption(
    f"조회 날짜: {yesterday.strftime('%Y년 %m월 %d일')} "
    f"(한국 시간 기준)"
)


# --------------------------------------------------
# KOBIS API에서 데이터를 가져오는 함수
#
# cache_data를 사용하면 같은 날짜를 다시 조회할 때
# 1시간 동안 API를 다시 호출하지 않습니다.
# --------------------------------------------------

@st.cache_data(ttl=3600)
def get_boxoffice(target_dt, api_key):
    url = (
        "https://www.kobis.or.kr/kobisopenapi/webservice/rest/"
        "boxoffice/searchDailyBoxOfficeList.json"
    )

    params = {
        "key": api_key,
        "targetDt": target_dt
    }

    try:
        response = requests.get(
            url,
            params=params,
            timeout=10
        )

        # HTTP 오류 확인
        response.raise_for_status()

        # JSON으로 변환
        data = response.json()

    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "message": f"KOBIS API 요청에 실패했습니다.\n\n{e}"
        }

    except ValueError:
        return {
            "success": False,
            "message": "KOBIS API가 올바른 JSON 데이터를 반환하지 않았습니다."
        }

    # --------------------------------------------------
    # 인증키 오류 등의 경우 HTTP 상태코드는 200이어도
    # faultInfo가 들어올 수 있으므로 확인합니다.
    # --------------------------------------------------

    if "faultInfo" in data:
        fault = data["faultInfo"]

        fault_code = fault.get("errorCode", "알 수 없음")
        fault_message = fault.get("message", "알 수 없는 오류")

        return {
            "success": False,
            "message": (
                f"KOBIS API 오류가 발생했습니다.\n\n"
                f"오류 코드: {fault_code}\n"
                f"오류 내용: {fault_message}\n\n"
                f"확인할 것:\n"
                f"• Streamlit Secrets에 KOBIS_KEY가 등록되어 있는지\n"
                f"• 인증키를 정확하게 입력했는지\n"
                f"• KOBIS API 사용이 정상적으로 가능한지"
            )
        }

    # 예상한 응답 구조가 있는지 확인
    box_office_result = data.get("boxOfficeResult")

    if not box_office_result:
        return {
            "success": False,
            "message": (
                "KOBIS 응답에 boxOfficeResult가 없습니다.\n\n"
                "KOBIS API 응답 형식이나 API 상태를 확인해 주세요."
            )
        }

    movies = box_office_result.get("dailyBoxOfficeList", [])

    # 영화 목록이 비어 있는 경우
    if not movies:
        return {
            "success": False,
            "message": (
                f"{target_dt} 날짜의 박스오피스 영화 목록이 비어 있습니다.\n\n"
                "확인할 것:\n"
                "• 해당 날짜의 박스오피스가 집계되었는지\n"
                "• 조회 날짜가 올바른지\n"
                "• KOBIS API가 정상적으로 응답했는지"
            )
        }

    # --------------------------------------------------
    # API에서 숫자가 문자열로 오므로 숫자로 변환합니다.
    # --------------------------------------------------

    converted_movies = []

    for movie in movies:
        try:
            converted_movie = {
                "rank": int(movie.get("rank", 0)),
                "movieNm": movie.get("movieNm", ""),
                "openDt": movie.get("openDt", ""),
                "audiCnt": int(movie.get("audiCnt", 0)),
                "audiAcc": int(movie.get("audiAcc", 0)),
                "scrnCnt": int(movie.get("scrnCnt", 0)),
            }

            converted_movies.append(converted_movie)

        except (ValueError, TypeError):
            # 숫자로 변환할 수 없는 데이터가 있으면
            # 해당 영화는 건너뜁니다.
            continue

    if not converted_movies:
        return {
            "success": False,
            "message": (
                "영화 데이터는 받았지만 숫자 데이터를 변환할 수 없습니다.\n\n"
                "KOBIS API 응답 형식을 확인해 주세요."
            )
        }

    return {
        "success": True,
        "movies": converted_movies
    }


# --------------------------------------------------
# Streamlit Secrets에서 인증키 가져오기
# 코드에 인증키를 직접 적지 않습니다.
# --------------------------------------------------

try:
    api_key = st.secrets["KOBIS_KEY"]

except KeyError:
    st.error(
        "KOBIS_KEY를 찾을 수 없습니다.\n\n"
        "확인할 것:\n"
        "• Streamlit Cloud의 Secrets에 KOBIS_KEY가 등록되어 있는지\n"
        "• Secrets 이름이 정확히 KOBIS_KEY인지\n"
        "• 인증키 값이 올바르게 입력되어 있는지"
    )
    st.stop()


# --------------------------------------------------
# API 호출
# --------------------------------------------------

result = get_boxoffice(target_dt, api_key)


# API 요청 실패
if not result["success"]:
    st.error(result["message"])
    st.stop()


movies = result["movies"]


# --------------------------------------------------
# 1위 영화
# --------------------------------------------------

first_movie = movies[0]

st.subheader("🏆 1위 영화")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        "당일 관객수",
        f"{first_movie['audiCnt']:,}명"
    )

with col2:
    st.metric(
        "누적 관객수",
        f"{first_movie['audiAcc']:,}명"
    )

with col3:
    st.metric(
        "스크린수",
        f"{first_movie['scrnCnt']:,}개"
    )

st.markdown(
    f"### {first_movie['rank']}위 · {first_movie['movieNm']}"
)

st.write(
    f"개봉일: {first_movie['openDt']}"
)


# --------------------------------------------------
# 전체 박스오피스 표
# --------------------------------------------------

st.subheader("📋 일별 박스오피스")

# 화면에 보여줄 표를 만들기
table_data = []

for movie in movies:
    table_data.append({
        "순위": movie["rank"],
        "영화명": movie["movieNm"],
        "개봉일": movie["openDt"],
        "관객수": movie["audiCnt"],
        "누적관객": movie["audiAcc"],
        "스크린수": movie["scrnCnt"]
    })

st.dataframe(
    table_data,
    use_container_width=True,
    hide_index=True,
    column_config={
        "순위": st.column_config.NumberColumn(
            format="%d"
        ),
        "관객수": st.column_config.NumberColumn(
            format="%,d명"
        ),
        "누적관객": st.column_config.NumberColumn(
            format="%,d명"
        ),
        "스크린수": st.column_config.NumberColumn(
            format="%,d개"
        )
    }
)


# --------------------------------------------------
# 관객수 상위 5편 막대그래프
# 숫자로 변환해 놓았기 때문에
# 관객수를 기준으로 정확하게 정렬할 수 있습니다.
# --------------------------------------------------

st.subheader("📊 관객수 상위 5편")

top5 = sorted(
    movies,
    key=lambda movie: movie["audiCnt"],
    reverse=True
)[:5]

# 영화명을 인덱스로 하는 딕셔너리 생성
chart_data = {
    movie["movieNm"]: movie["audiCnt"]
    for movie in top5
}

st.bar_chart(
    chart_data,
    horizontal=True,
    x_label="관객수",
    y_label="영화"
)


# --------------------------------------------------
# 데이터 안내
# --------------------------------------------------

st.caption(
    "데이터 출처: 영화진흥위원회(KOBIS) 일별 박스오피스 API"
)
