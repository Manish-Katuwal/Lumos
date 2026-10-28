import sys
import random
import requests
from datetime import datetime, timezone, timedelta
import os
from dotenv import load_dotenv

load_dotenv()

from PyQt5.QtCore import (
    Qt, QThread, pyqtSignal, QPointF, QTimer,
    QPropertyAnimation, QEasingCurve
)
from PyQt5.QtGui import QColor, QPainter, QPen, QRadialGradient
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QPushButton,
    QLineEdit, QVBoxLayout, QHBoxLayout, QGridLayout, QFrame,
    QStackedWidget, QListWidget, QListWidgetItem, QMessageBox,
    QGraphicsDropShadowEffect
)

API_KEY = os.getenv("OPENWEATHER_API_KEY")

CURRENT_URL = "https://api.openweathermap.org/data/2.5/weather"
FORECAST_URL = "https://api.openweathermap.org/data/2.5/forecast"


class WeatherWorker(QThread): 
    succeeded = pyqtSignal(dict, dict)
    failed = pyqtSignal(str)

    def __init__(self, city):
        super().__init__()
        self.city = city

    def run(self):
        if not API_KEY or API_KEY == "YOUR_API_KEY_HERE":
            self.failed.emit(
                "Add your OpenWeatherMap API key near the top of weather.py."
            )
            return

        params = {"q": self.city, "appid": API_KEY, "units": "metric"}

        try:
            current_response = requests.get(CURRENT_URL, params=params, timeout=15)
            if current_response.status_code == 401:
                self.failed.emit(
                    "Your API key is invalid or not active yet. Check your "
                    "OpenWeatherMap account and try again."
                )
                return
            if current_response.status_code == 404:
                self.failed.emit(
                    f"I couldn't find '{self.city}'. Check the spelling and try again."
                )
                return
            current_response.raise_for_status()
            current = current_response.json()

            forecast_response = requests.get(FORECAST_URL, params=params, timeout=15)
            forecast_response.raise_for_status()
            forecast = forecast_response.json()

            self.succeeded.emit(current, forecast)

        except requests.Timeout:
            self.failed.emit("The weather service took too long to respond. Try again.")
        except requests.RequestException as error:
            self.failed.emit(
                "Couldn't load weather data. Check your internet connection.\n"
                f"Details: {error}"
            )


class MagicButton(QPushButton):
    """A button with a small violet glow whenever clicked."""
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.PointingHandCursor)

        self.glow = QGraphicsDropShadowEffect(self)
        self.glow.setColor(QColor("#B88AFF"))
        self.glow.setBlurRadius(2)
        self.glow.setOffset(0, 0)
        self.setGraphicsEffect(self.glow)

        self.animation = QPropertyAnimation(self.glow, b"blurRadius", self)
        self.animation.setDuration(420)
        self.animation.setStartValue(2)
        self.animation.setKeyValueAt(0.35, 22)
        self.animation.setEndValue(2)
        self.animation.setEasingCurve(QEasingCurve.OutCubic)
        self.clicked.connect(self.play_effect)

    def play_effect(self):
        self.animation.stop()
        self.animation.start()


class StarBackground(QWidget):
    def __init__(self):
        super().__init__()
        random.seed(17)
        self.stars = [
            (random.random(), random.random(), random.choice([1, 1, 2, 2, 3]))
            for _ in range(100)
        ]

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor("#100C20"))

        for x, y, radius, color in [
            (0.78, 0.12, 360, QColor(123, 57, 220, 46)),
            (0.35, 0.78, 300, QColor(93, 44, 180, 26)),
            (0.96, 0.72, 240, QColor(164, 105, 245, 20)),
        ]:
            gradient = QRadialGradient(
                QPointF(self.width() * x, self.height() * y), radius
            )
            transparent = QColor(color)
            transparent.setAlpha(0)
            gradient.setColorAt(0, color)
            gradient.setColorAt(1, transparent)
            painter.fillRect(self.rect(), gradient)

        for sx, sy, size in self.stars:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(224, 208, 255, 175))
            painter.drawEllipse(
                QPointF(sx * self.width(), sy * self.height()), size, size
            )

        points = [
            QPointF(self.width() * .72, self.height() * .14),
            QPointF(self.width() * .78, self.height() * .20),
            QPointF(self.width() * .84, self.height() * .16),
            QPointF(self.width() * .89, self.height() * .24),
            QPointF(self.width() * .82, self.height() * .30),
        ]
        painter.setPen(QPen(QColor(191, 150, 255, 80), 1.2))
        for i in range(len(points) - 1):
            painter.drawLine(points[i], points[i + 1])
        painter.end()


