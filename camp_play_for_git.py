import os
import time
import base64
import json
import requests
from datetime import datetime

# ==============================================================================
# [설정 영역]
# ==============================================================================
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# 감시할 캠핑장 및 일정 목록 (원하는 만큼 추가 가능)
TARGET_CAMPS = [
    {
        "name": "캠핑장 A (현재 타깃)",
        "business_id": "1734741351",
        "checkin": "20261031",
        "checkout": "20261101",
        "guest": "3",
        "target_rooms": []  # 특정 객실 키워드 (비워두면 전 객실)
    },
    # 추가하고 싶은 다른 캠핑장이 있다면 아래 양식대로 추가
    # {
    #     "name": "캠핑장 B",
    #     "business_id": "다른_캠핑장_ID",
    #     "checkin": "20261031",
    #     "checkout": "20261101",
    #     "guest": "3",
    #     "target_rooms": []
    # }
]

API_URL = "https://pcmap-api.place.naver.com/graphql"

# 공통 인증 토큰 및 쿠키
NCAPTCHA_TOKEN = "vlo81NKHruvDQS2rmYnv-7n6OsJS4QqJgZQElQlqIpc="

COOKIES = {
    "NNB": "VX52JPMD3SYWO",
    "ASID": "79b947de000001955465dc430000004e",
    "NAC": "YRxXBgw1AXRs",
    "PLACE_LANGUAGE": "ko",
    "page_uid": "jWoM7lqX5EwssmLKHfh-075009",
    "NLPA": "1051930d-96b2-4315-be78-27f7b64c46a4",
    "BUC": "E-8i2j8KKLO8FSfb_jzNSSZndqTJJlmABnWxqwwo_2U="
}

QUERY_STR = """
query bookingDetails($input: AccommodationBookingDetailsInput) {
  accommodationBookingDetails(input: $input) {
    rooms {
      resocName
      isBookable
      minPrice
    }
  }
}
"""
# ==============================================================================

def make_graphql_header(biz_id):
    """비즈니스 ID에 맞춰 x-wtm-graphql Base64 헤더 자동 생성"""
    raw_dict = {
        "arg": str(biz_id),
        "type": "accommodation",
        "source": "place"
    }
    encoded = base64.b64encode(json.dumps(raw_dict, separators=(',', ':')).encode('utf-8')).decode('utf-8')
    return encoded

def send_telegram(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"[텔레그램 전송 에러] {e}")

def check_single_camp(camp_info):
    name = camp_info["name"]
    biz_id = camp_info["business_id"]
    checkin = camp_info["checkin"]
    checkout = camp_info["checkout"]
    guest = camp_info["guest"]
    target_rooms = camp_info.get("target_rooms", [])

    # 각 캠핑장별 개별 동적 헤더 구성
    headers = {
        "accept": "*/*",
        "accept-language": "ko",
        "content-type": "application/json",
        "origin": "https://pcmap.place.naver.com",
        "priority": "u=1, i",
        "referer": f"https://pcmap.place.naver.com/accommodation/{biz_id}/room?from=map&svcName=map_pcv5&guest={guest}&checkin={checkin}&checkout={checkout}",
        "sec-ch-ua": '"Microsoft Edge";v="155", "Chromium";v="155", "Not(A:Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-site",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36 Edg/155.0.0.0",
        "x-wtm-graphql": make_graphql_header(biz_id),
        "x-wtm-ncaptcha-token": NCAPTCHA_TOKEN
    }

    payload = [
        {
            "operationName": "bookingDetails",
            "variables": {
                "input": {
                    "businessId": str(biz_id),
                    "isNx": False,
                    "checkin": checkin,
                    "checkout": checkout,
                    "entry": "bmp",
                    "guest": guest,
                    "size": 50
                }
            },
            "query": QUERY_STR
        }
    ]

    try:
        res = requests.post(API_URL, headers=headers, cookies=COOKIES, json=payload, timeout=10)
        if res.status_code == 200:
            data = res.json()
            available = []
            if isinstance(data, list) and len(data) > 0:
                details = data[0].get("data", {}).get("accommodationBookingDetails", {})
                for r in details.get("rooms", []):
                    r_name = r.get("resocName", "이름 미상")
                    if target_rooms and not any(t in r_name for t in target_rooms):
                        continue
                    if r.get("isBookable", False):
                        available.append(f"{r_name} ({r.get('minPrice', '0')}원)")

            if available:
                rooms_txt = "\n".join([f"- {item}" for item in available])
                msg = (
                    f"🎉 [{name} 빈자리 발견!]\n"
                    f"일정: {checkin} ~ {checkout} ({guest}인)\n\n"
                    f"예약 가능 목록:\n{rooms_txt}\n\n"
                    f"예약 링크: https://pcmap.place.naver.com/accommodation/{biz_id}/room"
                )
                print(msg)
                send_telegram(msg)
            else:
                print(f"[{name}] {checkin}~{checkout}: 전 사이트 매진")
        else:
            print(f"[{name}] HTTP 상태 오류: {res.status_code}")
    except Exception as e:
        print(f"[{name}] 조회 중 예외 발생: {e}")

def main():
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now_str}] 총 {len(TARGET_CAMPS)}개 캠핑장 일괄 점검 시작")

    for camp in TARGET_CAMPS:
        check_single_camp(camp)
        time.sleep(1.5)  # 연속 호출 차단 방지 대기

if __name__ == "__main__":
    main()
