#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════╗
║        MEDEVAC РЯТУВАЛЬНИЙ ДРОН v2 — СИМУЛЯЦІЯ ЗОНИ БОЮ              ║
║                                                                      ║
║  Керуй дроном-медиком у зоні бойових дій.                            ║
║  Справжня фізика температури, реальна нічна темрява,                 ║
║  видимість крізь стіни ВІДСУТНЯ, тепловізор — єдиний                 ║
║  спосіб бачити живих у темряві (вночі).                              ║
║  Вдень тепловізор НЕПРИДАТНИЙ — вулиця нагрівається                  ║
║  і людей серед гарячого асфальту не розібрати.                       ║
║                                                                      ║
║  Керування:                                                          ║
║    WASD / Стрілки  — Рух дрона                                       ║
║    T               — Тепловізор вкл/викл (тільки вночі)              ║
║    F               — Прожектор вкл/викл (вночі)                      ║
║    SPACE           — Підібрати пораненого / Здати на базу            ║
║    E               — Аварійна зарядка (витрачає час)                 ║
║    TAB             — Показати статус температури                     ║
║    P               — Чіт-меню (тестування)                          ║
║    ESC             — Меню налаштувань / Вихід                        ║
╚══════════════════════════════════════════════════════════════════════╝

Встанови залежності:  pip install pygame numpy
"""

import pygame
import math
import random
import sys
import numpy as np
from typing import Optional, List, Tuple

# ─────────────────────────────────────────────────────────────
#  INIT
# ─────────────────────────────────────────────────────────────
pygame.init()
pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)

SCREEN_W, SCREEN_H = 1280, 720
TILE = 48
MAP_COLS = 56
MAP_ROWS = 42
FPS = 60

screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
pygame.display.set_caption("MEDEVAC РЯТУВАЛЬНИЙ ДРОН v2 — ЗОНА БОЙОВИХ ДІЙ")
clock = pygame.time.Clock()

# ─────────────────────────────────────────────────────────────
#  ЦВЕТОВАЯ ПАЛИТРА
# ─────────────────────────────────────────────────────────────
BLACK        = (0,   0,   0  )
WHITE        = (255, 255, 255)
RED          = (200, 40,  40 )
BRIGHT_RED   = (255, 70,  70 )
GREEN        = (40,  180, 60 )
BRIGHT_GREEN = (80,  255, 100)
BLUE         = (40,  100, 200)
CYAN         = (0,   200, 255)
YELLOW       = (255, 210, 40 )
ORANGE       = (255, 130, 0  )
GRAY         = (128, 128, 128)
DARK_GRAY    = (45,  45,  50 )
LIGHT_GRAY   = (185, 185, 190)
BROWN        = (110, 75,  45 )
DARK_GREEN   = (22,  62,  22 )
SAND         = (165, 145, 85 )
DARK_SAND    = (125, 108, 65 )
DARK_BLUE    = (12,  25,  65 )
TEAL         = (0,   175, 175)
CREAM        = (215, 195, 160)
PURPLE       = (140, 60,  200)

# Тепловизор — правильная термограмма (холодное=фиолетовый/синий, тёплое=красный/белый)
TH_BG      = (2,   2,   4  )   # почти чёрный фон
TH_COLD    = (8,   8,   32 )   # холодные объекты — тёмно-синие
TH_WALL    = (12,  8,   22 )   # стены — очень тёмные
TH_AMBIENT = (18,  12,  35 )   # окружающая среда
TH_WARM    = (80,  20,  10 )   # тёплые — тёмно-красные
TH_HOT     = (200, 60,  20 )   # горячие — оранжево-красные
TH_PEAK    = (255, 240, 180)   # пиковые — почти белые

# ─────────────────────────────────────────────────────────────
#  ТИПЫ ТАЙЛОВ
# ─────────────────────────────────────────────────────────────
TILE_GROUND = 0
TILE_WALL   = 1
TILE_RUBBLE = 2
TILE_ROAD   = 3
TILE_WATER  = 4
TILE_GRASS  = 5
TILE_SAND_D = 6   # сухой песок

# ─────────────────────────────────────────────────────────────
#  ФИЗИЧЕСКИЕ КОНСТАНТЫ ТЕПЛОПЕРЕДАЧИ
# ─────────────────────────────────────────────────────────────
# Закон Ньютона: dQ/dt = h * A * (T_obj - T_env)
# Закон Фурье:   q = -k * dT/dx  (теплопроводность)
# Стефан-Больцман: P = ε * σ * A * T^4  (радиационные потери)

AMBIENT_DAY_C   = 28.0    # Дневная температура окружающей среды, °C
AMBIENT_NIGHT_C = 14.0    # Ночная температура, °C
BODY_TEMP_C     = 37.0    # Температура тела человека
WOUNDED_TEMP_C  = 34.5    # Температура раненого (потеря крови = гипотермия)
DEAD_TEMP_INIT  = 37.0    # Начальная температура трупа
DEAD_COOL_RATE  = 0.8     # °C/час остывания трупа (приближение к ambient)

# Коэффициенты конвекции (Вт/м²·К)
H_PERSON_STILL  = 3.5     # покоящийся человек
H_PERSON_ACTIVE = 7.0     # активный
H_DRONE         = 12.0    # дрон (воздушное охлаждение пропеллерами)
H_GROUND        = 0.8     # земля
H_WATER         = 25.0    # вода (сильная конвекция)

# Теплопроводность материалов (Вт/м·К)
K_CONCRETE  = 1.4         # бетон
K_SOIL      = 0.5         # почва
K_ASPHALT   = 0.75        # асфальт
K_WATER_M   = 0.6         # вода
K_AIR       = 0.026       # воздух

# Излучательная способность (безразмерная, 0-1)
EMISSIVITY_HUMAN  = 0.98   # кожа/одежда
EMISSIVITY_METAL  = 0.15   # металл дрона
EMISSIVITY_GROUND = 0.92   # земля
SIGMA = 5.67e-8            # Постоянная Стефана-Больцмана (Вт/м²·К⁴)

# Масштаб: 1 игровой кадр = 0.5 секунды (для видимой динамики)
DT_GAME = 0.5

# ═════════════════════════════════════════════════════════════
#  ЗВУКОВОЙ БАНК — расширенная процедурная генерация
# ═════════════════════════════════════════════════════════════
class SoundBank:
    SR = 44100

    def __init__(self):
        self.sounds = {}
        self._generate_all()

    def _stereo(self, mono: np.ndarray) -> pygame.mixer.Sound:
        s = np.column_stack([mono, mono]).astype(np.int16)
        return pygame.sndarray.make_sound(s)

    def _env(self, n: int, attack=0.02, sustain=1.0,
             release=0.12) -> np.ndarray:
        e = np.ones(n, dtype=np.float32)
        a = max(1, int(attack * self.SR))
        r = max(1, int(release * self.SR))
        e[:a] = np.linspace(0, 1, a)
        if r < n:
            e[-r:] = np.linspace(e[-r-1] if n > r+1 else sustain, 0, r)
        return e

    def _t(self, dur: float) -> np.ndarray:
        return np.linspace(0, dur, int(dur * self.SR), False)

    def _generate_all(self):
        sr = self.SR
        rng = np.random.default_rng(42)

        # 1. Гул двигателей дрона — богатый многокомпонентный звук
        t = self._t(1.2)
        # Основной тон + гармоники + небольшая модуляция
        lfo = 0.5 + 0.5 * np.sin(2*np.pi*4.2*t)
        w = (np.sin(2*np.pi*92*t) * 0.40 +
             np.sin(2*np.pi*184*t) * 0.22 +
             np.sin(2*np.pi*276*t) * 0.11 +
             np.sin(2*np.pi*368*t) * 0.06 +
             np.sin(2*np.pi*47*t)  * 0.08 * lfo +
             rng.uniform(-0.03, 0.03, len(t)))
        self.sounds['hum'] = self._stereo((w * 19000).astype(np.int16))

        # 2. Бип — ИИ анализ
        t = self._t(0.10)
        e = self._env(len(t), attack=0.004, release=0.05)
        w = np.sin(2*np.pi*1400*t) * e
        self.sounds['beep'] = self._stereo((w * 16000).astype(np.int16))

        # 3. Пинг — обнаружение
        t = self._t(0.10)
        e = self._env(len(t), attack=0.003, release=0.06)
        w = (np.sin(2*np.pi*2200*t)*0.65 + np.sin(2*np.pi*3300*t)*0.35) * e
        self.sounds['ping'] = self._stereo((w * 18000).astype(np.int16))

        # 4. Подбор — мелодичный аккорд C-E-G
        t = self._t(0.55)
        e = self._env(len(t), attack=0.01, release=0.30)
        w = (np.sin(2*np.pi*523*t)*0.38 + np.sin(2*np.pi*659*t)*0.32 +
             np.sin(2*np.pi*784*t)*0.22 + np.sin(2*np.pi*1046*t)*0.08) * e
        self.sounds['pickup'] = self._stereo((w * 26000).astype(np.int16))

        # 5. Успешная эвакуация — восходящее арпеджио
        t = self._t(0.95)
        notes = [523, 659, 784, 1047, 1318]
        seg = len(t) // len(notes)
        w = np.zeros(len(t), dtype=np.float32)
        for i, n in enumerate(notes):
            s0, s1 = i*seg, min((i+1)*seg, len(t))
            tt = t[s0:s1] - t[s0]
            ed = np.linspace(1.0, 0.2, s1-s0)
            w[s0:s1] += np.sin(2*np.pi*n*tt) * ed * 0.5
        self.sounds['success'] = self._stereo((w * 28000).astype(np.int16))

        # 6. Щелчок тепловизора — электронный клик
        t = self._t(0.06)
        rng2 = np.random.default_rng(7)
        noise = rng2.uniform(-1, 1, len(t))
        e = np.exp(-np.linspace(0, 8, len(t)))
        click_tone = np.sin(2*np.pi*3800*t) * e * 0.5
        w = noise * e * 0.5 + click_tone
        self.sounds['click'] = self._stereo((w * 18000).astype(np.int16))

        # 7. Предупреждение низкого заряда
        t = self._t(0.32)
        e = self._env(len(t), attack=0.01, release=0.14)
        w = (np.sin(2*np.pi*330*t) + np.sin(2*np.pi*247*t)*0.5) * e
        self.sounds['warn'] = self._stereo((w * 18000).astype(np.int16))

        # 8. Тревога — раненый найден (частота нарастает)
        t = self._t(0.42)
        freq_sweep = 340 + 520 * (t / t[-1])**0.7
        e = self._env(len(t), attack=0.02, release=0.14)
        w = np.sin(2*np.pi * np.cumsum(freq_sweep/sr)) * e
        self.sounds['alert'] = self._stereo((w * 22000).astype(np.int16))

        # 9. Провал миссии — нисходящий тон
        t = self._t(1.1)
        freq2 = 420 * np.exp(-0.9 * t/t[-1])
        phase = np.cumsum(freq2 / sr * 2*np.pi)
        e = self._env(len(t), attack=0.03, release=0.55)
        w = (np.sin(phase) + np.sin(phase*2)*0.3) * e * 0.8
        self.sounds['fail'] = self._stereo((w * 22000).astype(np.int16))

        # 10. Взрыв / удар — низкочастотный удар
        t = self._t(0.5)
        rng3 = np.random.default_rng(13)
        noise3 = rng3.uniform(-1, 1, len(t))
        exp_env = np.exp(-np.linspace(0, 6, len(t)))
        sub = np.sin(2*np.pi*48*t) * np.exp(-np.linspace(0, 4, len(t)))
        w = (noise3 * exp_env * 0.7 + sub * 0.3)
        self.sounds['explosion'] = self._stereo((w * 24000).astype(np.int16))

        # 11. Тепловой сигнал тепловизора — высокий тон при нагреве
        t = self._t(0.18)
        e = self._env(len(t), attack=0.006, release=0.10)
        w = (np.sin(2*np.pi*2600*t)*0.6 + np.sin(2*np.pi*3900*t)*0.4) * e
        self.sounds['thermal_ping'] = self._stereo((w * 14000).astype(np.int16))

        # 12. Зарядка — электрический гул
        t = self._t(0.8)
        rng4 = np.random.default_rng(21)
        e = self._env(len(t), attack=0.1, release=0.25)
        buzz = np.sin(2*np.pi*60*t) + rng4.uniform(-0.2, 0.2, len(t))
        hiss = rng4.uniform(-0.3, 0.3, len(t)) * np.exp(-np.linspace(0, 3, len(t)))
        w = (buzz * 0.6 + hiss * 0.4) * e
        self.sounds['charge'] = self._stereo((w * 16000).astype(np.int16))

        # 13. Шаги / движение (атмосфера)
        t = self._t(0.12)
        rng5 = np.random.default_rng(33)
        w = rng5.uniform(-1, 1, len(t)) * np.exp(-np.linspace(0, 5, len(t)))
        self.sounds['step'] = self._stereo((w * 8000).astype(np.int16))

        # 14. Свист ветра ночью
        t = self._t(2.0)
        rng6 = np.random.default_rng(55)
        noise_wind = rng6.uniform(-1, 1, len(t))
        # Полосовой фильтр: умножаем на медленную синусоиду
        wind_mod = 0.5 + 0.5 * np.sin(2*np.pi*0.3*t)
        w = noise_wind * wind_mod * 0.15
        self.sounds['wind'] = self._stereo((w * 12000).astype(np.int16))

    def play(self, name: str, vol: float = 1.0, loops: int = 0):
        s = self.sounds.get(name)
        if s:
            s.set_volume(max(0.0, min(1.0, vol)))
            s.play(loops)

    def stop(self, name: str):
        s = self.sounds.get(name)
        if s: s.stop()


# ═════════════════════════════════════════════════════════════
#  УЛУЧШЕННЫЕ СПРАЙТЫ — всё через pygame.draw
# ═════════════════════════════════════════════════════════════

def _hex_pts(cx, cy, r, angle_offset=30):
    return [(int(cx + math.cos(math.radians(i*60+angle_offset))*r),
             int(cy + math.sin(math.radians(i*60+angle_offset))*r))
            for i in range(6)]


def make_drone_surf(thermal: bool = False) -> pygame.Surface:
    """Улучшенный спрайт дрона 72×72 с деталями"""
    sz = 72
    s = pygame.Surface((sz, sz), pygame.SRCALPHA)
    cx = cy = sz // 2

    if thermal:
        # В тепловизоре дрон виден как горячий металл
        body_c   = (200, 80,  20)   # тёплый металл
        arm_c    = (120, 45,  10)
        prop_c   = (160, 60,  15)
        motor_c  = (240, 120, 40)
        light_c  = (255, 200, 100)
        cross_c  = (255, 180, 80)
        led_c    = (255, 220, 120)
    else:
        body_c   = (42,  135, 245)  # синий корпус
        arm_c    = (55,  60,  80)
        prop_c   = (200, 208, 215)
        motor_c  = (80,  85,  100)
        light_c  = (255, 55,  55)
        cross_c  = (255, 40,  40)
        led_c    = (60,  255, 120)

    arm_len = 28
    # Четыре луча + пропеллеры
    for deg in [45, 135, 225, 315]:
        rad = math.radians(deg)
        ex, ey = int(cx + math.cos(rad)*arm_len), int(cy + math.sin(rad)*arm_len)
        # Луч с двойной линией (объём)
        pygame.draw.line(s, arm_c, (cx, cy), (ex, ey), 5)
        px1 = int(cx + math.cos(rad+0.3)*3)
        py1 = int(cy + math.sin(rad+0.3)*3)
        pygame.draw.line(s, (arm_c[0]//2, arm_c[1]//2, arm_c[2]//2),
                         (px1, py1), (ex, ey), 2)
        # Мотор (круг с обводкой)
        pygame.draw.circle(s, motor_c, (ex, ey), 8)
        pygame.draw.circle(s, arm_c, (ex, ey), 8, 2)
        # Пропеллеры — 2 лопасти под углом
        for ba in [0, 90]:
            brd = math.radians(deg + ba)
            bx1 = int(ex + math.cos(brd)*13)
            by1 = int(ey + math.sin(brd)*13)
            bx2 = int(ex - math.cos(brd)*13)
            by2 = int(ey - math.sin(brd)*13)
            pygame.draw.line(s, prop_c, (bx1, by1), (bx2, by2), 3)
            # Блик на лопасти
            mx_ = (bx1+ex)//2; my_ = (by1+ey)//2
            pygame.draw.circle(s, WHITE if not thermal else (255,200,80), (mx_, my_), 2)

    # Шестигранный корпус с градиентом
    br = 18
    hp = _hex_pts(cx, cy, br)
    hp_inner = _hex_pts(cx, cy, br-5)
    pygame.draw.polygon(s, body_c, hp)
    # Внутренняя деталь
    inner_c = (min(255, body_c[0]+40), min(255, body_c[1]+40), min(255, body_c[2]+40))
    pygame.draw.polygon(s, inner_c, hp_inner)
    pygame.draw.polygon(s, arm_c, hp, 2)

    # Медицинский крест — более детальный
    cw, ch = 5, 14
    # Тень
    pygame.draw.rect(s, (0,0,0,120), (cx-cw//2+1, cy-ch//2+1, cw, ch))
    pygame.draw.rect(s, (0,0,0,120), (cx-ch//2+1, cy-cw//2+1, ch, cw))
    # Сам крест
    pygame.draw.rect(s, cross_c, (cx-cw//2, cy-ch//2, cw, ch))
    pygame.draw.rect(s, cross_c, (cx-ch//2, cy-cw//2, ch, cw))
    # Блик на кресте
    pygame.draw.rect(s, WHITE, (cx-cw//2+1, cy-ch//2+1, cw-2, 3))

    # Навигационные огни
    pygame.draw.circle(s, light_c, (cx, cy-br+2), 5)  # передний красный
    pygame.draw.circle(s, led_c,   (cx, cy+br-2), 4)  # задний зелёный
    pygame.draw.circle(s, arm_c,   (cx, cy-br+2), 5, 1)

    # Антенна
    pygame.draw.line(s, arm_c, (cx-2, cy-br), (cx-4, cy-br-8), 2)
    pygame.draw.circle(s, (0,200,255) if not thermal else (200,120,40), (cx-4, cy-br-8), 3)

    return s


def make_drone_spotlight_surf(radius: int) -> pygame.Surface:
    """Конус прожектора дрона"""
    sz = radius * 2 + 4
    s = pygame.Surface((sz, sz), pygame.SRCALPHA)
    cx = cy = sz // 2
    # Градиентный круг
    for r in range(radius, 0, -3):
        alpha = int(55 * (1 - r/radius)**0.5)
        pygame.draw.circle(s, (255, 248, 200, alpha), (cx, cy), r)
    return s


def draw_soldier_v2(surf: pygame.Surface, sx: int, sy: int,
                    wounded: bool, dead: bool, team: str,
                    thermal: bool = False, heat_vis: float = 1.0):
    """
    Улучшенный солдат с более детальным спрайтом.
    В обычном режиме БЕЗ тепловизора — цвета реальные, НО видимость
    зависит от освещения (heat_vis не используется в обычном режиме).
    В тепловизоре — цвет зависит от температуры.
    """
    if thermal:
        # Тепловые цвета: горячий = белый/жёлтый, холодный = тёмно-красный/синий
        if dead:
            v = int(40 + 60 * heat_vis)   # труп остывает
            body_c  = (max(0,v-10), max(0,v-30), max(0,v-30))
            head_c  = (max(0,v+5), max(0,v-20), max(0,v-20))
            equip_c = (max(0,v-20), max(0,v-40), max(0,v-40))
            helm_c  = (max(0,v-25), max(0,v-45), max(0,v-45))
        elif wounded:
            v = int(100 + 80 * heat_vis)
            body_c  = (v, int(v*0.3), int(v*0.1))
            head_c  = (min(255,v+40), int(v*0.4), int(v*0.1))
            equip_c = (int(v*0.7), int(v*0.2), int(v*0.1))
            helm_c  = (int(v*0.6), int(v*0.15), int(v*0.05))
        else:
            v = int(160 + 80 * heat_vis)
            body_c  = (min(255,v), int(v*0.35), int(v*0.1))
            head_c  = (min(255,v+20), int(v*0.45), int(v*0.15))
            equip_c = (int(v*0.75), int(v*0.25), int(v*0.08))
            helm_c  = (int(v*0.65), int(v*0.2), int(v*0.05))
    else:
        if team == 'friendly':
            body_c  = (42,  85,  42)
            equip_c = (30,  52,  30)
            leg_c   = (35,  62,  35)
            helm_c  = (28,  48,  28)
        else:
            body_c  = (98,  58,  34)
            equip_c = (72,  44,  28)
            leg_c   = (72,  44,  28)
            helm_c  = (55,  35,  22)
        if dead:
            body_c  = (55, 52, 48)
            equip_c = (42, 40, 36)
            leg_c   = (42, 40, 36)
            helm_c  = (38, 36, 32)
        head_c  = (188, 148, 102)
        if dead: head_c = (130, 115, 95)

    if dead or wounded:
        # Лежит — горизонтальный спрайт 46×26
        s = pygame.Surface((46, 26), pygame.SRCALPHA)
        # Туловище
        pygame.draw.ellipse(s, body_c, (2, 8, 30, 12))
        # Снаряжение
        pygame.draw.rect(s, equip_c, (5, 7, 14, 10))
        # Голова
        pygame.draw.circle(s, head_c, (38, 13), 6)
        pygame.draw.ellipse(s, helm_c, (32, 7, 12, 10))
        # Руки
        pygame.draw.line(s, body_c if not thermal else body_c, (12, 8), (1, 2), 3)
        pygame.draw.line(s, body_c, (5, 14), (0, 20), 3)
        pygame.draw.line(s, body_c, (8, 15), (3, 22), 3)
        # Ноги
        pygame.draw.line(s, body_c, (20, 18), (14, 24), 3)
        pygame.draw.line(s, body_c, (24, 18), (30, 24), 3)
        if not thermal and (dead or wounded):
            # Кровь
            blood = pygame.Surface((20, 8), pygame.SRCALPHA)
            pygame.draw.ellipse(blood, (120, 10, 10, 160), (0, 0, 20, 8))
            s.blit(blood, (8, 15))
        if wounded and not dead and not thermal:
            # Зелёный крест (пульсирует в другом месте)
            pygame.draw.line(s, BRIGHT_GREEN, (38, 3), (38, 9), 2)
            pygame.draw.line(s, BRIGHT_GREEN, (35, 6), (41, 6), 2)
        surf.blit(s, (sx-23, sy-13))
    else:
        # Стоит — вертикальный спрайт 26×46
        s = pygame.Surface((26, 46), pygame.SRCALPHA)
        ccx = 13
        if not thermal:
            # Ноги
            pygame.draw.line(s, leg_c,   (ccx-3, 26), (ccx-5, 44), 5)
            pygame.draw.line(s, leg_c,   (ccx+3, 26), (ccx+5, 44), 5)
            # Ботинки
            pygame.draw.ellipse(s, (22,18,14), (ccx-8, 40, 10, 6))
            pygame.draw.ellipse(s, (22,18,14), (ccx+1, 40, 10, 6))
        else:
            pygame.draw.line(s, body_c, (ccx-3, 26), (ccx-5, 44), 5)
            pygame.draw.line(s, body_c, (ccx+3, 26), (ccx+5, 44), 5)
        # Туловище
        pygame.draw.rect(s, body_c,  (ccx-6, 14, 12, 14))
        # Снаряжение (бронежилет)
        pygame.draw.rect(s, equip_c, (ccx-7, 13, 14, 12))
        pygame.draw.rect(s, equip_c, (ccx-5, 25, 10, 4))  # патронташ
        # Руки
        pygame.draw.line(s, body_c, (ccx-6, 16), (0,  24), 4)
        pygame.draw.line(s, body_c, (ccx+6, 16), (26, 24), 4)
        # Голова
        pygame.draw.circle(s, head_c, (ccx, 7), 7)
        # Шлем
        pygame.draw.ellipse(s, helm_c, (ccx-8, 1, 16, 12))
        pygame.draw.rect(s, helm_c, (ccx-8, 5, 16, 5))
        # Визор шлема
        if not thermal:
            pygame.draw.rect(s, (40, 50, 75, 180), (ccx-5, 5, 10, 4))
        # Оружие
        gun_c = (38, 34, 34) if not thermal else equip_c
        if team == 'friendly':
            # Медицинская сумка вместо оружия
            pygame.draw.rect(s, (180, 20, 20) if not thermal else equip_c,
                             (ccx+5, 16, 8, 7))
            pygame.draw.line(s, WHITE if not thermal else body_c,
                             (ccx+7, 18), (ccx+7, 22), 1)
            pygame.draw.line(s, WHITE if not thermal else body_c,
                             (ccx+5, 20), (ccx+11, 20), 1)
        else:
            # Автомат
            pygame.draw.rect(s, gun_c, (ccx+6, 15, 4, 16))
            pygame.draw.rect(s, gun_c, (ccx+6, 13, 14, 4))
        surf.blit(s, (sx-13, sy-43))


def draw_building_v2(surf: pygame.Surface, rect: pygame.Rect,
                     damaged: bool = False, thermal: bool = False,
                     night_factor: float = 0.0):
    """Улучшенные здания с подсветкой окон ночью"""
    if thermal:
        # Стены поглощают тепло, но медленно отдают его — чуть теплее земли
        wall_c = (14, 10, 26)
        win_c  = (10, 8, 20)
        out_c  = (18, 14, 32)
    else:
        if damaged:
            wall_c = (100, 82, 62)
            out_c  = (82, 68, 52)
            win_c  = (38, 48, 70)
        else:
            wall_c = (132, 110, 88)
            out_c  = (105, 88, 68)
            win_c  = (58, 82, 138)

    pygame.draw.rect(surf, wall_c, rect)
    if not thermal:
        # Горизонтальные линии кладки
        for y in range(rect.y+4, rect.bottom, 14):
            pygame.draw.line(surf, out_c, (rect.x, y), (rect.right, y), 1)
        # Вертикальные трещины (повреждения)
        if damaged:
            rnd_dmg = random.Random(rect.x * 17 + rect.y)
            for _ in range(rnd_dmg.randint(2, 5)):
                cx0 = rect.x + rnd_dmg.randint(8, max(9, rect.width-8))
                cy0 = rect.y + rnd_dmg.randint(0, max(1, rect.height//3))
                cy1 = cy0 + rnd_dmg.randint(20, max(21, rect.height//2))
                pygame.draw.line(surf, (70, 55, 40), (cx0, cy0), (cx0+rnd_dmg.randint(-4,4), cy1), 1)

    # Окна
    for wy in range(rect.y+8, rect.bottom-12, 22):
        for wx in range(rect.x+10, rect.right-12, 20):
            ww, wh = 10, 13
            if wx+ww < rect.right and wy+wh < rect.bottom:
                if not thermal:
                    # Ночью случайные окна светятся
                    rnd_w = random.Random(wx*37+wy)
                    if night_factor > 0.3 and rnd_w.random() < 0.35:
                        lit_c = (220, 190, 80)  # тёплый свет
                        pygame.draw.rect(surf, lit_c, (wx, wy, ww, wh))
                        # Слабое свечение вокруг
                        glow = pygame.Surface((ww+8, wh+8), pygame.SRCALPHA)
                        pygame.draw.rect(glow, (220,190,80,40), (0,0,ww+8,wh+8))
                        surf.blit(glow, (wx-4, wy-4))
                    else:
                        pygame.draw.rect(surf, win_c, (wx, wy, ww, wh))
                        pygame.draw.rect(surf, (95,118,175), (wx, wy, ww, wh), 1)
                else:
                    pygame.draw.rect(surf, win_c, (wx, wy, ww, wh))
    pygame.draw.rect(surf, out_c, rect, 3)


def draw_tile_cell(surf: pygame.Surface, t: int, rect: pygame.Rect,
                   thermal: bool = False):
    if thermal:
        COLS = {
            TILE_GROUND: (12, 8,  18),
            TILE_WALL:   (18, 12, 28),
            TILE_RUBBLE: (16, 12, 14),
            TILE_ROAD:   (14, 12, 22),
            TILE_WATER:  (8,  10, 18),
            TILE_GRASS:  (10, 14, 10),
            TILE_SAND_D: (14, 10, 8),
        }
    else:
        COLS = {
            TILE_GROUND: SAND,
            TILE_WALL:   (108, 88, 68),
            TILE_RUBBLE: (95, 82, 60),
            TILE_ROAD:   (72, 70, 68),
            TILE_WATER:  (42, 82, 145),
            TILE_GRASS:  DARK_GREEN,
            TILE_SAND_D: (178, 158, 95),
        }
    c = COLS.get(t, SAND)
    pygame.draw.rect(surf, c, rect)

    if not thermal:
        if t == TILE_ROAD:
            # Дорожная разметка
            if (rect.centerx // TILE) % 4 == 0:
                pygame.draw.line(surf, (55, 53, 51),
                                 (rect.centerx, rect.y), (rect.centerx, rect.bottom), 1)
            if (rect.centery // TILE) % 4 == 0:
                pygame.draw.line(surf, (55, 53, 51),
                                 (rect.x, rect.centery), (rect.right, rect.centery), 1)
            # Осевая линия
            rng_r = random.Random(rect.x + rect.y*13)
            if rng_r.random() < 0.2:
                pygame.draw.line(surf, (90, 88, 80),
                                 (rect.centerx, rect.y+8), (rect.centerx, rect.bottom-8), 2)
        elif t == TILE_GRASS:
            # Трава — маленькие штрихи
            rng_g = random.Random(rect.x * 7 + rect.y)
            for _ in range(5):
                gx = rect.x + rng_g.randint(4, TILE-4)
                gy = rect.y + rng_g.randint(4, TILE-4)
                gh = rng_g.randint(4, 9)
                gc = rng_g.randint(18, 28)
                pygame.draw.line(surf, (gc, 58+gc, gc),
                                 (gx, gy), (gx+rng_g.randint(-3,3), gy-gh), 1)
        elif t == TILE_WATER:
            # Блики на воде
            rng_wa = random.Random(rect.x + rect.y*17)
            for _ in range(3):
                wx2 = rect.x + rng_wa.randint(4, TILE-4)
                wy2 = rect.y + rng_wa.randint(4, TILE-4)
                pygame.draw.line(surf, (80, 140, 200),
                                 (wx2, wy2), (wx2+rng_wa.randint(4,12), wy2), 1)


def draw_crater(surf: pygame.Surface, x: int, y: int, r: int,
                thermal: bool = False):
    c1  = (72, 58, 40)  if not thermal else (16, 12, 22)
    c2  = (50, 38, 26)  if not thermal else (10, 8,  16)
    rim = (88, 70, 48)  if not thermal else (22, 16, 30)
    rng = random.Random(x*31+y)
    pts = []
    for i in range(16):
        a  = math.radians(i*(360/16))
        rv = r + rng.randint(-7, 8)
        pts.append((int(x+math.cos(a)*rv), int(y+math.sin(a)*rv)))
    if len(pts) >= 3:
        pygame.draw.polygon(surf, c1, pts)
    pygame.draw.circle(surf, c2, (x, y), r//2)
    # Края воронки — осыпь
    for i in range(0, 360, 22):
        a = math.radians(i)
        rx = int(x+math.cos(a)*(r-2))
        ry = int(y+math.sin(a)*(r-2))
        pygame.draw.circle(surf, rim, (rx, ry), 3)
    # Центр чуть темнее
    pygame.draw.circle(surf, (38, 28, 18) if not thermal else (6,4,10), (x,y), r//4)


def draw_tree(surf: pygame.Surface, x: int, y: int, thermal: bool = False):
    trunk = (65, 42, 22) if not thermal else (20, 14, 8)
    leaf1 = (24, 80, 24) if not thermal else (10, 16, 10)
    leaf2 = (16, 58, 16) if not thermal else (7,  12, 7)
    leaf3 = (30, 95, 20) if not thermal else (12, 18, 8)
    # Ствол
    pygame.draw.rect(surf, trunk, (x-3, y+2, 7, 20))
    # Кроны (несколько слоёв)
    pygame.draw.circle(surf, leaf2, (x-9, y+4),  12)
    pygame.draw.circle(surf, leaf2, (x+9, y+4),  12)
    pygame.draw.circle(surf, leaf1, (x,   y-4),  17)
    pygame.draw.circle(surf, leaf1, (x,   y+4),  14)
    pygame.draw.circle(surf, leaf3, (x,   y-8),  10)


def draw_wreck(surf: pygame.Surface, x: int, y: int, thermal: bool = False):
    hull  = (62, 56, 48) if not thermal else (28, 22, 18)
    track = (42, 38, 34) if not thermal else (18, 14, 12)
    burn  = (28, 24, 20) if not thermal else (12, 10, 8)
    s = pygame.Surface((80, 50), pygame.SRCALPHA)
    # Гусеницы
    pygame.draw.rect(s, track, (0,  34, 80, 12), border_radius=4)
    pygame.draw.rect(s, track, (0,  34, 80, 12), border_radius=4)
    # Корпус
    pygame.draw.rect(s, hull,  (5,  14, 70, 24), border_radius=4)
    # Башня
    pygame.draw.polygon(s, hull, [(30, 4), (54, 8), (52, 18), (28, 16)])
    # Ствол пушки
    pygame.draw.line(s, track, (48, 12), (74, 6), 4)
    # Следы пожара
    pygame.draw.ellipse(s, burn, (12, 10, 20, 12))
    if not thermal:
        # Дым/копоть
        for i in range(3):
            sc = 45 + i*15
            pygame.draw.circle(s, (sc, sc-5, sc-10), (38+i*5, 4-i*3), 5+i*3)
    else:
        # В тепловизоре остаточное тепло от двигателя
        for i in range(3):
            v = 35 + i*8
            pygame.draw.circle(s, (v, int(v*0.3), int(v*0.1)), (38+i*5, 4-i*3), 5+i*3)
    surf.blit(s, (x-40, y-25))


def draw_sandbags(surf: pygame.Surface, rect: pygame.Rect, thermal: bool = False):
    bg_c = (118, 98, 62) if not thermal else (24, 18, 12)
    dk_c = (88,  74, 46) if not thermal else (16, 12, 8)
    bh, bw = 12, 22
    rows = max(1, rect.height // bh)
    for row in range(rows):
        offset = bw//2 if row%2 else 0
        y0 = rect.bottom - (row+1)*bh
        for col in range(rect.width//bw+2):
            bx  = rect.x - offset + col*bw
            bxc = max(bx, rect.x)
            bwc = min(bx+bw, rect.right) - bxc
            if bwc > 0:
                pygame.draw.ellipse(surf, bg_c, (bxc, y0, bwc, bh))
                pygame.draw.ellipse(surf, dk_c, (bxc, y0, bwc, bh), 1)
                # Строчка шва
                if bwc > 8:
                    pygame.draw.line(surf, dk_c, (bxc+3, y0+bh//2), (bxc+bwc-3, y0+bh//2), 1)


def draw_barrel(surf: pygame.Surface, x: int, y: int, thermal: bool = False,
                is_fire: bool = False):
    """Бочка, возможно горящая"""
    c1 = (58, 54, 50) if not thermal else (28, 22, 18)
    c2 = (45, 42, 38) if not thermal else (20, 16, 12)
    pygame.draw.ellipse(surf, c1, (x-8, y-14, 16, 28))
    pygame.draw.ellipse(surf, c2, (x-8, y-14, 16, 5))
    pygame.draw.ellipse(surf, c2, (x-8, y+9, 16, 5))
    pygame.draw.line(surf, c2, (x-8, y-8), (x+8, y-8), 2)
    if is_fire and not thermal:
        # Пламя
        for i in range(6):
            fx = x + random.randint(-5, 5)
            fy = y - 14 - random.randint(5, 18)
            fc = random.choice([(255,80,20), (255,160,20), (255,220,50)])
            pygame.draw.circle(surf, fc, (fx, fy), random.randint(3, 7))
    elif is_fire and thermal:
        # В тепловизоре огонь — очень горячий
        for i in range(4):
            fx = x + random.randint(-4, 4)
            fy = y - 14 - random.randint(4, 16)
            v = random.randint(200, 255)
            pygame.draw.circle(surf, (v, int(v*0.8), int(v*0.3)), (fx, fy), random.randint(3, 6))


def draw_fence(surf: pygame.Surface, x1: int, y1: int, x2: int, y2: int,
               thermal: bool = False):
    """Забор/ограждение"""
    c = (75, 65, 55) if not thermal else (20, 16, 14)
    pygame.draw.line(surf, c, (x1, y1), (x2, y2), 2)
    dx, dy = x2-x1, y2-y1
    dist = max(1, int(math.hypot(dx, dy)))
    step = 20
    for i in range(0, dist, step):
        fx = int(x1 + dx*i/dist)
        fy = int(y1 + dy*i/dist)
        pygame.draw.line(surf, c, (fx, fy-10), (fx, fy+10), 2)


# ═════════════════════════════════════════════════════════════
#  СИСТЕМА ТЕМПЕРАТУРЫ — физическая модель
# ═════════════════════════════════════════════════════════════
class ThermalPhysics:
    """
    Физически корректная модель теплопередачи.
    
    Используемые законы:
    1. Закон охлаждения Ньютона: dT/dt = -h*A/mc * (T - T_env)
       Где h — коэффициент теплообмена, A — площадь, m — масса, c — теплоёмкость
    
    2. Закон Фурье для теплопроводности: q = -k * ∇T
    
    3. Излучение Стефана-Больцмана: P = ε * σ * A * (T⁴ - T_env⁴)
    
    Для игровой оптимизации: упрощённая версия с реальными соотношениями.
    """

    def __init__(self):
        # Тепловые карты для земли (грубая сетка для производительности)
        self.grid_cols = MAP_COLS // 2
        self.grid_rows = MAP_ROWS // 2
        self.ground_temp = np.full(
            (self.grid_rows, self.grid_cols), AMBIENT_DAY_C, dtype=np.float32
        )
        self._ambient = AMBIENT_DAY_C
        self._sun_angle = 0.0   # угол солнца (0=восход, 90=полдень, 180=закат)
        self._fire_sources = []  # список (x, y, intensity) горящих объектов
        self._tick = 0

    def set_ambient(self, ambient_c: float, sun_angle_deg: float):
        self._ambient = ambient_c
        self._sun_angle = sun_angle_deg

    def add_fire(self, x: float, y: float, intensity: float = 200.0):
        self._fire_sources.append([x, y, intensity])

    def update(self, dt: float = DT_GAME):
        """Обновление тепловой карты — упрощённый закон Фурье"""
        self._tick += 1

        # Каждые 10 кадров — диффузия тепла (оптимизация)
        if self._tick % 10 == 0:
            self._diffuse(dt * 10)

        # Нагрев от солнца
        if 30 < self._sun_angle < 150:
            sun_factor = math.sin(math.radians(self._sun_angle)) * 0.8
        else:
            sun_factor = 0.0

        # Нагрев от источников огня
        for fs in self._fire_sources:
            gx = int(fs[0] / (TILE*2))
            gy = int(fs[1] / (TILE*2))
            if 0 <= gx < self.grid_cols and 0 <= gy < self.grid_rows:
                r_heat = 3
                for dr in range(-r_heat, r_heat+1):
                    for dc in range(-r_heat, r_heat+1):
                        nr, nc = gy+dr, gx+dc
                        if 0 <= nr < self.grid_rows and 0 <= nc < self.grid_cols:
                            dist2 = dr*dr + dc*dc
                            if dist2 == 0: dist2 = 0.1
                            heat_add = fs[2] / (dist2 * 5.0) * dt * 0.05
                            self.ground_temp[nr, nc] = min(
                                80.0, self.ground_temp[nr, nc] + heat_add
                            )

    def _diffuse(self, dt: float):
        """Диффузия тепла по закону Фурье"""
        k_eff = K_SOIL * dt * 0.001  # масштабированная теплопроводность
        # Конвективное охлаждение к ambient
        h_eff = H_GROUND * dt * 0.002
        diff = np.zeros_like(self.ground_temp)

        # Лапласиан (конечные разности)
        diff[1:-1, 1:-1] = (
            self.ground_temp[:-2, 1:-1] + self.ground_temp[2:, 1:-1] +
            self.ground_temp[1:-1, :-2] + self.ground_temp[1:-1, 2:] -
            4 * self.ground_temp[1:-1, 1:-1]
        ) * k_eff

        self.ground_temp += diff
        # Конвекция к окружающей среде
        self.ground_temp += (self._ambient - self.ground_temp) * h_eff
        # Ограничения
        np.clip(self.ground_temp, -10.0, 120.0, out=self.ground_temp)

    def body_temp_after_dt(self, current_temp: float, is_dead: bool,
                           is_wounded: bool, ambient: float, dt: float) -> float:
        """
        Расчёт температуры тела по закону Ньютона.
        dT/dt = -h*A/mc * (T - T_env)
        
        Для тела человека:
          m ≈ 70 кг, c ≈ 3500 Дж/кг·К (теплоёмкость тела)
          A ≈ 1.8 м²
          h ≈ 3.5 Вт/м²·К (конвекция стоячего человека)
        
        Постоянная времени τ = mc/(hA) ≈ 70*3500/(3.5*1.8) ≈ 39000 сек ≈ 10.8 часов
        """
        if is_dead:
            # Труп охлаждается быстрее: τ ≈ 6-8 часов (метод Хенсса)
            tau_dead = 25000.0  # секунды
            target = ambient
            rate = dt / tau_dead
            return current_temp + (target - current_temp) * rate

        # Живой человек: метаболизм поддерживает температуру
        if is_wounded:
            target_temp = WOUNDED_TEMP_C  # потеря крови = падение
            tau_wounded = 8000.0
            rate = dt / tau_wounded
            # Стресс-реакция: небольшие колебания
            noise = random.uniform(-0.05, 0.05)
            return max(28.0, current_temp + (target_temp - current_temp) * rate + noise)
        else:
            # Здоровый: регуляция близка к 37°C
            target_temp = BODY_TEMP_C
            tau_healthy = 50000.0
            rate = dt / tau_healthy
            noise = random.uniform(-0.03, 0.03)
            return current_temp + (target_temp - current_temp) * rate + noise

    def radiation_loss(self, temp_c: float, area_m2: float = 0.8,
                       emissivity: float = EMISSIVITY_HUMAN) -> float:
        """
        Радиационные потери по Стефану-Больцману.
        P = ε * σ * A * (T^4 - T_env^4)
        Возвращает потерю температуры в °С/сек (для игровых масштабов).
        """
        T_obj = temp_c + 273.15
        T_env = self._ambient + 273.15
        P = emissivity * SIGMA * area_m2 * (T_obj**4 - T_env**4)
        # mc ≈ 245000 Дж/К для человека
        dT_dt = -P / 245000.0
        return dT_dt

    def get_ground_temp(self, wx: float, wy: float) -> float:
        gc = int(wx / (TILE*2))
        gr = int(wy / (TILE*2))
        gc = max(0, min(self.grid_cols-1, gc))
        gr = max(0, min(self.grid_rows-1, gr))
        return float(self.ground_temp[gr, gc])

    def temp_to_thermal_color(self, temp_c: float,
                               ambient: float) -> Tuple[int, int, int]:
        """
        Преобразование температуры в цвет тепловизора.
        Реальные тепловизоры используют pseudo-color:
        - очень холодный: тёмно-синий/фиолетовый
        - ambient: тёмный
        - тёплый: красный/оранжевый
        - горячий: жёлтый/белый
        """
        delta = temp_c - ambient

        if delta < -5:
            # Холоднее ambient — синий/фиолетовый
            t = max(0.0, (delta + 15) / 10.0)  # 0..1
            return (int(20*t), int(10*t), int(60 + 40*t))
        elif delta < 0:
            # Чуть холоднее — тёмный
            t = (delta + 5) / 5.0
            return (int(12*t), int(8*t), int(25*t))
        elif delta < 2:
            # Ambient — почти чёрный
            t = delta / 2.0
            return (int(15*t), int(10*t), int(20*t))
        elif delta < 8:
            # Немного теплее — тёмно-красный
            t = (delta - 2) / 6.0
            return (int(t * 120), int(t * 20), int(t * 15))
        elif delta < 15:
            # Тёплый — красный/оранжевый
            t = (delta - 8) / 7.0
            return (120 + int(t * 120), int(t * 60), int(t * 20))
        else:
            # Горячий — жёлтый/белый
            t = min(1.0, (delta - 15) / 15.0)
            return (min(255, 200 + int(t*55)), min(255, 80+int(t*170)), min(255, int(t*180)))


# ═════════════════════════════════════════════════════════════
#  КАРТА
# ═════════════════════════════════════════════════════════════
class GameMap:
    def __init__(self):
        self.cols = MAP_COLS
        self.rows = MAP_ROWS
        self.tiles = [[TILE_GROUND]*self.cols for _ in range(self.rows)]
        self.buildings  = []   # list[pygame.Rect]
        self.sandbags   = []   # list[pygame.Rect]
        self.craters    = []   # list[(x,y,r)]
        self.trees      = []   # list[(x,y)]
        self.wrecks     = []   # list[(x,y)]
        self.barrels    = []   # list[(x,y,is_fire)]
        self.fences     = []   # list[(x1,y1,x2,y2)]
        self.fire_positions = []  # list[(x,y)]
        self._rng = random.Random(7)
        self._generate()
        self._surf_day     = None
        self._surf_thermal = None
        self._bake(night_factor=0.0)

    def _generate(self):
        rng = self._rng
        mr = self.rows // 2
        mc = self.cols // 2

        # Дороги — крест + диагональные переулки
        for c in range(self.cols):
            self.tiles[mr][c]   = TILE_ROAD
            self.tiles[mr+1][c] = TILE_ROAD
        for r in range(self.rows):
            self.tiles[r][mc]   = TILE_ROAD
            self.tiles[r][mc+1] = TILE_ROAD
        # Горизонтальная дорога на 1/4 и 3/4
        for c in range(self.cols):
            self.tiles[mr//2][c] = TILE_ROAD
            self.tiles[mr+mr//2][c] = TILE_ROAD

        # Здания — расширенная сетка
        bdef = [
            (1,1,9,8),(12,1,10,8),(24,1,9,8),(37,1,10,8),(49,1,6,8),
            (1,12,9,9),(12,12,10,9),(37,12,10,9),(49,12,6,9),
            (1,24,9,9),(12,24,10,9),(24,24,9,9),(37,24,10,9),(49,24,6,9),
            (1,35,9,6),(12,35,10,6),(24,35,9,6),(37,35,10,6),
        ]
        for (bc, br, bw, bh) in bdef:
            if rng.random() < 0.80:
                for r in range(br, min(br+bh, self.rows)):
                    for c in range(bc, min(bc+bw, self.cols)):
                        if 0<=r<self.rows and 0<=c<self.cols:
                            self.tiles[r][c] = TILE_WALL
                rect = pygame.Rect(bc*TILE, br*TILE, bw*TILE, bh*TILE)
                self.buildings.append(rect)

        # Трава
        for _ in range(45):
            gc, gr = rng.randint(0, self.cols-5), rng.randint(0, self.rows-5)
            for r in range(gr, min(gr+rng.randint(2,6), self.rows)):
                for c in range(gc, min(gc+rng.randint(2,7), self.cols)):
                    if self.tiles[r][c] == TILE_GROUND:
                        self.tiles[r][c] = TILE_GRASS

        # Щебень (разрушения)
        for _ in range(60):
            rc, rr = rng.randint(0, self.cols-1), rng.randint(0, self.rows-1)
            if self.tiles[rr][rc] == TILE_GROUND:
                self.tiles[rr][rc] = TILE_RUBBLE

        # Вода
        for _ in range(5):
            wc, wr = rng.randint(2, self.cols-6), rng.randint(2, self.rows-6)
            for r in range(wr, min(wr+rng.randint(2,5), self.rows)):
                for c in range(wc, min(wc+rng.randint(3,7), self.cols)):
                    if self.tiles[r][c] == TILE_GROUND:
                        self.tiles[r][c] = TILE_WATER

        # Сухой песок
        for _ in range(20):
            sc2, sr = rng.randint(0, self.cols-4), rng.randint(0, self.rows-4)
            for r in range(sr, min(sr+rng.randint(2,4), self.rows)):
                for c in range(sc2, min(sc2+rng.randint(2,5), self.cols)):
                    if self.tiles[r][c] == TILE_GROUND:
                        self.tiles[r][c] = TILE_SAND_D

        # Воронки
        for _ in range(30):
            cx = rng.randint(TILE*2, (self.cols-2)*TILE)
            cy = rng.randint(TILE*2, (self.rows-2)*TILE)
            self.craters.append((cx, cy, rng.randint(14, 38)))

        # Деревья
        for _ in range(62):
            tx = rng.randint(TILE, (self.cols-1)*TILE)
            ty = rng.randint(TILE, (self.rows-1)*TILE)
            tc, tr = tx//TILE, ty//TILE
            if 0<=tr<self.rows and 0<=tc<self.cols:
                if self.tiles[tr][tc] in (TILE_GROUND, TILE_GRASS):
                    self.trees.append((tx, ty))

        # Обломки
        for _ in range(12):
            wx = rng.randint(TILE*2, (self.cols-2)*TILE)
            wy = rng.randint(TILE*2, (self.rows-2)*TILE)
            self.wrecks.append((wx, wy))

        # Бочки (часть горящие — источники тепла)
        for _ in range(16):
            bx = rng.randint(TILE*2, (self.cols-2)*TILE)
            by = rng.randint(TILE*2, (self.rows-2)*TILE)
            is_fire = rng.random() < 0.35
            bc2, br2 = bx//TILE, by//TILE
            if 0<=br2<self.rows and 0<=bc2<self.cols:
                if self.tiles[br2][bc2] not in (TILE_WALL, TILE_WATER):
                    self.barrels.append((bx, by, is_fire))
                    if is_fire:
                        self.fire_positions.append((bx, by))

        # Мешки с песком
        sb_defs = [
            (mc*TILE-44, mr*TILE-22, 88, 14),
            (mc*TILE+100,(mr+1)*TILE+10, 88, 14),
            (18*TILE, mr*TILE-22, 80, 14),
            (24*TILE, (mr+1)*TILE+10, 80, 14),
            ((mc-6)*TILE, mr*TILE-22, 80, 14),
            ((mc+8)*TILE, (mr+1)*TILE+10, 80, 14),
        ]
        for bd in sb_defs:
            self.sandbags.append(pygame.Rect(*bd))

        # Заборы
        fence_defs = [
            (8*TILE, 2*TILE, 8*TILE, 9*TILE),
            (45*TILE, 3*TILE, 54*TILE, 3*TILE),
            (3*TILE, 30*TILE, 10*TILE, 30*TILE),
            (28*TILE, 26*TILE, 35*TILE, 26*TILE),
        ]
        for fd in fence_defs:
            self.fences.append(fd)

    def _bake(self, night_factor: float = 0.0):
        w, h = self.cols*TILE, self.rows*TILE
        self._surf_day     = pygame.Surface((w, h))
        self._surf_thermal = pygame.Surface((w, h))

        for thermal, surf in [(False, self._surf_day), (True, self._surf_thermal)]:
            # Тайлы
            for r in range(self.rows):
                for c in range(self.cols):
                    rect = pygame.Rect(c*TILE, r*TILE, TILE, TILE)
                    draw_tile_cell(surf, self.tiles[r][c], rect, thermal)
            # Заборы
            for (x1, y1, x2, y2) in self.fences:
                draw_fence(surf, x1, y1, x2, y2, thermal)
            # Воронки
            for cx, cy, cr in self.craters:
                draw_crater(surf, cx, cy, cr, thermal)
            # Обломки
            for wx, wy in self.wrecks:
                draw_wreck(surf, wx, wy, thermal)
            # Деревья
            for tx, ty in self.trees:
                draw_tree(surf, tx, ty, thermal)
            # Здания
            rng_dmg = random.Random(99)
            for brect in self.buildings:
                draw_building_v2(surf, brect, rng_dmg.random()<0.38, thermal, night_factor)
            # Мешки с песком
            for barrect in self.sandbags:
                draw_sandbags(surf, barrect, thermal)
            # Бочки
            for (bx, by, is_fire) in self.barrels:
                draw_barrel(surf, bx, by, thermal, is_fire)

    def rebake_night(self, night_factor: float):
        """Перезапекаем поверхность для обновления ночного освещения зданий"""
        if abs(night_factor - self._last_night_factor) > 0.15:
            self._last_night_factor = night_factor
            self._bake(night_factor)

    _last_night_factor = -1.0

    def is_wall(self, x: float, y: float) -> bool:
        c, r = int(x)//TILE, int(y)//TILE
        if c<0 or r<0 or c>=self.cols or r>=self.rows:
            return True
        return self.tiles[r][c] == TILE_WALL

    def is_water(self, x: float, y: float) -> bool:
        c, r = int(x)//TILE, int(y)//TILE
        if c<0 or r<0 or c>=self.cols or r>=self.rows:
            return False
        return self.tiles[r][c] == TILE_WATER

    def tile_at(self, x: float, y: float) -> int:
        c, r = int(x)//TILE, int(y)//TILE
        if c<0 or r<0 or c>=self.cols or r>=self.rows:
            return TILE_GROUND
        return self.tiles[r][c]

    def get_surf(self, thermal: bool) -> pygame.Surface:
        return self._surf_thermal if thermal else self._surf_day

    @property
    def pw(self): return self.cols*TILE
    @property
    def ph(self): return self.rows*TILE


# ═════════════════════════════════════════════════════════════
#  ЧАСТИЦЫ — расширенная система
# ═════════════════════════════════════════════════════════════
class Particle:
    __slots__ = ('x','y','vx','vy','life','maxl','color','size','grav','fade')

    def __init__(self, x, y, vx, vy, life, color, size=3, grav=0.0, fade=True):
        self.x, self.y  = x, y
        self.vx, self.vy = vx, vy
        self.life = self.maxl = life
        self.color = color
        self.size  = size
        self.grav  = grav
        self.fade  = fade

    def update(self) -> bool:
        self.x  += self.vx
        self.y  += self.vy
        self.vy += self.grav
        self.vx *= 0.94
        self.life -= 1
        return self.life > 0

    def draw(self, surf: pygame.Surface, cx: int, cy: int):
        if self.fade:
            sz = max(1, int(self.size * self.life / self.maxl))
        else:
            sz = max(1, int(self.size))
        sx, sy = int(self.x-cx), int(self.y-cy)
        if -sz <= sx <= SCREEN_W+sz and -sz <= sy <= SCREEN_H+sz:
            pygame.draw.circle(surf, self.color, (sx, sy), sz)


class Particles:
    MAX = 900

    def __init__(self):
        self.pool: List[Particle] = []

    def _add(self, p: Particle):
        if len(self.pool) < self.MAX:
            self.pool.append(p)

    def burst(self, x, y, count=8, colors=None,
              speed=2.5, life=45, size=3.5, grav=0.04):
        colors = colors or [ORANGE, YELLOW, RED]
        for _ in range(count):
            a   = math.radians(random.uniform(0, 360))
            sp  = random.uniform(0.3, speed)
            self._add(Particle(x, y,
                                math.cos(a)*sp, math.sin(a)*sp,
                                random.randint(life//2, life),
                                random.choice(colors),
                                random.uniform(size*0.5, size), grav))

    def smoke(self, x, y, count=2):
        for _ in range(count):
            v = random.randint(45, 85)
            self._add(Particle(x, y,
                                random.uniform(-0.4, 0.4),
                                random.uniform(-1.0, -0.3),
                                random.randint(40, 85),
                                (v, v, v+5),
                                random.uniform(2, 6), -0.007))

    def thruster(self, x, y, angle_deg: float, count=4):
        back = angle_deg + 180
        for _ in range(count):
            a   = math.radians(back + random.uniform(-28, 28))
            sp  = random.uniform(1.0, 3.0)
            col = random.choice([(255,200,50),(255,130,20),(255,60,10),(200,200,255)])
            self._add(Particle(x, y, math.cos(a)*sp, math.sin(a)*sp,
                                random.randint(5, 14), col, random.uniform(1.5, 3.5)))

    def sparks(self, x, y, count=6):
        """Искры (огонь/удар)"""
        for _ in range(count):
            a  = math.radians(random.uniform(0, 360))
            sp = random.uniform(0.5, 4.0)
            col = random.choice([(255,220,60),(255,160,20),(255,80,10)])
            self._add(Particle(x, y, math.cos(a)*sp, math.sin(a)*sp,
                                random.randint(8, 22), col, random.uniform(1, 3), 0.08))

    def fire_puff(self, x, y, count=3):
        """Пламя от огня"""
        for _ in range(count):
            fx = x + random.uniform(-8, 8)
            fy = y + random.uniform(-5, 5)
            col = random.choice([(255,80,20),(255,160,30),(255,220,60),(200,50,10)])
            self._add(Particle(fx, fy,
                                random.uniform(-0.5, 0.5),
                                random.uniform(-2.5, -0.5),
                                random.randint(10, 25), col,
                                random.uniform(3, 8), -0.02, True))

    def dust(self, x, y, count=4):
        """Пыль"""
        for _ in range(count):
            v = random.randint(88, 135)
            self._add(Particle(x, y,
                                random.uniform(-0.8, 0.8),
                                random.uniform(-0.4, -0.1),
                                random.randint(25, 55),
                                (v, int(v*0.9), int(v*0.7)),
                                random.uniform(2, 7), -0.005))

    def update(self):
        self.pool = [p for p in self.pool if p.update()]

    def draw(self, surf: pygame.Surface, cx: int, cy: int):
        for p in self.pool:
            p.draw(surf, cx, cy)


# ═════════════════════════════════════════════════════════════
#  ТЕПЛОВИЗОР — улучшенный raycast + физические цвета
# ═════════════════════════════════════════════════════════════
class ThermalImager:
    """
    Raycast видимость с физически корректными тепловыми цветами.
    В ночном режиме тепловизор — ЕДИНСТВЕННЫЙ способ видеть живых.
    Стены полностью блокируют тепловое излучение.
    """
    RAYS      = 240
    RANGE     = 420
    STEP      = 5
    UPDATE_DIST = 6.0

    def __init__(self, game_map: GameMap, physics: ThermalPhysics):
        self.gmap    = game_map
        self.physics = physics
        self._poly_world = []
        self._last_ox = -9999.0
        self._last_oy = -9999.0
        self._dirs = [
            (math.cos(math.radians(i*360/self.RAYS)),
             math.sin(math.radians(i*360/self.RAYS)))
            for i in range(self.RAYS+1)
        ]
        self._noise_surf = None
        self._noise_tick = 0

    def _cast(self, ox: float, oy: float, dx: float, dy: float) -> tuple:
        step = self.STEP
        for dist in range(step, self.RANGE+step, step):
            nx, ny = ox+dx*dist, oy+dy*dist
            if self.gmap.is_wall(nx, ny):
                return (ox+dx*(dist-step), oy+dy*(dist-step))
        return (ox+dx*self.RANGE, oy+dy*self.RANGE)

    def _rebuild(self, ox: float, oy: float):
        self._poly_world = [(ox, oy)]
        for dx, dy in self._dirs:
            self._poly_world.append(self._cast(ox, oy, dx, dy))
        self._last_ox, self._last_oy = ox, oy

    def has_los(self, ox, oy, tx, ty, max_range: Optional[float] = None) -> bool:
        dx, dy = tx-ox, ty-oy
        dist = math.hypot(dx, dy)
        r = max_range or self.RANGE
        if dist == 0 or dist > r:
            return False
        steps = max(1, int(dist/self.STEP))
        sdx, sdy = dx/steps, dy/steps
        for i in range(1, steps):
            if self.gmap.is_wall(ox+sdx*i, oy+sdy*i):
                return False
        return True

    def render(self, screen_surf: pygame.Surface,
               world_surf: pygame.Surface,
               ox: float, oy: float,
               cam_x: int, cam_y: int,
               heat_entities: list,
               ambient_c: float,
               fire_sources: list):
        w, h = SCREEN_W, SCREEN_H

        # Пересчёт полигона
        moved = math.hypot(ox-self._last_ox, oy-self._last_oy)
        if moved > self.UPDATE_DIST:
            self._rebuild(ox, oy)

        # 1. Тепловая карта мира (очень тёмная — всё холодное)
        screen_surf.blit(world_surf, (0, 0), (cam_x, cam_y, w, h))

        # 2. Абсолютно тёмный оверлей с дырой видимости
        overlay = pygame.Surface((w, h), pygame.SRCALPHA)
        overlay.fill((TH_BG[0], TH_BG[1], TH_BG[2], 255))

        if len(self._poly_world) >= 3:
            screen_poly = [
                (int(px-cam_x), int(py-cam_y))
                for px, py in self._poly_world
            ]
            pygame.draw.polygon(overlay, (0, 0, 0, 0), screen_poly)

        screen_surf.blit(overlay, (0, 0))

        # 3. Шум тепловизора (зернистость CCD матрицы)
        self._noise_tick += 1
        if self._noise_tick % 3 == 0:
            self._draw_sensor_noise(screen_surf, ox, oy, cam_x, cam_y)

        # 4. Горячие точки от огня
        for (fx, fy) in fire_sources:
            fsx = int(fx-cam_x)
            fsy = int(fy-cam_y)
            if not (-40 <= fsx <= w+40 and -40 <= fsy <= h+40):
                continue
            if self.has_los(ox, oy, fx, fy):
                self._draw_fire_heat(screen_surf, fsx, fsy)

        # 5. Тепловые силуэты живых существ
        for ent in heat_entities:
            ex = int(ent.x-cam_x)
            ey = int(ent.y-cam_y)
            if not (-40 <= ex <= w+40 and -40 <= ey <= h+40):
                continue
            dist = math.hypot(ent.x-ox, ent.y-oy)
            if dist <= self.RANGE and self.has_los(ox, oy, ent.x, ent.y):
                temp_c   = getattr(ent, 'temp_c', BODY_TEMP_C)
                wounded  = getattr(ent, 'wounded', False)
                dead     = getattr(ent, 'dead', False)
                # Рисуем силуэт с физическими цветами
                self._draw_thermal_entity(screen_surf, ex, ey,
                                          temp_c, wounded, dead, ambient_c, dist)

    def _draw_thermal_entity(self, surf, sx, sy, temp_c, wounded, dead, ambient, dist):
        """Тепловой силуэт с физически корректными цветами"""
        # Интенсивность падает с расстоянием (инверсный квадрат)
        dist_factor = max(0.1, 1.0 - (dist / self.RANGE)**1.5)
        delta = (temp_c - ambient) * dist_factor
        col = self.physics.temp_to_thermal_color(ambient + delta, ambient)

        if dead:
            # Труп — горизонтально лежит, тусклый
            eff_col = tuple(int(c*0.4) for c in col)
            pygame.draw.ellipse(surf, eff_col, (sx-20, sy-8, 40, 16))
            # Холодная зона от потери крови
            cold = tuple(max(0, c-30) for c in eff_col)
            pygame.draw.ellipse(surf, cold, (sx-10, sy-4, 22, 10))
        elif wounded:
            # Раненый — лежит, тусклый (потеря тепла)
            pygame.draw.ellipse(surf, col, (sx-18, sy-7, 36, 14))
            # Горячая голова
            head_col = tuple(min(255, int(c*1.3)) for c in col)
            pygame.draw.circle(surf, head_col, (sx+14, sy), 7)
            # Холодная зона раны
            wound_col = tuple(int(c*0.3) for c in col)
            pygame.draw.circle(surf, wound_col, (sx-5, sy+3), 5)
        else:
            # Здоровый стоит — вертикальный силуэт
            pygame.draw.rect(surf, col, (sx-6, sy-20, 12, 22))
            head_col = tuple(min(255, int(c*1.4)) for c in col)
            pygame.draw.circle(surf, head_col, (sx, sy-24), 8)
            # Руки (теплее там, где ближе к торсу)
            arm_col = tuple(int(c*0.85) for c in col)
            pygame.draw.line(surf, arm_col, (sx-6, sy-16), (sx-14, sy-4), 3)
            pygame.draw.line(surf, arm_col, (sx+6, sy-16), (sx+14, sy-4), 3)
            # Ноги (холоднее конечности)
            leg_col = tuple(int(c*0.7) for c in col)
            pygame.draw.line(surf, leg_col, (sx-3, sy+2), (sx-5, sy+18), 4)
            pygame.draw.line(surf, leg_col, (sx+3, sy+2), (sx+5, sy+18), 4)

    def _draw_fire_heat(self, surf, sx, sy):
        """Тепловое пятно от огня — очень яркое"""
        for r in range(28, 0, -5):
            t = 1 - r/28
            col = (int(80+t*175), int(t*130), int(t*30))
            alpha = int(180 * t)
            ring = pygame.Surface((r*2+2, r*2+2), pygame.SRCALPHA)
            pygame.draw.circle(ring, (*col, alpha), (r+1, r+1), r)
            surf.blit(ring, (sx-r-1, sy-r-1))

    def _draw_sensor_noise(self, surf, ox, oy, cam_x, cam_y):
        """Зернистость тепловизора в зоне видимости"""
        csx = int(ox-cam_x)
        csy = int(oy-cam_y)
        for _ in range(60):
            a = random.uniform(0, 2*math.pi)
            r = random.uniform(0, self.RANGE*0.95)
            px2 = int(csx + math.cos(a)*r)
            py2 = int(csy + math.sin(a)*r)
            if 0 <= px2 < SCREEN_W and 0 <= py2 < SCREEN_H:
                v = random.randint(0, 18)
                ns = pygame.Surface((2, 2), pygame.SRCALPHA)
                ns.fill((v, int(v*0.5), int(v*0.3), random.randint(30, 80)))
                surf.blit(ns, (px2, py2))


# ═════════════════════════════════════════════════════════════
#  СИСТЕМА ВИДИМОСТИ — raycast для обычного режима
# ═════════════════════════════════════════════════════════════
class VisibilitySystem:
    """
    Raycast для ночного режима.
    Стены полностью блокируют видимость.
    Дрон не видит сквозь стены даже при наличии прожектора.
    """
    RAYS = 180
    STEP = 6

    def __init__(self, game_map: GameMap):
        self.gmap = game_map
        self._poly = []
        self._last_ox = -9999.0
        self._last_oy = -9999.0
        self._dirs = [
            (math.cos(math.radians(i*360/self.RAYS)),
             math.sin(math.radians(i*360/self.RAYS)))
            for i in range(self.RAYS+1)
        ]

    def rebuild(self, ox: float, oy: float, radius: int):
        moved = math.hypot(ox-self._last_ox, oy-self._last_oy)
        if moved > 8:
            self._poly = [(ox, oy)]
            for dx, dy in self._dirs:
                dist_hit = radius
                for d in range(self.STEP, radius+self.STEP, self.STEP):
                    if self.gmap.is_wall(ox+dx*d, oy+dy*d):
                        dist_hit = d - self.STEP
                        break
                self._poly.append((ox+dx*dist_hit, oy+dy*dist_hit))
            self._last_ox, self._last_oy = ox, oy

    def get_screen_poly(self, cam_x: int, cam_y: int):
        return [(int(px-cam_x), int(py-cam_y)) for px, py in self._poly]

    def has_los(self, ox, oy, tx, ty, radius: int) -> bool:
        dx, dy = tx-ox, ty-oy
        dist = math.hypot(dx, dy)
        if dist == 0 or dist > radius:
            return False
        steps = max(1, int(dist/self.STEP))
        sdx, sdy = dx/steps, dy/steps
        for i in range(1, steps):
            if self.gmap.is_wall(ox+sdx*i, oy+sdy*i):
                return False
        return True


# ═════════════════════════════════════════════════════════════
#  ДЕНЬ / НОЧЬ — настоящая темнота
# ═════════════════════════════════════════════════════════════
class DayNight:
    PHASES = [2000, 300, 1800, 300]  # день, закат, ночь, рассвет

    def __init__(self):
        self.tick  = 0
        self.total = sum(self.PHASES)
        self._ov   = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        # Звёзды
        self._stars = [(random.randint(0, SCREEN_W), random.randint(0, SCREEN_H),
                        random.randint(1, 3), random.random())
                       for _ in range(200)]

    def update(self):
        self.tick = (self.tick+1) % self.total

    def _night_alpha(self) -> float:
        day, dusk, night, dawn = self.PHASES
        t = self.tick
        if t < day:
            return 0.0
        t -= day
        if t < dusk:
            return t/dusk
        t -= dusk
        if t < night:
            return 1.0
        t -= night
        return 1.0 - t/dawn

    @property
    def phase(self) -> str:
        t = self.tick
        d, du, n, da = self.PHASES
        if t < d:           return "ДЕНЬ"
        elif t < d+du:      return "ЗАКАТ"
        elif t < d+du+n:    return "НОЧЬ"
        else:               return "РАССВЕТ"

    @property
    def is_night(self) -> bool:
        return self._night_alpha() > 0.5

    @property
    def night_alpha(self) -> float:
        return self._night_alpha()

    @property
    def progress(self) -> float:
        return self.tick / self.total

    @property
    def ambient_temp(self) -> float:
        a = self._night_alpha()
        return AMBIENT_NIGHT_C + (AMBIENT_DAY_C - AMBIENT_NIGHT_C) * (1-a)

    @property
    def sun_angle(self) -> float:
        """Угол солнца: 0=восход, 90=полдень, 180=закат"""
        day, dusk, night, dawn = self.PHASES
        t = self.tick
        if t < day:
            return 30 + 120 * t/day   # восход → закат
        elif t < day+dusk:
            return 150 + 30 * (t-day)/dusk
        else:
            return 0.0  # ночь

    def draw_sky(self, surf: pygame.Surface):
        """Рисуем небо (фон за пределами карты) + звёзды"""
        alpha = self._night_alpha()
        if alpha < 0.01:
            return
        # Звёзды появляются ночью
        if alpha > 0.3:
            for sx, sy, sr, phase in self._stars:
                # Мерцание
                twinkle = 0.6 + 0.4*math.sin(pygame.time.get_ticks()*0.001*phase*6)
                star_alpha = int(220 * alpha * twinkle * min(1.0, (alpha-0.3)/0.4))
                if star_alpha > 20:
                    star_s = pygame.Surface((sr*2+2, sr*2+2), pygame.SRCALPHA)
                    pygame.draw.circle(star_s, (200, 210, 255, star_alpha), (sr+1, sr+1), sr)
                    surf.blit(star_s, (sx-sr-1, sy-sr-1))

    def draw_overlay(self, surf: pygame.Surface):
        """Дневной/ночной оверлей — при полной ночи ОЧЕНЬ тёмно"""
        alpha = self._night_alpha()
        if alpha < 0.01:
            return
        # Ночной оверлей — почти непрозрачный синий/чёрный
        # При alpha=1.0: 245 из 255 — практически не видно ничего
        night_opacity = int(240 * alpha)
        self._ov.fill((4, 6, 22, night_opacity))
        surf.blit(self._ov, (0, 0))

        # Закат/рассвет — цветовые тона
        if self.phase == "ЗАКАТ":
            day, dusk = self.PHASES[0], self.PHASES[1]
            t2 = (self.tick - day) / dusk
            sunset_s = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
            sunset_s.fill((180, 60, 20, int(80*t2)))
            surf.blit(sunset_s, (0, 0))
        elif self.phase == "РАССВЕТ":
            day, dusk, night, dawn = self.PHASES
            t2 = (self.tick - day - dusk - night) / dawn
            dawn_s = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
            dawn_s.fill((200, 100, 40, int(60*(1-t2))))
            surf.blit(dawn_s, (0, 0))

    def night_vision_radius(self, has_spotlight: bool) -> int:
        """Радиус видимости ночью — очень маленький без прожектора"""
        a = self._night_alpha()
        base = int(360 - 280 * a)  # днём 360, ночью 80 пикс
        if has_spotlight:
            base += 200  # прожектор даёт +200 пикс
        return base

    def draw_night_visibility(self, surf: pygame.Surface,
                               vis_poly_screen,
                               sx: int, sy: int,
                               radius: int,
                               has_spotlight: bool):
        """
        Рисуем ночное затемнение с дыркой видимости через raycast.
        НЕ видно сквозь стены.
        """
        if not self.is_night and self._night_alpha() < 0.05:
            return

        alpha = self._night_alpha()
        # Основное затемнение — ПОЧТИ ПОЛНОЕ в ночи
        dark = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        darkness = int(242 * alpha)
        dark.fill((4, 6, 22, darkness))

        # Вырезаем полигон видимости (с учётом стен!)
        if vis_poly_screen and len(vis_poly_screen) >= 3:
            pygame.draw.polygon(dark, (0, 0, 0, 0), vis_poly_screen)

            # Плавный край зоны видимости
            if has_spotlight:
                spot_col = (220, 200, 120, int(60*alpha))
            else:
                spot_col = (15, 18, 40, int(40*alpha))

            for dr in range(0, 45, 8):
                a_edge = int(darkness * dr/45)
                pygame.draw.circle(dark, (4, 6, 22, a_edge), (sx, sy), radius+dr, 10)

        surf.blit(dark, (0, 0))

        # Ореол прожектора (конусный)
        if has_spotlight and alpha > 0.1:
            spot = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
            spot_r = radius + 30
            for r2 in range(spot_r, spot_r-80, -15):
                if r2 > 0:
                    t2 = (spot_r - r2) / 80.0
                    spot_alpha = int(25 * t2 * alpha)
                    pygame.draw.circle(spot, (220, 200, 120, spot_alpha), (sx, sy), r2, 12)
            surf.blit(spot, (0, 0))


# ═════════════════════════════════════════════════════════════
#  ИИ АНАЛИЗАТОР
# ═════════════════════════════════════════════════════════════
class AIAnalyzer:
    RANGE     = 96
    SCAN_TIME = 150

    UNKNOWN   = 0
    SCANNING  = 1
    HEALTHY   = 2
    WOUNDED   = 3
    KIA       = 4

    LABELS = {0:"НЕИЗВЕСТНО", 1:"СКАНИРОВАНИЕ...",
              2:"ЖИВОЙ / ЗДОРОВ", 3:"РАНЕН — НУЖНА ЭВАКУАЦИЯ",
              4:"ПОГИБ / КИА"}
    COLORS = {0: LIGHT_GRAY, 1: YELLOW, 2: BRIGHT_GREEN,
              3: BRIGHT_RED,  4: GRAY}

    def __init__(self, sounds: SoundBank):
        self.sounds   = sounds
        self.records  = {}
        self._beep_cd = 0
        self._last_wounded_alert = set()

    def update(self, dx: float, dy: float, soldiers: list):
        self._beep_cd = max(0, self._beep_cd-1)
        active = set()

        for s in soldiers:
            if s.rescued or s.carried:
                continue
            sid = id(s)
            dist = math.hypot(s.x-dx, s.y-dy)
            if dist > self.RANGE:
                continue
            active.add(sid)

            if sid not in self.records:
                self.records[sid] = {
                    'status': self.SCANNING, 'progress': 0.0, 'ref': s
                }
            rec = self.records[sid]

            if rec['status'] == self.SCANNING:
                rec['progress'] += 1/self.SCAN_TIME
                if self._beep_cd == 0:
                    self.sounds.play('beep', 0.15)
                    self._beep_cd = 18
                if rec['progress'] >= 1.0:
                    rec['progress'] = 1.0
                    if s.dead:
                        rec['status'] = self.KIA
                    elif s.wounded:
                        rec['status'] = self.WOUNDED
                        if sid not in self._last_wounded_alert:
                            self.sounds.play('alert', 0.6)
                            self._last_wounded_alert.add(sid)
                    else:
                        rec['status'] = self.HEALTHY
                        self.sounds.play('ping', 0.28)

        for sid in list(self.records):
            if sid not in active:
                if self.records[sid]['status'] == self.SCANNING:
                    del self.records[sid]

    def status(self, s) -> int:
        return self.records.get(id(s), {}).get('status', self.UNKNOWN)

    def progress(self, s) -> float:
        return self.records.get(id(s), {}).get('progress', 0.0)


# ═════════════════════════════════════════════════════════════
#  СОЛДАТ — с физической температурой и поведением
# ═════════════════════════════════════════════════════════════
class Soldier:
    PATROL_SPD = 0.55

    def __init__(self, x, y, team='friendly', wounded=False, dead=False):
        self.x, self.y  = float(x), float(y)
        self.team    = team
        self.wounded = wounded
        self.dead    = dead
        self.carried = False
        self.rescued = False

        # Физическая температура тела
        if dead:
            self.temp_c = DEAD_TEMP_INIT - random.uniform(0, 8)  # уже успел остыть
        elif wounded:
            self.temp_c = WOUNDED_TEMP_C + random.uniform(-1.5, 1.5)
        else:
            self.temp_c = BODY_TEMP_C + random.uniform(-0.5, 0.5)

        self._heat    = self.temp_c    # алиас для обратной совместимости
        self._patrol_ang = random.uniform(0, 360)
        self._patrol_tmr = random.randint(60, 240)
        self._step_tmr   = 0
        self._anim_t     = random.randint(0, 120)

        # Прогресс ухудшения раненого (гипотермия)
        self._wound_progress = 0.0

    @property
    def heat(self) -> float:
        """Для совместимости со старым кодом — возвращаем 0..255"""
        t_norm = (self.temp_c - 20.0) / 20.0
        return max(0, min(255, int(t_norm * 255)))

    def update(self, gmap: GameMap, physics: ThermalPhysics,
               ambient_c: float, dt: float = DT_GAME):
        self._anim_t += 1

        # Обновление температуры по физике
        self.temp_c = physics.body_temp_after_dt(
            self.temp_c, self.dead, self.wounded, ambient_c, dt
        )
        # Радиационные потери (малые)
        rad_loss = physics.radiation_loss(self.temp_c)
        self.temp_c += rad_loss * dt * 0.1

        if self.rescued or self.carried or self.wounded or self.dead:
            return

        # Патруль
        self._patrol_tmr -= 1
        if self._patrol_tmr <= 0:
            self._patrol_ang = random.uniform(0, 360)
            self._patrol_tmr = random.randint(80, 260)

        rad = math.radians(self._patrol_ang)
        nx = self.x + math.cos(rad) * self.PATROL_SPD
        ny = self.y + math.sin(rad) * self.PATROL_SPD
        if not gmap.is_wall(nx, ny) and not gmap.is_water(nx, ny):
            self.x, self.y = nx, ny
        else:
            self._patrol_ang = random.uniform(0, 360)

    def draw(self, surf, cam_x, cam_y, thermal=False,
             vis_sys: Optional[VisibilitySystem] = None,
             drone_x=0.0, drone_y=0.0, vis_radius=200,
             night_alpha=0.0, ambient_c=AMBIENT_DAY_C):
        if self.rescued:
            return
        sx = int(self.x - cam_x)
        sy = int(self.y - cam_y)
        if not (-55 <= sx <= SCREEN_W+55 and -55 <= sy <= SCREEN_H+55):
            return

        if not thermal:
            # В обычном режиме: ночью солдаты НЕ видны без LoS
            if night_alpha > 0.1 and vis_sys is not None:
                # Проверяем видимость через raycast
                if not vis_sys.has_los(drone_x, drone_y, self.x, self.y, vis_radius):
                    return  # не видно — не рисуем
                # Уменьшаем яркость с ростом ночи
                if night_alpha > 0.5:
                    # Очень тёмно — почти не видно даже в конусе
                    # Рисуем только силуэт
                    pass

        heat_vis = min(1.0, max(0.0, (self.temp_c - ambient_c - 5) / 20.0))
        draw_soldier_v2(surf, sx, sy, self.wounded, self.dead,
                        self.team, thermal, heat_vis)

    def draw_indicator(self, surf, cam_x, cam_y, analyzer: AIAnalyzer,
                       night_alpha: float = 0.0):
        """Индикаторы видны только если солдат обнаружен анализатором"""
        if self.rescued or self.carried:
            return
        sx = int(self.x - cam_x)
        sy = int(self.y - cam_y)
        st = analyzer.status(self)
        if st == AIAnalyzer.UNKNOWN:
            return

        # Ночью индикаторы менее яркие
        alpha_mod = int(255 * (1.0 - night_alpha * 0.5))
        col = AIAnalyzer.COLORS[st]
        bar_y = sy - 44

        if st == AIAnalyzer.SCANNING:
            prog = analyzer.progress(self)
            bar_surf = pygame.Surface((46, 9), pygame.SRCALPHA)
            pygame.draw.rect(bar_surf, (*DARK_GRAY, alpha_mod), (0, 0, 46, 9))
            pygame.draw.rect(bar_surf, (*YELLOW, alpha_mod), (0, 0, int(46*prog), 9))
            pygame.draw.rect(bar_surf, (*GRAY, alpha_mod), (0, 0, 46, 9), 1)
            surf.blit(bar_surf, (sx-23, bar_y))
        else:
            ind = pygame.Surface((14, 14), pygame.SRCALPHA)
            pygame.draw.circle(ind, (*col, alpha_mod), (7, 7), 6)
            pygame.draw.circle(ind, (255, 255, 255, alpha_mod), (7, 7), 6, 1)
            surf.blit(ind, (sx-7, bar_y))
            if st == AIAnalyzer.WOUNDED:
                if pygame.time.get_ticks() % 900 < 550:
                    fnt = pygame.font.SysFont('consolas', 11)
                    t2 = fnt.render("SPACE=ПОДОБРАТЬ", True, BRIGHT_RED)
                    t2.set_alpha(alpha_mod)
                    surf.blit(t2, (sx-t2.get_width()//2, bar_y-16))
                    # Температура раненого
                    temp_str = f"{self.temp_c:.1f}°C"
                    temp_s = fnt.render(temp_str, True, (100, 180, 255))
                    temp_s.set_alpha(alpha_mod)
                    surf.blit(temp_s, (sx-temp_s.get_width()//2, bar_y+16))


# ═════════════════════════════════════════════════════════════
#  ДРОН
# ═════════════════════════════════════════════════════════════
class Drone:
    MAX_SPD      = 4.5
    ACCEL        = 0.28
    FRICTION     = 0.862
    BATT_MAX     = 9000       # ~150 сек при FPS=60
    CARRY_MULT   = 0.70
    WOBBLE_AMP   = 0.38
    WOBBLE_FREQ  = 0.056
    BODY_TEMP_C  = 42.0       # Дрон нагревается от моторов
    HOVER_TEMP_C = 38.0       # В режиме парения

    def __init__(self, x: float, y: float):
        self.x, self.y   = float(x), float(y)
        self.vx = self.vy = 0.0
        self.angle       = 0.0
        self.thermal     = False
        self.spotlight   = False  # прожектор
        self.carrying: Optional[Soldier] = None
        self.battery     = self.BATT_MAX
        self._wb_t       = 0.0
        self._surf_d     = make_drone_surf(False)
        self._surf_t     = make_drone_surf(True)
        self._spot_surf  = make_drone_spotlight_surf(280)
        self.temp_c      = self.HOVER_TEMP_C
        # Физика коллизий
        self.collision_r = 22

    @property
    def heat(self) -> float:
        return 255  # дрон всегда виден в тепловизоре

    def _input(self, keys):
        ax = ay = 0.0
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:  ax = -1.0
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]: ax =  1.0
        if keys[pygame.K_w] or keys[pygame.K_UP]:    ay = -1.0
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:  ay =  1.0
        if ax and ay:
            ax *= 0.7071; ay *= 0.7071
        return ax, ay

    def update(self, keys, gmap: GameMap, parts: Particles,
               ambient_c: float, physics: ThermalPhysics):
        ax, ay = self._input(keys)
        moving = bool(ax or ay)

        # Батарея
        drain = 1.2 if moving else 0.48
        if self.spotlight:
            drain += 0.3   # прожектор тратит энергию
        if self.carrying:
            drain += 0.2
        self.battery = max(0, self.battery - drain)

        cm = self.CARRY_MULT if self.carrying else 1.0
        bat_frac = max(0.1, self.battery / self.BATT_MAX)
        acc = self.ACCEL * cm * bat_frac

        self.vx += ax * acc
        self.vy += ay * acc
        spd = math.hypot(self.vx, self.vy)
        msp = self.MAX_SPD * cm
        if spd > msp:
            self.vx = self.vx/spd * msp
            self.vy = self.vy/spd * msp

        self.vx *= self.FRICTION
        self.vy *= self.FRICTION

        if moving:
            target = math.degrees(math.atan2(ay, ax)) + 90
            diff = (target - self.angle + 180) % 360 - 180
            self.angle += diff * 0.12

        # Парение
        self._wb_t += self.WOBBLE_FREQ
        wobble = math.sin(self._wb_t) * self.WOBBLE_AMP

        # Коллизии (более точные)
        cr = self.collision_r
        nx = self.x + self.vx
        ny = self.y + self.vy + wobble
        # X
        if not (gmap.is_wall(nx-cr, self.y) or gmap.is_wall(nx+cr, self.y)):
            self.x = nx
        else:
            self.vx *= -0.22
            # Частицы удара
            parts.sparks(self.x, self.y, 4)
        # Y
        if not (gmap.is_wall(self.x, ny-cr) or gmap.is_wall(self.x, ny+cr)):
            self.y = ny
        else:
            self.vy *= -0.22
            parts.sparks(self.x, self.y, 4)

        # Границы
        self.x = max(42, min(gmap.pw-42, self.x))
        self.y = max(42, min(gmap.ph-42, self.y))

        if self.carrying:
            self.carrying.x = self.x
            self.carrying.y = self.y + 28

        # Температура дрона — нагрев моторов
        if moving:
            self.temp_c += (self.BODY_TEMP_C - self.temp_c) * 0.02
        else:
            self.temp_c += (self.HOVER_TEMP_C - self.temp_c) * 0.01
        # Конвекция с окружающей средой
        self.temp_c += (ambient_c - self.temp_c) * 0.001

        # Частицы
        if moving and random.random() < 0.5:
            parts.smoke(self.x + random.uniform(-10, 10), self.y+22, 1)

    def draw(self, surf: pygame.Surface, cam_x: int, cam_y: int):
        sx, sy = int(self.x-cam_x), int(self.y-cam_y)

        # Прожектор — рисуем под дроном
        if self.spotlight:
            spot_r = 280
            spot = pygame.Surface((spot_r*2, spot_r*2), pygame.SRCALPHA)
            for r in range(spot_r, 0, -20):
                t = 1 - r/spot_r
                a = int(35 * t**0.6)
                pygame.draw.circle(spot, (230, 215, 130, a), (spot_r, spot_r), r)
            surf.blit(spot, (sx-spot_r, sy-spot_r), special_flags=pygame.BLEND_ADD)

        sp = self._surf_t if self.thermal else self._surf_d
        rot = pygame.transform.rotate(sp, -self.angle)
        r2 = rot.get_rect(center=(sx, sy))
        surf.blit(rot, r2.topleft)

        if self.carrying:
            pygame.draw.line(surf, LIGHT_GRAY, (sx, sy+14), (sx, sy+26), 2)
            pygame.draw.circle(surf, YELLOW, (sx, sy+26), 4, 2)

    def draw_carry_halo(self, surf, cam_x, cam_y, frame):
        if not self.carrying:
            return
        sx, sy = int(self.x-cam_x), int(self.y-cam_y)
        pr = int(32+6*math.sin(frame*0.11))
        h_surf = pygame.Surface((pr*2+4, pr*2+4), pygame.SRCALPHA)
        pygame.draw.circle(h_surf, (255, 210, 40, 160), (pr+2, pr+2), pr, 2)
        surf.blit(h_surf, (sx-pr-2, sy-pr-2))

    def toggle_thermal(self):
        self.thermal = not self.thermal

    def toggle_spotlight(self):
        self.spotlight = not self.spotlight

    def try_pickup(self, soldiers, analyzer: AIAnalyzer) -> Optional['Soldier']:
        if self.carrying:
            return None
        for s in soldiers:
            if s.wounded and not s.carried and not s.rescued:
                if math.hypot(s.x-self.x, s.y-self.y) < 58:
                    if analyzer.status(s) == AIAnalyzer.WOUNDED:
                        s.carried = True
                        self.carrying = s
                        return s
        return None

    def drop(self) -> Optional['Soldier']:
        if self.carrying:
            s = self.carrying
            s.carried = False
            self.carrying = None
            return s
        return None

    def emergency_charge(self) -> bool:
        """Аварийная зарядка — 10% заряда, 3 секунды"""
        if self.battery < self.BATT_MAX * 0.8:
            self.battery = min(self.BATT_MAX, self.battery + self.BATT_MAX * 0.10)
            return True
        return False


# ═════════════════════════════════════════════════════════════
#  ЗОНА ЭВАКУАЦИИ
# ═════════════════════════════════════════════════════════════
class Extraction:
    R = 62

    def __init__(self, x: float, y: float):
        self.x, self.y = float(x), float(y)
        self.count = 0
        self._t    = 0

    def update(self):
        self._t = (self._t+1) % 120

    def in_zone(self, drone: Drone) -> bool:
        return math.hypot(drone.x-self.x, drone.y-self.y) < self.R

    def receive(self, drone: Drone, sounds: SoundBank) -> bool:
        if drone.carrying and self.in_zone(drone):
            s = drone.carrying
            s.rescued = True
            s.carried = False
            drone.carrying = None
            self.count += 1
            sounds.play('success', 0.65)
            return True
        return False

    def draw(self, surf, cam_x, cam_y, thermal=False, night_alpha=0.0):
        sx, sy = int(self.x-cam_x), int(self.y-cam_y)
        pr = int(self.R + 8*math.sin(self._t*0.105))

        if thermal:
            c1 = (30, 28, 50)
            c2 = (20, 18, 38)
        else:
            c1 = (0,  220, 80)
            c2 = (0,  160, 58)

        # Ночью зона подсвечивается зелёным
        if not thermal and night_alpha > 0.2:
            glow = pygame.Surface((pr*2+40, pr*2+40), pygame.SRCALPHA)
            ga = int(80 * night_alpha)
            pygame.draw.circle(glow, (0, 220, 80, ga), (pr+20, pr+20), pr+20)
            surf.blit(glow, (sx-pr-20, sy-pr-20))

        pygame.draw.circle(surf, c1, (sx, sy), pr, 3)
        pygame.draw.circle(surf, c2, (sx, sy), self.R-16, 2)

        # H (вертикальный посадочный знак)
        hw = 15
        lines = [
            [(sx-hw, sy-20),(sx-hw, sy+20)],
            [(sx+hw, sy-20),(sx+hw, sy+20)],
            [(sx-hw, sy),   (sx+hw, sy)],
        ]
        for pts in lines:
            pygame.draw.line(surf, c1, pts[0], pts[1], 3)

        # Вращающиеся маркеры
        for i in range(4):
            a = math.radians(i*90 + self._t*3.0)
            ax2 = int(sx + math.cos(a)*(pr+12))
            ay2 = int(sy + math.sin(a)*(pr+12))
            pygame.draw.circle(surf, c2, (ax2, ay2), 5)

        # Счётчик
        if not thermal:
            fnt = pygame.font.SysFont('consolas', 14, bold=True)
            ct = fnt.render(f"ЭВАК: {self.count}", True, c1)
            surf.blit(ct, (sx-ct.get_width()//2, sy+pr+6))


# ═════════════════════════════════════════════════════════════
#  HUD — улучшенный с температурными данными
# ═════════════════════════════════════════════════════════════
class HUD:
    def __init__(self):
        self.f_big  = pygame.font.SysFont('consolas', 34, bold=True)
        self.f_med  = pygame.font.SysFont('consolas', 20, bold=True)
        self.f_sm   = pygame.font.SysFont('consolas', 13)
        self.f_tiny = pygame.font.SysFont('consolas', 11)
        self._msgs  = []

    def msg(self, text: str, dur=180, col=WHITE):
        if not any(t == text for t, _, _ in self._msgs):
            self._msgs.append((text, dur, col))

    def update(self):
        self._msgs = [(t, d-1, c) for t, d, c in self._msgs if d > 1]

    def _bar(self, surf, x, y, w, h, frac, col, border=True):
        frac = max(0, min(1, frac))
        pygame.draw.rect(surf, DARK_GRAY, (x, y, w, h), border_radius=3)
        if frac > 0:
            fill_col = col
            pygame.draw.rect(surf, fill_col, (x, y, int(w*frac), h), border_radius=3)
        if border:
            pygame.draw.rect(surf, GRAY, (x, y, w, h), 1, border_radius=3)

    def _panel(self, surf, x, y, w, h, border_col=(0, 175, 255, 110)):
        panel = pygame.Surface((w, h), pygame.SRCALPHA)
        panel.fill((8, 8, 18, 195))
        pygame.draw.rect(panel, border_col, (0, 0, w, h), 2)
        surf.blit(panel, (x, y))

    def draw(self, surf, drone: Drone, dn: DayNight,
             extr: Extraction, total_w: int, ana: AIAnalyzer,
             frame: int, physics: ThermalPhysics, soldiers: list,
             show_temp_debug: bool = False):

        # ── Левая панель ─────────────────────────────────────────
        px, py, pw, ph = 10, 10, 300, 185
        self._panel(surf, px, py, pw, ph)

        # Батарея
        bf = drone.battery / Drone.BATT_MAX
        bc = BRIGHT_GREEN if bf > 0.5 else (YELLOW if bf > 0.25 else BRIGHT_RED)
        lbl = self.f_sm.render("БАТАРЕЯ", True, LIGHT_GRAY)
        surf.blit(lbl, (px+8, py+8))
        self._bar(surf, px+8+lbl.get_width()+6, py+10, 170, 14, bf, bc)
        pct = self.f_sm.render(f"{int(bf*100)}%", True, bc)
        surf.blit(pct, (px+8+lbl.get_width()+6+174, py+8))

        # Скорость
        spd = math.hypot(drone.vx, drone.vy) / Drone.MAX_SPD
        lbl2 = self.f_sm.render("СКОРОСТЬ", True, LIGHT_GRAY)
        surf.blit(lbl2, (px+8, py+30))
        self._bar(surf, px+8+lbl2.get_width()+6, py+32, 140, 10, spd, TEAL)

        # Тепловизор
        tc = CYAN if drone.thermal else GRAY
        ts = self.f_sm.render(f"ТЕПЛОВИЗОР: {'ВКЛ' if drone.thermal else 'ВЫКЛ'}", True, tc)
        surf.blit(ts, (px+8, py+50))

        # Прожектор
        fc = (220, 200, 80) if drone.spotlight else GRAY
        fs = self.f_sm.render(f"ПРОЖЕКТОР: {'ВКЛ' if drone.spotlight else 'ВЫКЛ'}", True, fc)
        surf.blit(fs, (px+8, py+66))

        # Время суток
        phase_c = {"ДЕНЬ": YELLOW, "ЗАКАТ": ORANGE,
                   "НОЧЬ": (100, 150, 255), "РАССВЕТ": CREAM}
        pc = phase_c.get(dn.phase, WHITE)
        pt = self.f_sm.render(f"ВРЕМЯ: {dn.phase}", True, pc)
        surf.blit(pt, (px+8, py+82))

        # Температура окружающей среды
        amb = dn.ambient_temp
        amb_c = (100, 180, 255) if dn.is_night else YELLOW
        at = self.f_sm.render(f"ТЕМП. СРЕДЫ: {amb:.1f}°C", True, amb_c)
        surf.blit(at, (px+8, py+98))

        # Груз
        if drone.carrying:
            ct = self.f_sm.render("ГРУЗ: РАНЕНЫЙ НА БОРТУ", True, YELLOW)
        else:
            ct = self.f_sm.render("ГРУЗ: ПУСТО", True, GRAY)
        surf.blit(ct, (px+8, py+114))

        # Управление
        h1 = self.f_tiny.render("[T]=Тепловізор(ніч)  [F]=Прожектор  [E]=Зарядка", True, (75,75,88))
        h2 = self.f_tiny.render("[WASD/Стрілки]=Рух  [SPACE]=Підібрати/Здати", True, (75,75,88))
        h3 = self.f_tiny.render("[TAB]=Темп.дані  [P]=Чіт-меню  [ESC]=Налаштування", True, (75,75,88))
        surf.blit(h1, (px+8, py+134))
        surf.blit(h2, (px+8, py+148))
        surf.blit(h3, (px+8, py+162))

        # ── Правая панель миссии ──────────────────────────────────
        mx, my, mw, mh = SCREEN_W-230, 10, 220, 96
        self._panel(surf, mx, my, mw, mh, (0, 200, 80, 110))
        ms_t = self.f_sm.render("СТАТУС МИССИИ", True, BRIGHT_GREEN)
        surf.blit(ms_t, (mx+8, my+8))
        rc = extr.count
        rs_t = self.f_med.render(f"ЭВАК: {rc}/{total_w}", True, WHITE)
        surf.blit(rs_t, (mx+8, my+28))
        self._bar(surf, mx+8, my+62, mw-16, 14, rc/max(1,total_w), BRIGHT_GREEN)
        prog_t = self.f_sm.render(f"{int(rc/max(1,total_w)*100)}%", True, BRIGHT_GREEN)
        surf.blit(prog_t, (mx+8+mw-16+4, my+60))

        # Температура дрона
        drone_tc = self.f_tiny.render(f"T_дрон: {drone.temp_c:.1f}°C", True, (100,200,255))
        surf.blit(drone_tc, (mx+8, my+78))

        # ── ИИ Анализ панель ─────────────────────────────────────
        active = [(rec['status'], rec.get('ref'))
                  for rec in ana.records.values()
                  if rec['status'] != AIAnalyzer.UNKNOWN]
        if active:
            aph = 26 + len(active)*26
            apx, apy = 10, SCREEN_H - aph - 48
            self._panel(surf, apx, apy, 276, aph, (0, 145, 255, 90))
            ah = self.f_sm.render("ИИ АНАЛИЗАТОР", True, CYAN)
            surf.blit(ah, (apx+8, apy+4))
            for i, (st, sol) in enumerate(active):
                col2 = AIAnalyzer.COLORS.get(st, WHITE)
                lbl3 = AIAnalyzer.LABELS.get(st, "?")
                iy = apy + 24 + i*26
                pygame.draw.circle(surf, col2, (apx+12, iy+8), 5)
                lt = self.f_sm.render(lbl3, True, col2)
                surf.blit(lt, (apx+22, iy+2))
                if st == AIAnalyzer.SCANNING and sol:
                    prg = ana.progress(sol)
                    self._bar(surf, apx+142, iy+4, 120, 9, prg, YELLOW)
                elif st == AIAnalyzer.WOUNDED and sol:
                    # Показываем температуру раненого
                    temp_str = f"{sol.temp_c:.1f}°C"
                    ts2 = self.f_tiny.render(temp_str, True, (100, 200, 255))
                    surf.blit(ts2, (apx+200, iy+4))

        # ── Ночное предупреждение ─────────────────────────────────
        if dn.is_night and not drone.thermal:
            na = dn.night_alpha
            pulse = int(abs(math.sin(frame*0.08)) * 200 + 30)
            if na > 0.7:
                warn_s = pygame.Surface((SCREEN_W, 32), pygame.SRCALPHA)
                warn_s.fill((80, 0, 0, pulse))
                surf.blit(warn_s, (0, SCREEN_H//2 - 80))
                wt = self.f_med.render("⚠ НОЧЬ: ВКЛЮЧИ ТЕПЛОВИЗОР [T] ИЛИ ПРОЖЕКТОР [F] ⚠",
                                        True, (255, 80, 80, pulse))
                surf.blit(wt, (SCREEN_W//2-wt.get_width()//2, SCREEN_H//2-76))

        # ── Температурная панель (TAB) ────────────────────────────
        if show_temp_debug:
            self._draw_temp_panel(surf, soldiers, physics, dn.ambient_temp)

        # ── Центральные сообщения ─────────────────────────────────
        my_pos = SCREEN_H//2 - 100
        for text, timer, col3 in self._msgs:
            al = min(255, timer*5)
            t_s = self.f_med.render(text, True, col3)
            t_s.set_alpha(al)
            surf.blit(t_s, (SCREEN_W//2-t_s.get_width()//2, my_pos))
            my_pos += 36

        # ── Критически низкий заряд ───────────────────────────────
        if drone.battery < 650 and frame%28 < 14:
            warn2 = self.f_med.render("⚠ КРИТИЧЕСКИ НИЗКИЙ ЗАРЯД — НАЖМИ [E] ⚠",
                                       True, BRIGHT_RED)
            surf.blit(warn2, (SCREEN_W//2-warn2.get_width()//2, SCREEN_H-54))

    def _draw_temp_panel(self, surf, soldiers, physics: ThermalPhysics,
                          ambient_c: float):
        """Отладочная панель температур"""
        pw, ph = 320, 260
        px2, py2 = SCREEN_W//2 - pw//2, SCREEN_H//2 - ph//2
        self._panel(surf, px2, py2, pw, ph, (0, 180, 255, 120))

        title = self.f_med.render("ТЕМПЕРАТУРНЫЕ ДАННЫЕ", True, CYAN)
        surf.blit(title, (px2+8, py2+8))

        amb_s = self.f_sm.render(f"Ambient: {ambient_c:.1f}°C", True, (150, 220, 255))
        surf.blit(amb_s, (px2+8, py2+34))

        y_off = py2 + 54
        alive = [s for s in soldiers if not s.rescued][:8]
        for i, s in enumerate(alive):
            status = "МЁРТВ" if s.dead else ("РАНЕН" if s.wounded else "ЖИВОЙ")
            col4 = GRAY if s.dead else (BRIGHT_RED if s.wounded else BRIGHT_GREEN)
            line = f"{status}: {s.temp_c:.2f}°C  Δ={s.temp_c-ambient_c:+.2f}"
            ts3 = self.f_tiny.render(line, True, col4)
            surf.blit(ts3, (px2+8, y_off + i*22))

        # Физические формулы
        formula_y = y_off + len(alive)*22 + 8
        f1 = self.f_tiny.render("dT/dt = -(hA/mc)(T-T_env)  [Newton]", True, (80,80,100))
        f2 = self.f_tiny.render("P_rad = ε·σ·A·(T⁴-T_env⁴) [Stefan-Boltzmann]", True, (80,80,100))
        surf.blit(f1, (px2+8, formula_y))
        surf.blit(f2, (px2+8, formula_y+14))


# ═════════════════════════════════════════════════════════════
#  МИНИКАРТА
# ═════════════════════════════════════════════════════════════
class Minimap:
    SCALE = 4

    def __init__(self, gmap: GameMap):
        self.scale = self.SCALE
        mw = gmap.cols * self.scale
        mh = gmap.rows * self.scale
        self._base = pygame.Surface((mw, mh), pygame.SRCALPHA)
        self._base.fill((16, 16, 24, 215))
        for r in range(gmap.rows):
            for c in range(gmap.cols):
                t = gmap.tiles[r][c]
                COLS = {
                    TILE_GROUND: (125, 108, 72), TILE_WALL: (82, 68, 52),
                    TILE_RUBBLE: (88, 76, 55),   TILE_ROAD: (65, 65, 70),
                    TILE_WATER:  (36, 65, 125),  TILE_GRASS: (26, 66, 26),
                    TILE_SAND_D: (158, 140, 88),
                }
                col5 = COLS.get(t, (115, 98, 68))
                pygame.draw.rect(self._base, col5,
                                 (c*self.scale, r*self.scale, self.scale, self.scale))
        self.w, self.h = mw, mh

    def draw(self, surf, drone: Drone, soldiers, extr: Extraction,
             cam_x, cam_y, font_sm, night_alpha=0.0):
        mm = self._base.copy()
        sc = self.scale

        # Ночью миникарта темнее
        if night_alpha > 0.1:
            night_ov = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
            night_ov.fill((0, 0, 20, int(100*night_alpha)))
            mm.blit(night_ov, (0, 0))

        # Зона эвакуации
        ec = int(extr.x/TILE*sc)
        er = int(extr.y/TILE*sc)
        pygame.draw.circle(mm, BRIGHT_GREEN, (ec, er), 6, 2)
        pygame.draw.circle(mm, (0,255,80,180), (ec, er), 4)

        # Солдаты
        for s in soldiers:
            if s.rescued: continue
            mc2 = int(s.x/TILE*sc)
            mr2 = int(s.y/TILE*sc)
            if s.dead:
                c6 = GRAY
            elif s.wounded:
                c6 = BRIGHT_RED
            elif s.team == 'friendly':
                c6 = GREEN
            else:
                c6 = ORANGE
            # Ночью на миникарте видны только раненые (тепловой след)
            if night_alpha > 0.6 and not s.wounded and not s.dead:
                continue  # здоровые не видны ночью без тепловизора
            pygame.draw.circle(mm, c6, (mc2, mr2), 2)

        # Горящие объекты
        for (fx, fy, _) in [b for b in []] :  # расширяемо
            pass

        # Дрон
        dc = int(drone.x/TILE*sc)
        dr = int(drone.y/TILE*sc)
        pygame.draw.circle(mm, CYAN, (dc, dr), 4)
        pygame.draw.circle(mm, WHITE, (dc, dr), 4, 1)

        # Вид камеры
        vx = int(cam_x/TILE*sc)
        vy = int(cam_y/TILE*sc)
        vw = int(SCREEN_W/TILE*sc)
        vh = int(SCREEN_H/TILE*sc)
        pygame.draw.rect(mm, (200, 200, 200, 50), (vx, vy, vw, vh), 1)

        pygame.draw.rect(mm, CYAN, (0, 0, self.w, self.h), 2)

        mx2 = SCREEN_W - self.w - 10
        my2 = SCREEN_H - self.h - 44
        surf.blit(mm, (mx2, my2))

        lt2 = font_sm.render("ТАКТИЧЕСКАЯ КАРТА", True, CYAN)
        surf.blit(lt2, (mx2+4, my2+self.h+2))


# ═════════════════════════════════════════════════════════════
#  МЕНЮ НАЛАШТУВАНЬ (ESC)
# ═════════════════════════════════════════════════════════════
class SettingsMenu:
    OPTIONS = [
        "ПРОДОВЖИТИ ГРУ",
        "ПЕРЕЗАПУСТИТИ МІСІЮ",
        "ВИЙТИ З ГРИ",
    ]

    def __init__(self):
        self.f_big  = pygame.font.SysFont('consolas', 38, bold=True)
        self.f_med  = pygame.font.SysFont('consolas', 22, bold=True)
        self.f_sm   = pygame.font.SysFont('consolas', 16)
        self.selected = 0
        self.visible  = False

    def toggle(self):
        self.visible = not self.visible
        self.selected = 0

    def handle_key(self, key) -> str:
        if key == pygame.K_ESCAPE:
            self.visible = False
            return 'resume'
        if key == pygame.K_UP:
            self.selected = (self.selected - 1) % len(self.OPTIONS)
        elif key == pygame.K_DOWN:
            self.selected = (self.selected + 1) % len(self.OPTIONS)
        elif key in (pygame.K_RETURN, pygame.K_SPACE):
            if self.selected == 0:
                self.visible = False
                return 'resume'
            elif self.selected == 1:
                self.visible = False
                return 'restart'
            elif self.selected == 2:
                return 'quit'
        return ''

    def draw(self, surf):
        if not self.visible:
            return
        ov = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 200))
        surf.blit(ov, (0, 0))
        pw, ph = 420, 320
        px = SCREEN_W // 2 - pw // 2
        py = SCREEN_H // 2 - ph // 2
        panel = pygame.Surface((pw, ph), pygame.SRCALPHA)
        panel.fill((10, 14, 30, 245))
        pygame.draw.rect(panel, (0, 180, 255, 200), (0, 0, pw, ph), 3)
        surf.blit(panel, (px, py))
        title = self.f_big.render("НАЛАШТУВАННЯ", True, (0, 200, 255))
        surf.blit(title, (SCREEN_W // 2 - title.get_width() // 2, py + 20))
        pygame.draw.line(surf, (0, 120, 180), (px + 20, py + 72), (px + pw - 20, py + 72), 1)
        for i, opt in enumerate(self.OPTIONS):
            is_sel = i == self.selected
            col = (255, 220, 0) if is_sel else (180, 200, 220)
            prefix = "> " if is_sel else "  "
            t = self.f_med.render(prefix + opt, True, col)
            yy = py + 100 + i * 56
            if is_sel:
                hl = pygame.Surface((pw - 40, 36), pygame.SRCALPHA)
                hl.fill((0, 180, 255, 40))
                surf.blit(hl, (px + 20, yy - 4))
            surf.blit(t, (px + 36, yy))
        hint = self.f_sm.render("UP/DN -- вибір    Enter -- підтвердити    ESC -- продовжити", True, (80, 100, 130))
        surf.blit(hint, (SCREEN_W // 2 - hint.get_width() // 2, py + ph - 30))


# ═════════════════════════════════════════════════════════════
#  ЧІТ-МЕНЮ (P)
# ═════════════════════════════════════════════════════════════
class CheatMenu:
    OPTIONS = [
        ("ПОВНА БАТАРЕЯ",             'full_battery'),
        ("ВІДНОВИТИ ВСІХ ПОРАНЕНИХ",  'heal_all'),
        ("ТЕЛЕПОРТ ДО БАЗИ",          'teleport_base'),
        ("МИТТЄВА ПЕРЕМОГА",          'instant_win'),
        ("ПЕРЕКЛЮЧИТИ ДЕНЬ/НІЧ",      'toggle_daynight'),
        ("ЗАКРИТИ",                   'close'),
    ]

    def __init__(self):
        self.f_big  = pygame.font.SysFont('consolas', 30, bold=True)
        self.f_med  = pygame.font.SysFont('consolas', 20, bold=True)
        self.f_sm   = pygame.font.SysFont('consolas', 14)
        self.selected = 0
        self.visible  = False

    def toggle(self):
        self.visible = not self.visible
        self.selected = 0

    def handle_key(self, key) -> str:
        if key in (pygame.K_ESCAPE, pygame.K_p):
            self.visible = False
            return 'close'
        if key == pygame.K_UP:
            self.selected = (self.selected - 1) % len(self.OPTIONS)
        elif key == pygame.K_DOWN:
            self.selected = (self.selected + 1) % len(self.OPTIONS)
        elif key in (pygame.K_RETURN, pygame.K_SPACE):
            action = self.OPTIONS[self.selected][1]
            if action == 'close':
                self.visible = False
            return action
        return ''

    def draw(self, surf):
        if not self.visible:
            return
        ov = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 185))
        surf.blit(ov, (0, 0))
        pw, ph = 460, 80 + len(self.OPTIONS) * 50 + 40
        px = SCREEN_W // 2 - pw // 2
        py = SCREEN_H // 2 - ph // 2
        panel = pygame.Surface((pw, ph), pygame.SRCALPHA)
        panel.fill((10, 24, 14, 245))
        pygame.draw.rect(panel, (0, 255, 80, 200), (0, 0, pw, ph), 3)
        surf.blit(panel, (px, py))
        title = self.f_big.render("[CHEAT] ТЕСТУВАННЯ", True, (0, 255, 100))
        surf.blit(title, (SCREEN_W // 2 - title.get_width() // 2, py + 14))
        pygame.draw.line(surf, (0, 160, 60), (px + 20, py + 56), (px + pw - 20, py + 56), 1)
        for i, (label, _) in enumerate(self.OPTIONS):
            is_sel = i == self.selected
            col = (255, 255, 0) if is_sel else (160, 220, 160)
            prefix = "> " if is_sel else "  "
            t = self.f_med.render(prefix + label, True, col)
            yy = py + 68 + i * 50
            if is_sel:
                hl = pygame.Surface((pw - 40, 36), pygame.SRCALPHA)
                hl.fill((0, 255, 80, 35))
                surf.blit(hl, (px + 20, yy - 4))
            surf.blit(t, (px + 36, yy))
        hint = self.f_sm.render("UP/DN -- вибір    Enter -- активувати    P/ESC -- закрити", True, (60, 120, 70))
        surf.blit(hint, (SCREEN_W // 2 - hint.get_width() // 2, py + ph - 22))


# ═════════════════════════════════════════════════════════════
#  ГОЛОВНИЙ КЛАС ГРАВЦЯ
# ═════════════════════════════════════════════════════════════
class Game:
    N_WOUNDED = 9
    N_HEALTHY = 13
    N_ENEMY   = 6
    N_KIA     = 5

    def __init__(self):
        self.screen  = screen
        self.clock   = clock
        self.frame   = 0
        self.running = True
        self.over    = False
        self.victory = False
        self._show_temp = False

        # Подсистемы
        self.sounds   = SoundBank()
        self.physics  = ThermalPhysics()
        self.gmap     = GameMap()
        self.parts    = Particles()
        self.thermal  = ThermalImager(self.gmap, self.physics)
        self.vis_sys  = VisibilitySystem(self.gmap)
        self.dn       = DayNight()
        self.analyzer = AIAnalyzer(self.sounds)
        self.hud      = HUD()
        self.minimap  = Minimap(self.gmap)
        self.settings_menu = SettingsMenu()
        self.cheat_menu    = CheatMenu()

        # Добавляем источники огня в физику
        for (bx, by, is_fire) in self.gmap.barrels:
            if is_fire:
                self.physics.add_fire(bx, by, 120.0)

        # Камера
        self.cam_x = 0
        self.cam_y = 0

        # Зона эвакуации
        ex_x = self.gmap.pw // 2
        ex_y = self.gmap.ph // 2
        self.extraction = Extraction(ex_x, ex_y)

        # Дрон
        self.drone = Drone(ex_x + 95, ex_y)

        # Солдаты
        self.soldiers: List[Soldier] = []
        self._spawn_soldiers()

        # Звуковой канал гула двигателей
        self._hum_ch = None
        self._wind_ch = None
        try:
            ch = pygame.mixer.find_channel(True)
            if ch:
                self.sounds.sounds['hum'].set_volume(0.10)
                ch.play(self.sounds.sounds['hum'], loops=-1)
                self._hum_ch = ch
            # Ветер ночью
            ch2 = pygame.mixer.find_channel(True)
            if ch2:
                self.sounds.sounds['wind'].set_volume(0.0)
                ch2.play(self.sounds.sounds['wind'], loops=-1)
                self._wind_ch = ch2
        except Exception:
            pass

        # Таймер зарядки
        self._charge_cd = 0

        # Частицы огня (постоянные)
        self._fire_tick = 0

    # ── спавн солдат ─────────────────────────────────────────────
    def _spawn_soldiers(self):
        rng = random.Random(321)
        used = []

        def safe_pos(min_dist_ex=170, min_dist_used=45):
            for _ in range(400):
                x = rng.randint(TILE*2, (self.gmap.cols-2)*TILE)
                y = rng.randint(TILE*2, (self.gmap.rows-2)*TILE)
                if self.gmap.is_wall(x, y) or self.gmap.is_water(x, y):
                    continue
                if math.hypot(x-self.extraction.x, y-self.extraction.y) < min_dist_ex:
                    continue
                if any(math.hypot(x-ux, y-uy) < min_dist_used for ux, uy in used):
                    continue
                used.append((x, y))
                return float(x), float(y)
            return float(self.gmap.pw//4), float(self.gmap.ph//4)

        for _ in range(self.N_WOUNDED):
            x, y = safe_pos()
            self.soldiers.append(Soldier(x, y, 'friendly', wounded=True))
        for _ in range(self.N_HEALTHY):
            x, y = safe_pos()
            self.soldiers.append(Soldier(x, y, 'friendly'))
        for _ in range(self.N_ENEMY):
            x, y = safe_pos()
            self.soldiers.append(Soldier(x, y, 'enemy'))
        for _ in range(self.N_KIA):
            x, y = safe_pos(min_dist_ex=90)
            self.soldiers.append(
                Soldier(x, y, rng.choice(['friendly','enemy']),
                        wounded=False, dead=True))

    # ── камера ───────────────────────────────────────────────────
    def _update_cam(self):
        tx = int(self.drone.x - SCREEN_W//2)
        ty = int(self.drone.y - SCREEN_H//2)
        tx = max(0, min(self.gmap.pw-SCREEN_W, tx))
        ty = max(0, min(self.gmap.ph-SCREEN_H, ty))
        self.cam_x += int((tx - self.cam_x) * 0.10)
        self.cam_y += int((ty - self.cam_y) * 0.10)

    # ── події ──────────────────────────────────────────────────
    def _events(self):
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                self.running = False
            elif ev.type == pygame.KEYDOWN:
                # Якщо відкрите чіт-меню — передаємо керування йому
                if self.cheat_menu.visible:
                    action = self.cheat_menu.handle_key(ev.key)
                    self._apply_cheat(action)
                    continue
                # Якщо відкрите меню налаштувань — передаємо керування йому
                if self.settings_menu.visible:
                    action = self.settings_menu.handle_key(ev.key)
                    if action == 'quit':
                        self.running = False
                    elif action == 'restart':
                        self.__init__()
                    continue

                if ev.key == pygame.K_ESCAPE:
                    self.settings_menu.toggle()
                elif ev.key == pygame.K_p:
                    self.cheat_menu.toggle()
                elif ev.key == pygame.K_t:
                    # Тепловізор працює ТІЛЬКИ вночі
                    if self.dn.night_alpha < 0.35:
                        self.hud.msg("ТЕПЛОВІЗОР НЕДОСТУПНИЙ ВДЕНЬ", 120, ORANGE)
                        self.hud.msg("(вулиця нагріта — людей не видно)", 120, GRAY)
                    else:
                        self.drone.toggle_thermal()
                        self.sounds.play('click', 0.55)
                        state = "УВІМКНЕНий" if self.drone.thermal else "ВИМКНЕНИЙ"
                        self.hud.msg(f"ТЕПЛОВІЗОР {state}", 90, CYAN)
                        if self.drone.thermal:
                            self.sounds.play('thermal_ping', 0.4)
                elif ev.key == pygame.K_f:
                    self.drone.toggle_spotlight()
                    self.sounds.play('click', 0.4)
                    st = "УВІМКНЕНий" if self.drone.spotlight else "ВИМКНЕНИЙ"
                    self.hud.msg(f"ПРОЖЕКТОР {st}", 80,
                                  (220,200,80) if self.drone.spotlight else GRAY)
                elif ev.key == pygame.K_SPACE:
                    self._interact()
                elif ev.key == pygame.K_e:
                    self._emergency_charge()
                elif ev.key == pygame.K_TAB:
                    self._show_temp = not self._show_temp
                elif ev.key == pygame.K_r and self.over:
                    self.__init__()

    def _apply_cheat(self, action: str):
        if not action or action == 'close':
            return
        if action == 'full_battery':
            self.drone.battery = Drone.BATT_MAX
            self.hud.msg("[CHEAT] Повна батарея!", 120, YELLOW)
        elif action == 'heal_all':
            for s in self.soldiers:
                if s.wounded and not s.rescued:
                    s.wounded = False
                    s.temp_c  = BODY_TEMP_C
            self.hud.msg("[CHEAT] Всі поранені вилікувані!", 120, BRIGHT_GREEN)
        elif action == 'teleport_base':
            self.drone.x = float(self.extraction.x + 30)
            self.drone.y = float(self.extraction.y)
            self.drone.vx = self.drone.vy = 0.0
            self.hud.msg("[CHEAT] Телепорт до бази!", 120, CYAN)
        elif action == 'instant_win':
            for s in self.soldiers:
                if s.wounded:
                    s.rescued = True
                    s.carried = False
            self.drone.carrying = None
            self.extraction.count = sum(1 for s in self.soldiers if s.wounded)
            self.victory = True
            self.over    = True
            self.sounds.play('success', 0.9)
        elif action == 'toggle_daynight':
            d, du, n, da = self.dn.PHASES
            if self.dn.phase in ("ДЕНЬ",):
                self.dn.tick = d + du  # перемотуємо на початок ночі
            else:
                self.dn.tick = 0       # перемотуємо на початок дня
            # Якщо тепловізор увімкнений вдень — вимикаємо
            if self.dn.night_alpha < 0.35 and self.drone.thermal:
                self.drone.thermal = False
                self.hud.msg("Тепловізор вимкнено (день)", 90, ORANGE)
            self.hud.msg(f"[CHEAT] Час доби: {self.dn.phase}", 120, PURPLE)

    # ── аварійна зарядка ────────────────────────────────────────
    def _emergency_charge(self):
        if self._charge_cd > 0:
            self.hud.msg(f"Зарядка перезаряжается: {self._charge_cd//60}с", 60, GRAY)
            return
        if self.drone.emergency_charge():
            self._charge_cd = 600  # 10 секунд КД
            self.sounds.play('charge', 0.6)
            self.hud.msg("⚡ АВАРИЙНАЯ ЗАРЯДКА +10%", 130, YELLOW)
            self.parts.burst(self.drone.x, self.drone.y,
                              8, [(0,200,255),(100,255,255),(255,255,100)], 3, 30)
        else:
            self.hud.msg("Зарядка не нужна (>80%)", 80, GRAY)

    # ── взаимодействие ───────────────────────────────────────────
    def _interact(self):
        if self.drone.carrying:
            if self.extraction.in_zone(self.drone):
                if self.extraction.receive(self.drone, self.sounds):
                    self.hud.msg("✓ РАНЕНЫЙ ЭВАКУИРОВАН!", 200, BRIGHT_GREEN)
                    self.parts.burst(self.drone.x, self.drone.y,
                                      22, [BRIGHT_GREEN, GREEN, YELLOW], 3.8, 70)
                    total_w = sum(1 for s in self.soldiers if s.wounded)
                    if self.extraction.count >= total_w:
                        self.victory = True
                        self.over    = True
                        self.sounds.play('success', 0.9)
            else:
                dropped = self.drone.drop()
                if dropped:
                    self.hud.msg("Раненый выгружен", 90, YELLOW)
        else:
            picked = self.drone.try_pickup(self.soldiers, self.analyzer)
            if picked:
                self.sounds.play('pickup', 0.7)
                self.hud.msg("✓ РАНЕНЫЙ НА БОРТУ!", 160, YELLOW)
                self.parts.burst(picked.x, picked.y, 14,
                                  [YELLOW, WHITE, CREAM], 2.8, 50)
            else:
                dist_ex = math.hypot(self.drone.x-self.extraction.x,
                                     self.drone.y-self.extraction.y)
                if dist_ex < self.extraction.R + 38:
                    self.hud.msg("Нет груза для сдачи", 80, GRAY)
                else:
                    nearby = [
                        (math.hypot(s.x-self.drone.x, s.y-self.drone.y), s)
                        for s in self.soldiers
                        if s.wounded and not s.rescued and not s.carried
                        and self.analyzer.status(s) == AIAnalyzer.WOUNDED
                    ]
                    if nearby:
                        nearby.sort()
                        _, ns = nearby[0]
                        d = int(nearby[0][0])
                        self.hud.msg(f"Раненый в {d}м — подлети ближе!", 120, YELLOW)

    # ── обновление ───────────────────────────────────────────────
    def _update(self):
        keys = pygame.key.get_pressed()

        # Физика температуры
        ambient = self.dn.ambient_temp
        self.physics.set_ambient(ambient, self.dn.sun_angle)
        self.physics.update()

        # Дрон
        self.drone.update(keys, self.gmap, self.parts, ambient, self.physics)

        # Солдаты
        for s in self.soldiers:
            s.update(self.gmap, self.physics, ambient)

        # ИИ
        self.analyzer.update(self.drone.x, self.drone.y, self.soldiers)

        # Системы
        self.dn.update()
        self.extraction.update()
        self.parts.update()
        self.hud.update()
        self._update_cam()

        # Перезапекаємо нічні вогні будівель
        self.gmap.rebake_night(self.dn.night_alpha)

        # Тепловізор недоступний вдень — вимикаємо автоматично
        if self.dn.night_alpha < 0.35 and self.drone.thermal:
            self.drone.thermal = False
            self.hud.msg("ТЕПЛОВІЗОР ВИМКНЕНО (настав день)", 150, ORANGE)

        # Кулдаун зарядки
        self._charge_cd = max(0, self._charge_cd - 1)

        # Частицы огня от горящих бочек
        self._fire_tick += 1
        if self._fire_tick % 4 == 0:
            for (bx, by, is_fire) in self.gmap.barrels:
                if is_fire:
                    bsx = int(bx - self.cam_x)
                    bsy = int(by - self.cam_y)
                    if -50 <= bsx <= SCREEN_W+50 and -50 <= bsy <= SCREEN_H+50:
                        if random.random() < 0.7:
                            self.parts.fire_puff(bx, by, 2)
                        if random.random() < 0.3:
                            self.parts.smoke(bx, by+5, 1)

        # Звуки
        if self._hum_ch:
            spd = math.hypot(self.drone.vx, self.drone.vy) / Drone.MAX_SPD
            vol = 0.06 + 0.16*spd
            if self.drone.carrying:
                vol += 0.04
            self._hum_ch.set_volume(vol)

        # Ветер ночью
        if self._wind_ch:
            wind_vol = self.dn.night_alpha * 0.18
            self._wind_ch.set_volume(wind_vol)

        # Батарея исчерпана
        if self.drone.battery <= 0 and not self.over:
            self.over    = True
            self.victory = False
            self.sounds.play('fail', 0.7)
            self.hud.msg("БАТАРЕЯ ИСЧЕРПАНА!", 300, BRIGHT_RED)

        # Предупреждения
        if self.drone.battery < 900 and self.frame % 120 == 0:
            self.sounds.play('warn', 0.35)
            self.hud.msg("НИЗКИЙ ЗАРЯД БАТАРЕИ!", 80, RED)

        # Обновляем видимость
        vis_r = self.dn.night_vision_radius(self.drone.spotlight)
        self.vis_sys.rebuild(self.drone.x, self.drone.y, vis_r)

    # ── рендер мира ──────────────────────────────────────────────
    def _draw_world(self):
        cx, cy = self.cam_x, self.cam_y
        w, h   = SCREEN_W, SCREEN_H
        drone  = self.drone
        night_alpha = self.dn.night_alpha
        ambient_c   = self.dn.ambient_temp

        sx_screen = int(drone.x - cx)
        sy_screen = int(drone.y - cy)

        if drone.thermal:
            # ═══ ТЕПЛОВИЗОРНЫЙ РЕЖИМ ════════════════════════════
            self.thermal.render(
                self.screen,
                self.gmap.get_surf(True),
                drone.x, drone.y,
                cx, cy,
                [s for s in self.soldiers if not s.rescued],
                ambient_c,
                self.gmap.fire_positions
            )
            # Зона эвакуации
            self.extraction.draw(self.screen, cx, cy, thermal=True,
                                  night_alpha=night_alpha)
            # Дрон
            drone.draw(self.screen, cx, cy)
            drone.draw_carry_halo(self.screen, cx, cy, self.frame)
            # Кольцо сканирования
            self._scan_ring_thermal()

            # Рамка тепловизора
            self._draw_thermal_frame()

        else:
            # ═══ ОБЫЧНЫЙ РЕЖИМ ══════════════════════════════════
            self.screen.blit(self.gmap.get_surf(False), (0,0), (cx, cy, w, h))

            # Звёзды ночью
            self.dn.draw_sky(self.screen)

            # Горящие бочки (мировые координаты → экранные)
            # (уже отрисованы в запечённой поверхности)

            # Зона эвакуации
            self.extraction.draw(self.screen, cx, cy, thermal=False,
                                  night_alpha=night_alpha)

            # Солдаты — только в зоне видимости
            for s in self.soldiers:
                s.draw(self.screen, cx, cy, thermal=False,
                       vis_sys=self.vis_sys,
                       drone_x=drone.x, drone_y=drone.y,
                       vis_radius=self.dn.night_vision_radius(drone.spotlight),
                       night_alpha=night_alpha,
                       ambient_c=ambient_c)
                # Индикаторы только в зоне видимости
                if night_alpha < 0.5 or self.vis_sys.has_los(
                        drone.x, drone.y, s.x, s.y,
                        self.dn.night_vision_radius(drone.spotlight)):
                    s.draw_indicator(self.screen, cx, cy, self.analyzer, night_alpha)

            # Ночное затемнение с raycast-дырой
            vis_poly = self.vis_sys.get_screen_poly(cx, cy)
            vis_r = self.dn.night_vision_radius(drone.spotlight)
            self.dn.draw_night_visibility(
                self.screen, vis_poly,
                sx_screen, sy_screen,
                vis_r, drone.spotlight
            )

            # Дрон (поверх темноты)
            drone.draw(self.screen, cx, cy)
            drone.draw_carry_halo(self.screen, cx, cy, self.frame)
            # Кольцо сканирования
            self._scan_ring_normal()

        # Частицы (поверх всего)
        self.parts.draw(self.screen, cx, cy)

    def _draw_thermal_frame(self):
        """Рамка и виньетка тепловизора"""
        vign = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        for r in range(SCREEN_W//2, SCREEN_W//2 - 80, -12):
            if r > 0:
                a = int(60 * (1 - (r - SCREEN_W//2 + 80)/80))
                pygame.draw.ellipse(vign, (0, 0, 0, a),
                                    (-SCREEN_W//4, -SCREEN_H//4,
                                     SCREEN_W*3//2, SCREEN_H*3//2),
                                    max(1, (SCREEN_W//2-r)//3))
        self.screen.blit(vign, (0,0))
        # Рамка
        pygame.draw.rect(self.screen, (0, 220, 120), (0, 0, SCREEN_W, SCREEN_H), 3)
        # Метка
        fnt = pygame.font.SysFont('consolas', 12)
        ts = fnt.render("THERMAL VISION  [T]=OFF", True, (0, 220, 120))
        self.screen.blit(ts, (SCREEN_W-ts.get_width()-10, SCREEN_H-20))

    def _scan_ring_thermal(self):
        sx = int(self.drone.x - self.cam_x)
        sy = int(self.drone.y - self.cam_y)
        r  = AIAnalyzer.RANGE
        al = int(50 + 25*math.sin(self.frame*0.09))
        rs = pygame.Surface((r*2+6, r*2+6), pygame.SRCALPHA)
        pygame.draw.circle(rs, (80, 255, 120, al), (r+3, r+3), r, 2)
        # Пунктирные метки
        for i in range(8):
            a = math.radians(i*45 + self.frame*1.2)
            mx2 = int((r+3) + math.cos(a)*(r+6))
            my2 = int((r+3) + math.sin(a)*(r+6))
            pygame.draw.circle(rs, (80, 255, 120, al//2), (mx2, my2), 2)
        self.screen.blit(rs, (sx-r-3, sy-r-3))

    def _scan_ring_normal(self):
        sx = int(self.drone.x - self.cam_x)
        sy = int(self.drone.y - self.cam_y)
        r  = AIAnalyzer.RANGE
        al = int(28 + 16*math.sin(self.frame*0.09))
        rs = pygame.Surface((r*2+6, r*2+6), pygame.SRCALPHA)
        pygame.draw.circle(rs, (0, 200, 255, al), (r+3, r+3), r, 2)
        self.screen.blit(rs, (sx-r-3, sy-r-3))

    # ── экран конца ──────────────────────────────────────────────
    def _draw_gameover(self):
        ov = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 185))
        self.screen.blit(ov, (0,0))

        if self.victory:
            title_c = BRIGHT_GREEN
            title   = "✓ МИССИЯ ВЫПОЛНЕНА"
            sub     = f"Все {self.extraction.count} раненых эвакуированы!"
        else:
            title_c = BRIGHT_RED
            title   = "✗ МИССИЯ ПРОВАЛЕНА"
            sub     = "Заряд дрона исчерпан" if self.drone.battery <= 0 else "Миссия прервана"

        tw = self.hud.f_big.render(title, True, title_c)
        sw = self.hud.f_med.render(sub, True, WHITE)
        hw = self.hud.f_sm.render("Нажми R для перезапуска", True, LIGHT_GRAY)

        total_w = sum(1 for s in self.soldiers if s.wounded)
        batt_used = int((1 - self.drone.battery/Drone.BATT_MAX)*100)
        stat = self.hud.f_sm.render(
            f"Эвакуировано: {self.extraction.count}/{total_w}  |  "
            f"Батарея израсходована: {batt_used}%",
            True, LIGHT_GRAY)

        # Температурная статистика
        avg_dead_temp = 0.0
        dead_count = sum(1 for s in self.soldiers if s.dead)
        if dead_count:
            avg_dead_temp = sum(s.temp_c for s in self.soldiers if s.dead) / dead_count
        temp_stat = self.hud.f_sm.render(
            f"Среднее T трупов: {avg_dead_temp:.1f}°C  |  Ambient: {self.dn.ambient_temp:.1f}°C",
            True, (100, 180, 255))

        cy0 = SCREEN_H//2 - 90
        self.screen.blit(tw,        (SCREEN_W//2-tw.get_width()//2, cy0))
        self.screen.blit(sw,        (SCREEN_W//2-sw.get_width()//2, cy0+58))
        self.screen.blit(hw,        (SCREEN_W//2-hw.get_width()//2, cy0+96))
        self.screen.blit(stat,      (SCREEN_W//2-stat.get_width()//2, cy0+126))
        self.screen.blit(temp_stat, (SCREEN_W//2-temp_stat.get_width()//2, cy0+150))

    # ── главный цикл ─────────────────────────────────────────────
    def run(self):
        while self.running:
            self.clock.tick(FPS)
            self.frame += 1

            self._events()
            if not self.over and not self.settings_menu.visible and not self.cheat_menu.visible:
                self._update()

            self._draw_world()

            total_w = sum(1 for s in self.soldiers if s.wounded)
            self.minimap.draw(self.screen, self.drone, self.soldiers,
                              self.extraction, self.cam_x, self.cam_y,
                              self.hud.f_sm, self.dn.night_alpha)
            self.hud.draw(self.screen, self.drone, self.dn,
                          self.extraction, total_w, self.analyzer,
                          self.frame, self.physics, self.soldiers,
                          self._show_temp)

            if self.over:
                self._draw_gameover()

            # Меню налаштувань і чіт-меню поверх усього
            self.settings_menu.draw(self.screen)
            self.cheat_menu.draw(self.screen)

            pygame.display.flip()

        pygame.quit()
        sys.exit()


# ═════════════════════════════════════════════════════════════
#  ТОЧКА ВХОДА
# ═════════════════════════════════════════════════════════════
if __name__ == '__main__':
    print("=" * 65)
    print("  MEDEVAC RESCUE DRONE v2 — WAR ZONE SIMULATION")
    print("=" * 65)
    print("  Требуется: pip install pygame numpy")
    print()
    print("  НОВОЕ В v2:")
    print("  • Настоящая физика температуры (Newton + Stefan-Boltzmann)")
    print("  • Ночь реально тёмная — 95%+ затемнение")
    print("  • Raycast: не видно сквозь стены")
    print("  • Тепловизор с физическими цветами (термограмма)")
    print("  • Прожектор [F]: освещает область вокруг дрона")
    print("  • Аварийная зарядка [E]")
    print("  • TAB: показать температурные данные")
    print("  • Горящие бочки — источники тепла")
    print("  • Трупы остывают по закону Ньютона")
    print("=" * 65)
    game = Game()
    game.run()