def make_label(text, size=12, color="#F5EFFF", bold=False):
    item = QLabel(text)
    item.setStyleSheet(
        f"color:{color}; font-size:{size}px; "
        f"font-weight:{'700' if bold else '400'}; background:transparent;"
    )
    return item


def make_card():
    box = QFrame()
    box.setObjectName("lumosCard")
    box.setStyleSheet("""
        QFrame#lumosCard {
            background: rgba(39, 28, 65, 225);
            border: 1px solid rgba(183, 143, 255, 65);
            border-radius: 18px;
        }
    """)
    return box


class Lumos(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Lumos | Your Personal Sky")
        self.resize(1240, 830)
        self.setMinimumSize(970, 690)

        self.current = None
        self.forecast = None
        self.unit = "C"
        self.saved_cities = ["New York", "Kathmandu", "Barcelona", "London"]
        self.worker = None
        self.city_name = "New York"
        self.city_offset = 0

        root = QWidget()
        self.setCentralWidget(root)
        outer = QHBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        sidebar = self.build_sidebar()
        outer.addWidget(sidebar)

        self.background = StarBackground()
        outer.addWidget(self.background, 1)

        content = QVBoxLayout(self.background)
        content.setContentsMargins(28, 24, 28, 24)
        content.setSpacing(17)

        top = QHBoxLayout()
        title_column = QVBoxLayout()
        title_column.setSpacing(4)
        self.page_title = make_label("Your sky, at a glance", 23, "#FFFFFF", True)
        self.page_subtitle = make_label(
            "A little light for whatever the day brings.", 11, "#B5A5CB"
        )
        title_column.addWidget(self.page_title)
        title_column.addWidget(self.page_subtitle)
        top.addLayout(title_column)
        top.addStretch()

        self.city_input = QLineEdit()
        self.city_input.setPlaceholderText("Search a city...")
        self.city_input.setFixedWidth(205)
        self.city_input.returnPressed.connect(self.search_city)
        top.addWidget(self.city_input)

        search = MagicButton("⌕  Search")
        search.clicked.connect(self.search_city)
        top.addWidget(search)
        content.addLayout(top)

        self.pages = QStackedWidget()
        content.addWidget(self.pages, 1)

        self.build_overview()
        self.build_forecast()
        self.build_saved()
        self.build_settings()

        self.setStyleSheet("""
            QMainWindow { background:#100C20; }
            QLineEdit {
                background:#261C40; color:#FFFFFF;
                border:1px solid #59427B; border-radius:12px;
                padding:12px; font-size:13px;
                selection-background-color:#8D5DE0;
            }
            QLineEdit:focus { border:1px solid #BD97FF; }
            QPushButton {
                background:#49316F; color:#FFFFFF;
                border:1px solid #7656A5; border-radius:11px;
                padding:11px 14px; font-size:12px; font-weight:600;
            }
            QPushButton:hover { background:#6946A0; border-color:#BFA0FF; }
            QPushButton:pressed { background:#35204F; padding-top:13px; padding-bottom:9px; }
            QListWidget {
                background:transparent; color:#D9C9F2;
                border:none; outline:none; font-size:13px;
            }
            QListWidget::item { padding:13px; border-radius:10px; margin:3px 0; }
            QListWidget::item:selected { background:#503576; color:white; }
        """)

        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self.update_city_clock)
        self.clock_timer.start(1000)

        self.change_page(0)
        self.load_weather("New York")

    def build_sidebar(self):
        sidebar = QWidget()
        sidebar.setFixedWidth(215)
        sidebar.setStyleSheet(
            "background:#151025; border-right:1px solid #33254E;"
        )
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(18, 25, 18, 20)
        layout.setSpacing(8)

        layout.addWidget(make_label("✦  LUMOS", 24, "#E8D9FF", True))
        layout.addWidget(make_label("YOUR PERSONAL SKY", 9, "#A995C8", True))
        layout.addSpacing(30)

        self.navigation = QListWidget()
        self.navigation.addItems([
            "✧   Overview", "☾   Forecast", "☆   Saved Cities", "⚙   Settings"
        ])
        self.navigation.setCurrentRow(0)
        self.navigation.currentRowChanged.connect(self.change_page)
        layout.addWidget(self.navigation)
        layout.addStretch()

        quote = make_card()
        q = QVBoxLayout(quote)
        q.setContentsMargins(13, 14, 13, 14)
        q.addWidget(make_label("✦  A LITTLE MAGIC", 10, "#C6A5FF", True))
        q.addWidget(make_label("Look up. The universe is putting on a show.", 11, "#B9A9D0"))
        layout.addWidget(quote)
        layout.addSpacing(10)
        layout.addWidget(make_label("LUMOS WEATHER  •  v1.1", 9, "#78678F"))
        return sidebar

    def build_overview(self):
        page = QWidget()
        page.setStyleSheet("background:transparent;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(13)

        self.location = make_label("NEW YORK", 11, "#C5A4FF", True)
        self.date = make_label("Local date loading...", 11, "#AA99C3")
        self.local_clock = make_label("--:--:--", 13, "#D7C5FF", True)
        layout.addWidget(self.location)
        row_date = QHBoxLayout()
        row_date.addWidget(self.date)
        row_date.addStretch()
        row_date.addWidget(make_label("LOCAL TIME", 9, "#A995C8", True))
        row_date.addWidget(self.local_clock)
        layout.addLayout(row_date)

        hero = make_card()
        hero_row = QHBoxLayout(hero)
        hero_row.setContentsMargins(24, 20, 24, 20)

        left = QVBoxLayout()
        left.addWidget(make_label("CURRENT CONDITIONS", 10, "#C4A4FF", True))
        self.condition = make_label("Waiting for the sky...", 18, "#FFFFFF", True)
        left.addWidget(self.condition)
        self.temperature = make_label("--°C", 58, "#FFFFFF", True)
        left.addWidget(self.temperature)
        self.feels = make_label("Feels like --°", 12, "#C5B7DC")
        left.addWidget(self.feels)
        self.description = make_label("Your forecast will appear here.", 12, "#D3C5E8")
        left.addWidget(self.description)
        hero_row.addLayout(left, 2)

        self.weather_icon = make_label("☾", 72, "#D1B0FF", True)
        self.weather_icon.setAlignment(Qt.AlignCenter)
        hero_row.addWidget(self.weather_icon, 1)
        layout.addWidget(hero)

        layout.addWidget(make_label("YOUR ATMOSPHERE", 11, "#C5A4FF", True))
        grid = QGridLayout()
        grid.setSpacing(11)
        self.metrics = {}

        for i, (key, title, icon, value) in enumerate([
            ("humidity", "HUMIDITY", "💧", "--%"),
            ("wind", "WIND", "✧", "-- km/h"),
            ("visibility", "VISIBILITY", "☼", "-- km"),
        ]):
            box = make_card()
            col = QVBoxLayout(box)
            col.setContentsMargins(14, 13, 14, 13)
            col.addWidget(make_label(f"{icon}  {title}", 9, "#B9A4D9", True))
            value_label = make_label(value, 21, "#FFFFFF", True)
            col.addWidget(value_label)
            self.metrics[key] = value_label
            grid.addWidget(box, 0, i)
        layout.addLayout(grid)

        layout.addWidget(make_label("THE NEXT HOURS", 11, "#C5A4FF", True))
        self.hourly = QHBoxLayout()
        self.hourly.setSpacing(9)
        layout.addLayout(self.hourly)
        self.hourly_note = make_label(
            "Forecast timestamps are shown in the city's local time.", 9, "#9584B0"
        )
        layout.addWidget(self.hourly_note)
        layout.addStretch()
        self.pages.addWidget(page)

    def build_forecast(self):
        page = QWidget()
        page.setStyleSheet("background:transparent;")
        layout = QVBoxLayout(page)
        layout.addWidget(make_label("The forecast", 21, "#FFFFFF", True))
        layout.addWidget(make_label("Real forecast points for the coming days.", 12, "#B5A5CB"))
        self.forecast_rows = QVBoxLayout()
        self.forecast_rows.setSpacing(10)
        layout.addLayout(self.forecast_rows)
        layout.addStretch()
        self.pages.addWidget(page)

    def build_saved(self):
        page = QWidget()
        page.setStyleSheet("background:transparent;")
        layout = QVBoxLayout(page)
        layout.addWidget(make_label("Your favorite skies", 21, "#FFFFFF", True))
        layout.addWidget(make_label("Double-click a city to load its weather.", 12, "#B5A5CB"))

        self.saved_list = QListWidget()
        self.saved_list.itemDoubleClicked.connect(self.open_saved)
        layout.addWidget(self.saved_list)

        row = QHBoxLayout()
        self.new_city = QLineEdit()
        self.new_city.setPlaceholderText("Add a city...")
        self.new_city.returnPressed.connect(self.add_city)
        add = MagicButton("+ Add City")
        add.clicked.connect(self.add_city)
        row.addWidget(self.new_city, 1)
        row.addWidget(add)
        layout.addLayout(row)
        self.refresh_saved()
        self.pages.addWidget(page)

    def build_settings(self):
        page = QWidget()
        page.setStyleSheet("background:transparent;")
        layout = QVBoxLayout(page)
        layout.addWidget(make_label("Make Lumos yours", 21, "#FFFFFF", True))
        layout.addWidget(make_label("Choose your preferred temperature unit.", 12, "#B5A5CB"))

        box = make_card()
        col = QVBoxLayout(box)
        col.setContentsMargins(20, 20, 20, 20)
        col.addWidget(make_label("TEMPERATURE UNITS", 10, "#C5A4FF", True))
        buttons = QHBoxLayout()
        self.fahrenheit_button = MagicButton("°F  Fahrenheit")
        self.celsius_button = MagicButton("°C  Celsius")
        self.fahrenheit_button.clicked.connect(lambda: self.set_unit("F"))
        self.celsius_button.clicked.connect(lambda: self.set_unit("C"))
        buttons.addWidget(self.fahrenheit_button)
        buttons.addWidget(self.celsius_button)
        self.update_temperature_buttons()
        col.addLayout(buttons)
        layout.addWidget(box)

        about = make_card()
        about_col = QVBoxLayout(about)
        about_col.setContentsMargins(20, 20, 20, 20)
        about_col.addWidget(make_label("ABOUT LUMOS", 10, "#C5A4FF", True))
        about_col.addWidget(make_label(
            "Your personal weather observatory, with a little cosmic magic.", 13, "#D3C5E8"
        ))
        about_col.addWidget(make_label(
            "Weather data provided by OpenWeatherMap.", 10, "#A995C8"
        ))
        layout.addWidget(about)
        layout.addStretch()
        self.pages.addWidget(page)

    def change_page(self, index):
        if not hasattr(self, "pages") or index < 0:
            return
        self.pages.setCurrentIndex(index)
        titles = [
            ("Your sky, at a glance", "A little light for whatever the day brings."),
            ("The forecast", "A little preparation makes a brighter day."),
            ("Saved cities", "Keep an eye on the places you care about."),
            ("Settings", "Make your personal sky feel just right."),
        ]
        self.page_title.setText(titles[index][0])
        self.page_subtitle.setText(titles[index][1])

    def search_city(self):
        city = self.city_input.text().strip()
        if city:
            self.load_weather(city)

    def load_weather(self, city):
        self.city_name = city
        self.city_input.setText(city)
        self.page_subtitle.setText(f"Looking up the sky over {city}...")
        self.hourly_note.setText("Loading local forecast times...")
        self.worker = WeatherWorker(city)
        self.worker.succeeded.connect(self.update_weather)
        self.worker.failed.connect(self.show_error)
        self.worker.start()

    def city_datetime(self, timestamp=None):
        """Convert a Unix timestamp using the UTC offset returned for this city."""
        if timestamp is None:
            timestamp = datetime.now(timezone.utc).timestamp()
        return datetime.fromtimestamp(
            timestamp, timezone.utc
        ) + timedelta(seconds=self.city_offset)

    def update_city_clock(self):
        if self.current is None:
            return
        city_now = self.city_datetime()
        self.date.setText(city_now.strftime("%A, %B %d, %Y"))
        self.local_clock.setText(city_now.strftime("%I:%M:%S %p").lstrip("0"))

    @staticmethod
    def symbol(code):
        if code.startswith("01"):
            return "☀" if code.endswith("d") else "☾"
        if code.startswith(("02", "03", "04")):
            return "☁"
        if code.startswith(("09", "10")):
            return "☂"
        if code.startswith("11"):
            return "ϟ"
        if code.startswith("13"):
            return "❄"
        if code.startswith("50"):
            return "≋"
        return "✦"

    def temp_value(self, celsius):
        return celsius if self.unit == "C" else celsius * 9 / 5 + 32

    def temp_text(self, celsius):
        return f"{round(self.temp_value(celsius))}°{self.unit}"

    def update_weather(self, current, forecast):
        self.current = current
        self.forecast = forecast
        self.city_offset = int(current.get("timezone", 0))
        name = current.get("name", self.city_name)
        country = current.get("sys", {}).get("country", "")
        self.location.setText(f"{name.upper()}, {country.upper()}".strip(", "))
        self.update_city_clock()

        self.condition.setText(current["weather"][0]["description"].title())
        self.temperature.setText(self.temp_text(current["main"]["temp"]))
        self.feels.setText(f"Feels like {self.temp_text(current['main']['feels_like'])}")
        self.description.setText("✨ Stay curious. Keep looking up.")
        self.weather_icon.setText(self.symbol(current["weather"][0]["icon"]))

        self.metrics["humidity"].setText(f"{current['main']['humidity']}%")
        wind_ms = current.get("wind", {}).get("speed")
        if wind_ms is not None:
            wind_value = wind_ms * 3.6 if self.unit == "C" else wind_ms * 2.23694
            wind_unit = "km/h" if self.unit == "C" else "mph"
            self.metrics["wind"].setText(f"{round(wind_value)} {wind_unit}")
        else:
            self.metrics["wind"].setText("--")
        visibility = current.get("visibility")
        self.metrics["visibility"].setText(
            f"{visibility / 1000:.1f} km" if visibility is not None else "-- km"
        )

        self.render_hourly(forecast)
        self.render_forecast(forecast)
        self.page_subtitle.setText("A little light for whatever the day brings.")

    def render_hourly(self, forecast):
        self.clear_layout(self.hourly)
        entries = forecast.get("list", [])
        if not entries:
            self.hourly_note.setText("No hourly forecast points were returned.")
            return
        
        now_ts = datetime.now(timezone.utc).timestamp()
        points = sorted(entries, key=lambda item: item["dt"])
        hourly_points = []
        first_hour = int(now_ts // 3600) * 3600

        for hour_index in range(5):
            target_ts = first_hour + hour_index * 3600
            before = None
            after = None
            for point in points:
                if point["dt"] <= target_ts:
                    before = point
                if point["dt"] >= target_ts:
                    after = point
                    break

            if before is None:
                before = points[0]
            if after is None:
                after = points[-1]

            t1 = float(before["main"]["temp"])
            t2 = float(after["main"]["temp"])
            if after["dt"] == before["dt"]:
                estimated_temp = t1
            else:
                fraction = (target_ts - before["dt"]) / (after["dt"] - before["dt"])
                fraction = max(0.0, min(1.0, fraction))
                estimated_temp = t1 + (t2 - t1) * fraction

            nearest = before if abs(target_ts - before["dt"]) <= abs(after["dt"] - target_ts) else after
            hourly_points.append((target_ts, estimated_temp, nearest, hour_index))

        for target_ts, estimated_temp, source, index in hourly_points:
            box = make_card()
            col = QVBoxLayout(box)
            col.setContentsMargins(6, 10, 6, 10)
            dt_local = self.city_datetime(target_ts)
            time_text = "NOW" if index == 0 else dt_local.strftime("%-I %p")
            col.addWidget(make_label(time_text, 9, "#C8B4E8", True))
            icon = make_label(
                self.symbol(source["weather"][0]["icon"]), 23, "#D1B0FF"
            )
            icon.setAlignment(Qt.AlignCenter)
            col.addWidget(icon)
            temp = make_label(self.temp_text(estimated_temp), 17, "#FFFFFF", True)
            temp.setAlignment(Qt.AlignCenter)
            col.addWidget(temp)
            desc = make_label(source["weather"][0]["main"], 9, "#B8A4D5")
            desc.setAlignment(Qt.AlignCenter)
            col.addWidget(desc)
            self.hourly.addWidget(box, 1)

        self.hourly_note.setText(
            "Hourly temperatures between 3-hour forecast points are estimates; weather icons use the nearest forecast point."
        )

    def render_forecast(self, forecast):
        self.clear_layout(self.forecast_rows)
        days = {}
        for entry in forecast.get("list", []):
            dt_local = self.city_datetime(entry["dt"])
            key = dt_local.strftime("%Y-%m-%d")
            # Keep the forecast point closest to local midday for each date.
            if key not in days or abs(dt_local.hour - 12) < abs(
                self.city_datetime(days[key]["dt"]).hour - 12
            ):
                days[key] = entry

        today_key = self.city_datetime().strftime("%Y-%m-%d")
        for key, entry in list(days.items())[:5]:
            dt_local = self.city_datetime(entry["dt"])
            box = make_card()
            row = QHBoxLayout(box)
            row.setContentsMargins(15, 12, 15, 12)
            day_text = "Today" if key == today_key else dt_local.strftime("%A, %b %d")
            row.addWidget(make_label(day_text, 12, "#FFFFFF", True), 2)
            row.addWidget(make_label(
                self.symbol(entry["weather"][0]["icon"]), 22, "#D1B0FF"
            ), 1)
            row.addWidget(make_label(
                entry["weather"][0]["description"].title(), 11, "#C5B7DC"
            ), 3)
            row.addWidget(make_label(
                self.temp_text(entry["main"]["temp"]), 17, "#FFFFFF", True
            ), 1)
            self.forecast_rows.addWidget(box)

    def clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
            elif item.layout() is not None:
                self.clear_layout(item.layout())

    def refresh_saved(self):
        if not hasattr(self, "saved_list"):
            return
        self.saved_list.clear()
        for city in self.saved_cities:
            item = QListWidgetItem(f"✦   {city}")
            item.setData(Qt.UserRole, city)
            self.saved_list.addItem(item)

    def add_city(self):
        city = self.new_city.text().strip()
        if not city:
            return
        if city.casefold() not in [item.casefold() for item in self.saved_cities]:
            self.saved_cities.append(city)
        self.new_city.clear()
        self.refresh_saved()
        self.page_subtitle.setText(f"✨ {city} added to your saved skies.")

    def open_saved(self, item):
        city = item.data(Qt.UserRole)
        self.navigation.setCurrentRow(0)
        self.load_weather(city)

    def update_temperature_buttons(self):
        active_style = """
            QPushButton {
                background-color: #B88AFF;
                color: #170D2B;
                border: 2px solid #E2CCFF;
                border-radius: 10px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #C9A8FF; }
        """
        inactive_style = """
            QPushButton {
                background-color: #24183D;
                color: #C9B7E8;
                border: 1px solid #574275;
                border-radius: 10px;
                font-weight: normal;
            }
            QPushButton:hover {
                background-color: #49316F;
                border: 1px solid #B88AFF;
            }
        """
        if hasattr(self, "celsius_button") and hasattr(self, "fahrenheit_button"):
            self.celsius_button.setStyleSheet(
                active_style if self.unit == "C" else inactive_style
            )
            self.fahrenheit_button.setStyleSheet(
                active_style if self.unit == "F" else inactive_style
            )

    def set_unit(self, unit):
        self.unit = unit
        self.update_temperature_buttons()
        if self.current and self.forecast:
            self.update_weather(self.current, self.forecast)
        self.page_subtitle.setText(f"Temperature units set to °{unit}.")

    def show_error(self, message):
        self.page_subtitle.setText("Let's try finding that sky again.")
        QMessageBox.warning(self, "Lumos", message)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("Lumos")
    window = Lumos()
    window.show()
    sys.exit(app.exec_())
