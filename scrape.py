#!/usr/bin/env python3
"""
토스 무이자 할부 안내 이미지 자동 갱신
매월 첫 영업일(한국 공휴일 반영)에 실행됨.
FORCE=1 환경변수로 게이트 우회 (초기 테스트용).
"""
import datetime
import os
import sys

import holidays
import requests
from playwright.sync_api import sync_playwright

TARGET_URL = "https://consumer.tosspayments.com/notice/free-installment"
IMAGE_FILTER = "static.toss.im/faq/live"
OUTPUT_PATH = "docs/installment.png"
LAST_UPDATED_PATH = "docs/last-updated.txt"

KST = datetime.timezone(datetime.timedelta(hours=9))


def first_biz_day(year: int, month: int) -> datetime.date:
    kr = holidays.SouthKorea(years=year)
    d = datetime.date(year, month, 1)
    while d.weekday() >= 5 or d in kr:  # 토=5, 일=6
        d += datetime.timedelta(days=1)
    return d


def is_first_biz_day() -> bool:
    today = datetime.datetime.now(KST).date()
    return today == first_biz_day(today.year, today.month)


def scrape_image_url() -> str | None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        print(f"Loading {TARGET_URL} ...")
        page.goto(TARGET_URL, wait_until="networkidle", timeout=60_000)
        # 스크롤로 lazy-load 트리거
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(2_000)
        src = page.evaluate(f"""
            Array.from(document.querySelectorAll('img'))
                 .map(e => e.src)
                 .find(s => s.includes('{IMAGE_FILTER}'))
        """)
        browser.close()
    return src


def download(url: str, dest: str):
    print(f"Downloading {url}")
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "wb") as f:
        f.write(r.content)
    print(f"Saved → {dest} ({len(r.content):,} bytes)")


def write_meta(url: str):
    now = datetime.datetime.now(KST).strftime("%Y-%m-%d %H:%M KST")
    with open(LAST_UPDATED_PATH, "w", encoding="utf-8") as f:
        f.write(f"updated: {now}\nsource: {url}\n")


def self_check():
    """2026년 각 달 첫 영업일이 주말·공휴일 아닌지 확인."""
    kr = holidays.SouthKorea(years=2026)
    for m in range(1, 13):
        d = first_biz_day(2026, m)
        assert d.weekday() < 5, f"2026-{m:02d}: {d} is weekend"
        assert d not in kr, f"2026-{m:02d}: {d} is holiday ({kr[d]})"
    print("self_check passed")


if __name__ == "__main__":
    if "--self-check" in sys.argv:
        self_check()
        sys.exit(0)

    force = os.environ.get("FORCE", "").lower() in ("1", "true", "yes")
    if not force and not is_first_biz_day():
        today = datetime.datetime.now(KST).date()
        fbd = first_biz_day(today.year, today.month)
        print(f"오늘({today})은 이번 달 첫 영업일({fbd})이 아님. skip.")
        sys.exit(0)

    src = scrape_image_url()
    if not src:
        print(
            "ERROR: static.toss.im/faq/live 이미지 못 찾음. 페이지 구조 변경 확인 필요.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Found: {src}")
    download(src, OUTPUT_PATH)
    write_meta(src)
    print("Done.")
