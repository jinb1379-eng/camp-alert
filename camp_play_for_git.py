import os
import requests
from datetime import datetime

# ==============================================================================
# [설정 영역]
# ==============================================================================
# GitHub Secrets에 등록된 값을 환경 변수에서 가져옵니다.
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

BUSINESS_ID = "1734741351"
CHECKIN = "20261031"   # 체크인 날짜: YYYYMMDD
CHECKOUT = "20261101"  # 체크아웃 날짜: YYYYMMDD
GUEST_COUNT = "3"      # 인원 수

# 특정 사이트/방만 감시하려면 이름 입력 (비워두면 전체 사이트 감시)
# 예: TARGET_ROOMS = ["A구역", "데크"]
TARGET_ROOMS = []

API_URL = "https://pcmap-api.place.naver.com/graphql"

HEADERS = {
    "accept": "*/*",
    "accept-language": "ko",
    "content-type": "application/json",
    "origin": "https://pcmap.place.naver.com",
    "priority": "u=1, i",
    "referer": f"https://pcmap.place.naver.com/accommodation/{BUSINESS_ID}/room?from=map&fromPanelNum=1&additionalHeight=76&timestamp=202610222230&locale=ko&svcName=map_pcv5&businessCategory=camping&entry=bmp&level=top&guest={GUEST_COUNT}&checkin={CHECKIN}&checkout={CHECKOUT}",
    "sec-ch-ua": '"Microsoft Edge";v="155", "Chromium";v="155", "Not(A:Brand";v="24"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-site",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36 Edg/155.0.0.0",
    "x-wtm-graphql": "eyJhcmciOiIxNzM0NzQxMzUxIiwidHlwZSI6ImFjY29tbW9kYXRpb24iLCJzb3VyY2UiOiJwbGFjZSJ9",
    "x-wtm-ncaptcha-token": "vlo81NKHruvDQS2rmYnv-7n6OsJS4QqJgZQElQlqIpc="
}

COOKIES = {
    "NNB": "VX52JPMD3SYWO",
    "ASID": "79b947de000001955465dc430000004e",
    "NAC": "YRxXBgw1AXRs",
    "PLACE_LANGUAGE": "ko",
    "page_uid": "jWoM7lqX5EwssmLKHfh-075009",
    "NLPA": "1051930d-96b2-4315-be78-27f7b64c46a4",
    "BUC": "E-8i2j8KKLO8FSfb_jzNSSZndqTJJlmABnWxqwwo_2U="
}
# ==============================================================================

QUERY_STR = """
query bookingDetails($input: AccommodationBookingDetailsInput) {
  accommodationBookingDetails(input: $input) {
    roomTotal
    rooms {
      resocId
      resocName
      isBookable
      minPrice
      maxPrice
      resrvUrl
    }
  }
}
"""

def send_telegram(message):
    """텔레그램 메시지 발송 함수"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("❌ [오류] GitHub Secrets에 TELEGRAM_BOT_TOKEN 또는 TELEGRAM_CHAT_ID가 설정되지 않았습니다.")
        return

    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
        res = requests.post(url, json=payload, timeout=10)
        if res.status_code != 200:
            print(f"[텔레그램 응답 에러] {res.status_code}: {res.text}")
    except Exception as e:
        print(f"[텔레그램 전송 중 예외 발생] {e}")

def main():
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 1. 텔레그램 연동 점검용 시작 안내 메시지 발송
    start_msg = (
        f"🤖 [캠핑장 알리미 가동 확인]\n"
        f"일정: {CHECKIN} ~ {CHECKOUT} ({GUEST_COUNT}인)\n"
        f"조회 시간: {now_str}\n"
        f"GitHub Actions 정상 실행 중입니다."
    )
    send_telegram(start_msg)

    # 2. 네이버 예약 실시간 잔여 현황 조회
    payload = [
        {
            "operationName": "bookingDetails",
            "variables": {
                "input": {
                    "businessId": BUSINESS_ID,
                    "isNx": False,
                    "checkin": CHECKIN,
                    "checkout": CHECKOUT,
                    "entry": "bmp",
                    "guest": GUEST_COUNT,
                    "size": 50
                }
            },
            "query": QUERY_STR
        }
    ]

    try:
        res = requests.post(API_URL, headers=HEADERS, cookies=COOKIES, json=payload, timeout=10)

        if res.status_code == 200:
            data = res.json()
            available_rooms = []

            if isinstance(data, list) and len(data) > 0:
                details = data[0].get("data", {}).get("accommodationBookingDetails", {})
                rooms = details.get("rooms", [])

                for r in rooms:
                    room_name = r.get("resocName", "이름 미상")
                    is_bookable = r.get("isBookable", False)
                    min_price = r.get("minPrice", "0")

                    if TARGET_ROOMS and not any(t in room_name for t in TARGET_ROOMS):
                        continue

                    # 예약 가능한 방이 있을 경우 수집
                    if is_bookable:
                        available_rooms.append(f"{room_name} ({min_price}원)")

            if available_rooms:
                room_list_str = "\n".join([f"- {r}" for r in available_rooms])
                success_msg = (
                    f"🎉 [캠핑장 빈자리 발생!]\n"
                    f"일정: {CHECKIN} ~ {CHECKOUT} (인원: {GUEST_COUNT}명)\n\n"
                    f"예약 가능 목록:\n{room_list_str}\n\n"
                    f"확인 시간: {now_str}\n"
                    f"바로가기: https://pcmap.place.naver.com/accommodation/{BUSINESS_ID}/room"
                )
                print(success_msg)
                send_telegram(success_msg)
            else:
                print(f"[{now_str}] [{CHECKIN}~{CHECKOUT}] 전 사이트 매진 상태 (정상 감시 완료)")

        else:
            err_msg = f"⚠️ [조회 실패] HTTP {res.status_code} 오류가 발생했습니다. (쿠키/토큰 만료 확인 필요)"
            print(f"[{now_str}] {err_msg}")
            send_telegram(err_msg)

    except Exception as e:
        print(f"[{now_str}] 통신 오류 발생: {e}")

if __name__ == "__main__":
    main()
