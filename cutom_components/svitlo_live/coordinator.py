# custom_components/svitlo_live/coordinator.py
from __future__ import annotations

import logging
from datetime import datetime, timedelta, date
from typing import Any, Tuple, Optional

import aiohttp
from bs4 import BeautifulSoup

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    CONF_REGION,
    CONF_QUEUE,
    CONF_SCAN_INTERVAL,
    CLASS_MAP,
    DEFAULT_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)
HEADERS = {"User-Agent": "Mozilla/5.0 (HomeAssistant; svitlo_live)"}


class SvitloCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Координатор: тягне HTML svitlo.live, парсить on/off/f4/f5, розкладає у 48 півгодин."""

    def __init__(self, hass: HomeAssistant, config: dict[str, Any]) -> None:
        self.hass = hass
        self.region: str = config[CONF_REGION]
        self.queue: str = config[CONF_QUEUE]

        scan_seconds = int(config.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))

        # Планувальник точного перемикання
        self._unsub_precise = None  # type: ignore[assignment]

        # Кеш розкладу (на випадок точного перемикання без мережі)
        self._today_pack_cached: Optional[Tuple[date, list[str], list[str]]] = None
        self._tomorrow_pack_cached: Optional[Tuple[date, list[str], list[str]]] = None

        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name=f"svitlo_live_{self.region}_{self.queue}",
            update_interval=timedelta(seconds=scan_seconds),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Основне оновлення: фетч HTML і побудова payload."""
        url = f"https://svitlo.live/{self.region}"
        polled_at = dt_util.utcnow().replace(microsecond=0).isoformat()  # час ОСТАННЬОГО ОПИТУВАННЯ

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=HEADERS, timeout=20) as resp:
                    if resp.status != 200:
                        raise UpdateFailed(f"HTTP {resp.status} for {url}")
                    html = await resp.text()
        except Exception as e:
            raise UpdateFailed(f"Network error: {e}") from e

        try:
            today_pack, tomorrow_pack, source_last_modified = self.parse_queue(html, self.queue)
            # Кешуємо актуальні пакети
            self._today_pack_cached = today_pack
            self._tomorrow_pack_cached = tomorrow_pack
        except Exception as e:
            raise UpdateFailed(f"Parse error: {e}") from e

        payload = self._build_payload(
            today_pack=today_pack,
            tomorrow_pack=tomorrow_pack,
            updated=polled_at,
            source_url=url,
            source_last_modified=source_last_modified,
        )

        # Плануємо точне оновлення на межі наступного 30-хв слоту
        self._schedule_precise_refresh(payload)
        return payload

    # ---------------------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------------------

    def _build_payload(
        self,
        today_pack: Tuple[date, list[str], list[str]],
        tomorrow_pack: Optional[Tuple[date, list[str], list[str]]],
        updated: str,
        source_url: str,
        source_last_modified: Optional[str],
    ) -> dict[str, Any]:
        """Будує словник даних для сенсорів із двох таблиць (сьогодні/завтра)."""
        today_date, hour_classes, halfhours = today_pack  # hour_classes: 24 значень on/off/f4/f5, halfhours: 48 значень on/off

        now_local = dt_util.now()
        # Індекс поточного півгодинного слоту
        if now_local.date() != today_date:
            idx = 0
        else:
            idx = now_local.hour * 2 + (1 if now_local.minute >= 30 else 0)

        # Поточний стан (on/off) із 30-хв масиву
        cur = halfhours[idx]

        # Наступна зміна стану в межах 48-слотної доби
        nci = self.next_change_idx(halfhours, idx)
        next_change_hhmm = None
        if nci is not None:
            h = nci // 2
            m = 30 if (nci % 2) else 0
            next_change_hhmm = f"{h:02d}:{m:02d}"

        # Вираховуємо наступні ключові моменти (вирівняні до кордонів 00/30)
        next_on_at = self.find_next_at(["on"], today_date, halfhours, idx, tomorrow_pack)
        next_off_at = self.find_next_at(["off"], today_date, halfhours, idx, tomorrow_pack)

        data: dict[str, Any] = {
            "queue": self.queue,
            "date": today_date.isoformat(),
            "now_status": cur,                      # "on"/"off" з 30-хв сітки
            "now_halfhour_index": idx,
            "next_change_at": next_change_hhmm,     # "HH:MM" (локальний)
            "today_24h_classes": hour_classes,      # оригінальні класи по годинах: on/off/f4/f5
            "today_48half": halfhours,              # 48 значень "on"/"off"
            "updated": updated,                     # час останнього ОПИТУВАННЯ (UTC ISO)
            "source": source_url,
            "source_last_modified": source_last_modified,  # як є, інформативно
            "next_on_at": next_on_at,               # ISO UTC або None
            "next_off_at": next_off_at,             # ISO UTC або None
        }

        if tomorrow_pack:
            d2, hc2, hh2 = tomorrow_pack
            data.update(
                {
                    "tomorrow_date": d2.isoformat(),
                    "tomorrow_24h_classes": hc2,
                    "tomorrow_48half": hh2,
                }
            )

        return data

    def _schedule_precise_refresh(self, data: dict[str, Any]) -> None:
        """Ставимо таймер на точний перехід до наступного півгодинного слоту за графіком."""
        # Скасувати попереднє планування, якщо було
        if self._unsub_precise:
            self._unsub_precise()
            self._unsub_precise = None

        next_change_hhmm = data.get("next_change_at")
        base_date_iso = data.get("date")
        if not next_change_hhmm or not base_date_iso:
            return

        try:
            base_day = datetime.fromisoformat(base_date_iso).date()
            hh, mm = [int(x) for x in next_change_hhmm.split(":")]

            candidate = dt_util.now().replace(
                year=base_day.year,
                month=base_day.month,
                day=base_day.day,
                hour=hh,
                minute=mm,
                second=0,
                microsecond=0,
            )
            # Якщо вже в минулому (зсунулися дати/години) — перенести на +1 день
            if candidate <= dt_util.now():
                candidate = candidate + timedelta(days=1)

            @callback
            def _precise_tick(_now) -> None:
                # 1) миттєво оновлюємо з КЕШУ (без мережі), updated НЕ змінюємо
                if self._today_pack_cached:
                    payload = self._build_payload(
                        today_pack=self._today_pack_cached,
                        tomorrow_pack=self._tomorrow_pack_cached,
                        updated=self.data.get("updated")
                        if self.data
                        else dt_util.utcnow().replace(microsecond=0).isoformat(),
                        source_url=self.data.get("source") if self.data else "",
                        source_last_modified=self.data.get("source_last_modified")
                        if self.data
                        else None,
                    )
                    self.async_set_updated_data(payload)
                # 2) слідом просимо мережевий refresh (він уже оновить updated)
                self.async_request_refresh()

            self._unsub_precise = async_track_point_in_time(self.hass, _precise_tick, candidate)
            _LOGGER.debug(
                "Scheduled precise refresh for %s/%s at %s",
                self.region,
                self.queue,
                candidate.isoformat(),
            )
        except Exception as e:
            _LOGGER.debug("Failed to schedule precise refresh: %s", e)

    # ---------------------- Parsing & time logic ----------------------

    @staticmethod
    def halfhours_from_hour_class(cls: str) -> list[str]:
        """on/off/f4/f5 → два півгодинні стани ('on' або 'off')."""
        if cls == "on":
            return ["on", "on"]
        if cls == "off":
            return ["off", "off"]
        if cls == "f4":  # перша половина off (00–29), друга on (30–59)
            return ["off", "on"]
        if cls == "f5":  # перша половина on (00–29), друга off (30–59)
            return ["on", "off"]
        # Якщо раптом несподіваний клас — трактуємо як on-on
        return ["on", "on"]

    @staticmethod
    def parse_queue(html: str, queue_id: str):
        """Парсимо блок div#chergraX.Y, беремо 2 таблиці (сьогодні/завтра)."""
        soup = BeautifulSoup(html, "html.parser")
        tab = soup.find("div", id=f"chergra{queue_id}")
        if not tab:
            raise ValueError(f"Queue {queue_id} not found (div#chergra{queue_id})")

        tables = tab.select("table.graph")
        if not tables:
            raise ValueError("No tables found in queue tab")

        def parse_table(table) -> Tuple[date, list[str], list[str]]:
            rows = table.select("tbody tr")
            if len(rows) < 2:
                raise ValueError("Table structure unexpected (need 2 rows)")

            # Заголовок: дата + 24 колонки часу
            header_tds = rows[0].find_all("td")
            date_str = header_tds[0].get_text(strip=True)
            day = datetime.strptime(date_str, "%d.%m.%Y").date()

            # Рядок 'Черга X.Y' із 24 cell по годинах
            cells = rows[1].find_all("td")[1:]
            if len(cells) != 24:
                # інколи сайт може показати менше/більше — страховка
                cells = cells[:24]

            hour_classes: list[str] = []
            for td in cells:
                cls = next((c for c in td.get("class", []) if c in CLASS_MAP), "on")
                hour_classes.append(cls)

            # Розкладаємо 24 години → 48 півгодинок
            halfhours: list[str] = []
            for cls in hour_classes:
                halfhours.extend(SvitloCoordinator.halfhours_from_hour_class(cls))

            return day, hour_classes, halfhours

        today_pack = parse_table(tables[0])
        tomorrow_pack = parse_table(tables[1]) if len(tables) > 1 else None

        # meta name="last-modified" (може бути, беремо як інформаційний)
        meta = soup.find("meta", attrs={"name": "last-modified"})
        source_last_modified = meta["content"] if meta and meta.has_attr("content") else None
        if source_last_modified and "-" in source_last_modified and ":" in source_last_modified:
            # Перекладаємо у UTC ISO, якщо це локальний час
            try:
                dt_local = datetime.fromisoformat(source_last_modified.replace(" ", "T"))
                source_last_modified = dt_util.as_utc(dt_local).replace(microsecond=0).isoformat()
            except Exception:
                pass

        return today_pack, tomorrow_pack, source_last_modified

    @staticmethod
    def next_change_idx(series: list[str], idx: int) -> Optional[int]:
        """Знайти індекс наступної зміни стану в 30-хв серії (циклічно в межах доби)."""
        cur = series[idx]
        n = len(series)
        for step in range(1, n + 1):
            j = (idx + step) % n
            if series[j] != cur:
                return j
        return None

    @staticmethod
    def find_next_at(
        target_states: list[str],
        base_date: date,
        today_half: list[str],
        idx: int,
        tomorrow_pack: Optional[Tuple[date, list[str], list[str]]],
    ) -> Optional[str]:
        """
        Повертає UTC ISO час НАСТУПНОГО target-стану ("on"/"off"),
        ВИРІВНЯНИЙ до межі півгодини (:00 або :30) від поточного слоту.
        """
        # Починаємо пошук від НАСТУПНОГО півгодинного слоту
        seq = today_half[idx + 1 :] + today_half[: idx + 1]
        seq2 = list(seq)
        if tomorrow_pack:
            _, _, tomorrow_half = tomorrow_pack
            seq2.extend(tomorrow_half)

        pos = next((i for i, s in enumerate(seq2) if s in target_states), None)
        if pos is None:
            return None

        # Вирівнюємо "базу" до початку поточного слоту локального часу
        now_local = dt_util.now().replace(second=0, microsecond=0)
        minute_block_start = 0 if now_local.minute < 30 else 30
        base_aligned = now_local.replace(minute=minute_block_start)

        # Додаємо (pos+1) слотів по 30 хвилин
        next_local = base_aligned + timedelta(minutes=(pos + 1) * 30)

        # Віддаємо як ISO в UTC (HA сам покаже у локалі)
        return dt_util.as_utc(next_local).isoformat()
