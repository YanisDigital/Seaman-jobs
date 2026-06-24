"""Веб-версия (Streamlit) сборщика вакансий — crewell + ukrcrewing.

Локальный запуск:   streamlit run streamlit_app.py
Деплой:             Streamlit Community Cloud (share.streamlit.io), main file —
                    этот файл. maritime-zone в облаке не используется (Cloudflare),
                    он доступен в десктоп-версии (.exe).
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

# Сайты только для десктоп-версии (.exe) — в облако не выводим.
# maritime_zone требует браузер (Cloudflare), поэтому остаётся вне облака.
_DESKTOP_ONLY = {"maritime_zone"}
_CLOUD_SITES = [(label, key) for label, key in catalog.SITES if key not in _DESKTOP_ONLY]
_POS = {label: kws for label, kws in catalog.POSITIONS}
_VES = {label: kws for label, kws in catalog.VESSEL_TYPES}


class _StatusLogHandler(logging.Handler):
    """Пишет строки лога в виджет st.status (живой прогресс)."""

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
    """Собрать вакансии, показывая живой лог в st.status."""
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


def main() -> None:
    st.set_page_config(page_title="Поиск вакансий моряков", page_icon="⚓", layout="wide")
    st.title("⚓ Поиск вакансий моряков")
    st.caption("Отметьте должности и типы судов, выберите сайты и нажмите «Старт». "
               "Результат — таблица и файл Excel со ссылками.")

    col1, col2 = st.columns(2)
    with col1:
        pos_labels = st.multiselect("Должности", list(_POS), placeholder="любые")
        pos_extra = st.text_input("Добавить должности (через запятую)", "")
    with col2:
        ves_labels = st.multiselect("Типы судов", list(_VES), placeholder="любые")
        ves_extra = st.text_input("Добавить типы судов (через запятую)", "")

    site_labels = st.multiselect("Сайты", [l for l, _ in _CLOUD_SITES],
                                 default=[l for l, _ in _CLOUD_SITES])
    st.caption("maritime-zone доступен в десктоп-версии (.exe) — в облаке он отключён "
               "из-за защиты Cloudflare.")

    c1, c2 = st.columns(2)
    with c1:
        limit = st.number_input("Лимит страниц с сайта (0 = все)",
                                min_value=0, max_value=200, value=5, step=1)
    with c2:
        details = st.checkbox("Грузить детали (больше информации, медленнее)", value=True)
    if limit == 0:
        st.warning("0 = все страницы: сбор может занять несколько минут.")

    if st.button("▶ Старт", type="primary"):
        sites = [key for label, key in _CLOUD_SITES if label in site_labels]
        if not sites:
            st.error("Выберите хотя бы один сайт.")
            st.stop()
        positions = _keywords(pos_labels, _POS, pos_extra)
        vessels = _keywords(ves_labels, _VES, ves_extra)
        settings = Settings(
            positions=positions, vessel_types=vessels, sites=sites,
            request=RequestSettings(max_pages_per_site=int(limit), fetch_details=details),
            maritime_zone=MaritimeZoneSettings(enabled=False),
        )
        try:
            vacs = _run(settings)
        except Exception as exc:  # noqa: BLE001
            st.error(f"Ошибка сбора: {exc}")
            st.stop()
        st.session_state["vacancies"] = vacs
        st.session_state["xlsx"] = workbook_bytes(vacs) if vacs else b""

    # --- результаты (сохраняются между перерисовками) ---
    vacs = st.session_state.get("vacancies")
    if vacs is not None:
        if not vacs:
            st.info("Подходящих вакансий не найдено. Ослабьте фильтры или добавьте сайты.")
            return
        st.success(f"Найдено вакансий: {len(vacs)}")
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
