from homeassistant.const import Platform

DOMAIN = "svitlo_live"

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.CALENDAR,
]

# Фіксований інтервал опитування (сек)
DEFAULT_SCAN_INTERVAL = 900  # 15 хв

CONF_REGION = "region"
CONF_QUEUE = "queue"

# Оновлений список (Херсонська прибрана)
REGIONS = {
    "cherkaska-oblast": "Черкаська область",
    "chernigivska-oblast": "Чернігівська область",
    "chernivetska-oblast": "Чернівецька область",
    "dnipropetrovska-oblast": "Дніпропетровська область",
    "donetska-oblast": "Донецька область",
    "harkivska-oblast": "Харківська область",
    # "hersonska-oblast": "Херсонська область",  # виключена
    "hmelnitska-oblast": "Хмельницька область",
    "ivano-frankivska-oblast": "Івано-Франківська область",
    "kirovogradska-oblast": "Кіровоградська область",
    "kyiv": "Київ",
    "kiivska-oblast": "Київська область",
    "lvivska-oblast": "Львівська область",
    "mikolaivska-oblast": "Миколаївська область",
    "odeska-oblast": "Одеська область",
    "poltavska-oblast": "Полтавська область",
    "rivnenska-oblast": "Рівненська область",
    "sumska-oblast": "Сумська область",
    "ternopilska-oblast": "Тернопільська область",
    "vinnitska-oblast": "Вінницька область",
    "volinska-oblast": "Волинська область",
    "zakarpatska-oblast": "Закарпатська область",
    "zaporizka-oblast": "Запорізька область",
    "jitomirska-oblast": "Житомирська область",
}

# Мапа режимів вибору черги/групи
REGION_QUEUE_MODE = {
    "chernivetska-oblast": "GRUPA_NUM",
    "donetska-oblast": "GRUPA_NUM",
}

# Публічний URL твого Cloudflare Worker (без секретів)
API_URL = "https://svitlo-proxy.svitlo-proxy.workers.dev"
