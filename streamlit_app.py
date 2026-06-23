"""Веб-версия (Streamlit) сборщика вакансий — crewell + ukrcrewing + crewdata.

Дизайн: тёмная «глубоководная» тема (навигационный пульт судна) — почти чёрный
навигационный фон + бирюзово-синий акцент, дисплейный шрифт Bricolage Grotesque
поверх технического Spline Sans.

Локальный запуск:   streamlit run streamlit_app.py   (нужен Python 3.10+)
Деплой:             Streamlit Community Cloud, main file — этот файл.
"""
from __future__ import annotations

import logging
from dataclasses import asdict

import streamlit as st

from scraper import catalog
from scraper.excel_writer import workbook_bytes
from scraper.models import COLUMNS
from scraper.runner import collect_all
from scraper.settings import MaritimeZoneSettings, RequestSettings, Settings

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

_CLOUD_SITES = [(label, key) for label, key in catalog.SITES if key != "maritime_zone"]
_POS = {label: kws for label, kws in catalog.POSITIONS}
_VES = {label: kws for label, kws in catalog.VESSEL_TYPES}

# ---------------------------------------------------------------- стиль
_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,500..800&family=Spline+Sans:wght@400;500;600;700&family=Spline+Sans+Mono:wght@400;500&display=swap');

:root{
  --bg:#0a0f1a; --panel:#111a2b; --panel-2:#0c1322;
  --accent:#36e0c8; --accent-2:#3d7bff; --text:#e6eef6; --muted:#8a9bb0;
  --border:rgba(120,160,200,.14);
}

.stApp{
  background:
    radial-gradient(1100px 560px at 12% -8%, rgba(54,224,200,.13), transparent 60%),
    radial-gradient(900px 480px at 112% 2%, rgba(61,123,255,.12), transparent 55%),
    var(--bg);
  color:var(--text);
}
html, body, [data-testid="stAppViewContainer"], .stApp,
.stMarkdown, p, label, span, div, input, button, textarea{
  font-family:'Spline Sans', sans-serif;
}
h1, h2, h3, h4, .hero-title{
  font-family:'Bricolage Grotesque', sans-serif; letter-spacing:-.02em;
}

/* убрать стандартный хром Streamlit, шапку оставить прозрачной (для бургера) */
#MainMenu, [data-testid="stToolbar"], [data-testid="stDecoration"], footer{display:none !important;}
[data-testid="stHeader"]{background:transparent;}
.block-container{padding-top:2.4rem; padding-bottom:3rem; max-width:1120px;}

/* герой */
.hero{animation:rise .7s cubic-bezier(.2,.7,.2,1) both;}
.hero-title{font-size:clamp(2.1rem,5vw,3.4rem); font-weight:800; line-height:1.03; margin:0;}
.hero-title .grad{
  background:linear-gradient(95deg,var(--accent),var(--accent-2));
  -webkit-background-clip:text; background-clip:text; color:transparent;
}
.hero-sub{color:var(--muted); font-size:1.05rem; margin-top:.6rem; max-width:60ch;}
.chips{display:flex; gap:.5rem; flex-wrap:wrap; margin-top:1rem;}
.chip{
  font-size:.78rem; color:var(--accent); border:1px solid var(--border);
  background:rgba(54,224,200,.06); padding:.3rem .75rem; border-radius:999px;
  font-weight:500; letter-spacing:.01em;
}
@keyframes rise{from{opacity:0; transform:translateY(14px)} to{opacity:1; transform:none}}

