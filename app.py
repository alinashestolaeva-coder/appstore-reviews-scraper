import re
import time
import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="App Store Reviews Scraper", layout="wide")
st.title("Сбор отзывов из App Store для продуктового анализа")
st.caption(
    "Введите ID приложения (например, 570060128 для Duolingo) или ссылку на"
    " страницу в App Store."
)


def extract_app_id(user_input: str) -> str | None:
  text = user_input.strip()
  if text.isdigit():
    return text
  match = re.search(r"id(\d+)", text)
  return match.group(1) if match else None


def fetch_reviews(app_id: str, country: str = "us", max_pages: int = 10):
  reviews = []
  headers = {"User-Agent": "Mozilla/5.0 (compatible; ProductResearchBot/1.0)"}
  progress = st.progress(0)
  status = st.empty()

  for page in range(1, max_pages + 1):
    status.text(f"Загружаем страницу {page} из {max_pages}...")
    url = f"https://itunes.apple.com/{country}/rss/customerreviews/page={page}/id={app_id}/sortby=mostrecent/json"
    try:
      resp = requests.get(url, headers=headers, timeout=15)
      resp.raise_for_status()
      data = resp.json()
    except requests.exceptions.RequestException as e:
      st.warning(f"Ошибка запроса на странице {page}: {e}")
      break
    except ValueError:
      st.warning(f"Ошибка чтения JSON на странице {page}.")
      break

    entries = data.get("feed", {}).get("entry", [])
    if isinstance(entries, dict):
      entries = [entries]

    page_items = []
    for item in entries:
      if "im:rating" not in item:
        continue
      try:
        rating = int(item.get("im:rating", {}).get("label", ""))
      except (ValueError, TypeError):
        rating = None

      page_items.append({
          "review_id": item.get("id", {}).get("label", ""),
          "date": item.get("updated", {}).get("label", ""),
          "rating": rating,
          "app_version": item.get("im:version", {}).get("label", ""),
          "author": item.get("author", {}).get("name", {}).get("label", ""),
          "title": item.get("title", {}).get("label", ""),
          "review_text": item.get("content", {}).get("label", ""),
      })

    if not page_items:
      break

    reviews.extend(page_items)
    progress.progress(min(page / max_pages, 1.0))
    time.sleep(0.4)

  status.empty()
  progress.empty()
  return reviews


col1, col2, col3 = st.columns([3, 1, 1])
with col1:
  raw_input = st.text_input(
      "ID или ссылка App Store", value="570060128"
  )
with col2:
  country = st.text_input("Страна (код)", value="us").lower().strip()
with col3:
  max_pages = st.slider(
      "Макс. страниц", min_value=1, max_value=10, value=5
  )

if st.button("Собрать отзывы", type="primary"):
  app_id = extract_app_id(raw_input)
  if not app_id:
    st.error(
        "Не удалось распознать ID приложения. Укажите числовой ID или ссылку"
        " с `id<номер>`."
    )
  else:
    data = fetch_reviews(app_id=app_id, country=country, max_pages=max_pages)
    if not data:
      st.info(
          "Отзывы не найдены. Проверьте ID приложения или код региона."
      )
    else:
      df = (
          pd.DataFrame(data)
          .drop_duplicates(subset=["review_id"])
          .reset_index(drop=True)
      )
      st.success(f"Собрано уникальных отзывов: {len(df)}")

      m1, m2 = st.columns(2)
      m1.metric("Всего отзывов", len(df))
      avg_rating = df["rating"].dropna().mean()
      m2.metric(
          "Средняя оценка",
          f"{avg_rating:.2f}" if pd.notna(avg_rating) else "—",
      )

      st.dataframe(df, use_container_width=True)

      csv_bytes = df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
      st.download_button(
          label="Скачать CSV",
          data=csv_bytes,
          file_name=f"reviews_{app_id}_{country}.csv",
          mime="text/csv",
      )