/* боковая панель */
[data-testid="stSidebar"]{
  background:linear-gradient(180deg,#0c1322,#0a0f1a); border-right:1px solid var(--border);
}
[data-testid="stSidebar"] h2{font-size:1.05rem; margin-bottom:.2rem;}

/* кнопки */
.stButton>button, .stDownloadButton>button{
  border-radius:12px; font-weight:600; border:1px solid var(--border);
  transition:transform .15s ease, box-shadow .25s ease, border-color .2s ease;
}
.stButton>button[kind="primary"]{
  background:linear-gradient(95deg,var(--accent),var(--accent-2)); color:#04121a;
  border:0; box-shadow:0 8px 26px rgba(54,224,200,.28);
}
.stButton>button:hover, .stDownloadButton>button:hover{
  transform:translateY(-2px); box-shadow:0 12px 30px rgba(54,224,200,.30); border-color:var(--accent);
}

/* поля ввода / селекты */
[data-baseweb="select"]>div, .stTextInput input, .stNumberInput input{border-radius:10px !important;}

/* таблица результатов */
[data-testid="stDataFrame"]{border:1px solid var(--border); border-radius:14px; overflow:hidden;}

/* плашка результата */
.result-bar{
  display:flex; align-items:baseline; gap:.7rem; background:var(--panel);
  border:1px solid var(--border); border-radius:14px; padding:1rem 1.2rem; margin:.2rem 0 1.1rem;
}
.result-bar .n{font-family:'Spline Sans Mono',monospace; font-size:1.7rem; color:var(--accent); font-weight:600;}
.result-bar .t{color:var(--muted);}

/* пустое состояние */
.empty{
  border:1px dashed var(--border); border-radius:16px; padding:2.2rem 1.4rem; margin-top:.6rem;
  text-align:center; color:var(--muted); background:rgba(17,26,43,.4);
}
.empty .big{font-size:2.2rem; margin-bottom:.4rem;}
</style>
"""

_HERO = """
<div class="hero">
  <div class="hero-title">Поиск вакансий <span class="grad">моряков</span></div>
  <div class="hero-sub">Фильтр по должности и типу судна. Результат — таблица со
  ссылками на вакансии и выгрузка в Excel.</div>
  <div class="chips">
    <span class="chip">crewell.net</span>
    <span class="chip">ukrcrewing.com.ua</span>
    <span class="chip">crewdata.com</span>
  </div>
</div>
"""


class _StatusLogHandler(logging.Handler):
    def __init__(self, status):
        super().__init__()
        self.status = status

    def emit(self, record):
        try:
            self.status.write(self.format(record))
        except Exception:  # noqa: BLE001
            pass


def _keywords(selected_labels, mapping, extra_text):
    kws = [k for lbl in selected_labels for k in mapping[lbl]]
    kws += [t.strip() for t in (extra_text or "").split(",") if t.strip()]
    return kws


def _run(settings: Settings):
    handler = _StatusLogHandler(None)
    handler.setFormatter(logging.Formatter("%(asctime)s  %(message)s", datefmt="%H:%M:%S"))
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    with st.status("Собираю вакансии…", expanded=True) as status:
        handler.status = status
        root.addHandler(handler)
        try:
            vacs = collect_all(settings)
        finally:
            root.removeHandler(handler)
        status.update(label=f"Готово: найдено {len(vacs)}", state="complete", expanded=False)
    return vacs


def _sidebar_controls():
    with st.sidebar:
        st.markdown("## ⚓ Параметры поиска")
        pos_labels = st.multiselect("Должности", list(_POS), placeholder="любые")
        pos_extra = st.text_input("Добавить должности", "", placeholder="через запятую")
        ves_labels = st.multiselect("Типы судов", list(_VES), placeholder="любые")
        ves_extra = st.text_input("Добавить типы судов", "", placeholder="через запятую")
        site_labels = st.multiselect("Сайты", [l for l, _ in _CLOUD_SITES],
                                     default=[l for l, _ in _CLOUD_SITES])
        c1, c2 = st.columns([1, 1])
        with c1:
            limit = st.number_input("Лимит страниц", min_value=0, max_value=200, value=5, step=1,
                                    help="0 = все страницы (может быть долго)")
        with c2:
            details = st.checkbox("Детали", value=True, help="Больше информации, но медленнее")
        go = st.button("▶ Начать поиск", type="primary", use_container_width=True)
        st.caption("maritime-zone — в десктоп-версии (.exe): из облака его блокирует Cloudflare.")
        return {
            "go": go, "site_labels": site_labels, "limit": int(limit), "details": details,
            "positions": _keywords(pos_labels, _POS, pos_extra),
            "vessels": _keywords(ves_labels, _VES, ves_extra),
        }


def main() -> None:
    st.set_page_config(page_title="Поиск вакансий моряков", page_icon="⚓",
                       layout="wide", initial_sidebar_state="expanded")
    st.markdown(_CSS, unsafe_allow_html=True)
    st.markdown(_HERO, unsafe_allow_html=True)

    f = _sidebar_controls()

    if f["go"]:
        sites = [key for label, key in _CLOUD_SITES if label in f["site_labels"]]
        if not sites:
            st.error("Выберите хотя бы один сайт.")
            st.stop()
        if f["limit"] == 0:
            st.warning("Лимит 0 = все страницы: сбор может занять несколько минут.")
        settings = Settings(
            positions=f["positions"], vessel_types=f["vessels"], sites=sites,
            request=RequestSettings(max_pages_per_site=f["limit"], fetch_details=f["details"]),
            maritime_zone=MaritimeZoneSettings(enabled=False),
        )
        try:
            vacs = _run(settings)
        except Exception as exc:  # noqa: BLE001
            st.error(f"Ошибка сбора: {exc}")
            st.stop()
        st.session_state["vacancies"] = vacs
        st.session_state["xlsx"] = workbook_bytes(vacs) if vacs else b""

    _render_results()


def _render_results() -> None:
    vacs = st.session_state.get("vacancies")
    if vacs is None:
        st.markdown(
            '<div class="empty"><div class="big">🧭</div>'
            'Задайте фильтры слева и нажмите <b>«Начать поиск»</b>.<br>'
            'Пустой фильтр = все вакансии с выбранных сайтов.</div>',
            unsafe_allow_html=True)
        return
    if not vacs:
        st.info("Подходящих вакансий не найдено. Ослабьте фильтры или добавьте сайты.")
        return

    st.markdown(
        f'<div class="result-bar"><span class="n">{len(vacs)}</span>'
        f'<span class="t">вакансий найдено</span></div>', unsafe_allow_html=True)
    st.download_button("⬇ Скачать Excel", data=st.session_state["xlsx"],
                       file_name="vacancies.xlsx", mime=XLSX_MIME)
    records = [{label: asdict(v).get(key) for key, label in COLUMNS} for v in vacs[:300]]
    st.dataframe(
        records, use_container_width=True, hide_index=True,
        column_config={"Ссылка": st.column_config.LinkColumn("Ссылка", display_text="открыть")},
    )
    if len(vacs) > 300:
        st.caption(f"Показаны первые 300 из {len(vacs)} — полный список в Excel-файле.")


if __name__ == "__main__":
    main()
