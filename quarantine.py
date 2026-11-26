import math
import random
import sys
import wave
from bisect import bisect_right
from dataclasses import dataclass
from pathlib import Path

import arcade
from PIL import Image

from settings import Preferences, WINDOW_SIZES

SIZE = 3200
WIDTH, HEIGHT = WINDOW_SIZES[1]
ASSET_DIR = Path(__file__).resolve().parent / "assets"
COLORS = [(99,239,239), (255,213,92), (221,158,255)]
DASH_DURATION = .22
DASH_DISTANCE = 145
DASH_FADE = .10
ACID_COLOR = (175,255,92)
CALL_COLOR = (244,147,252)
SOUNDS = ("shot", "reload", "pickup", "hit", "wave", "spit", "call", "dash")
NUMBERS = (arcade.key.KEY_1, arcade.key.KEY_2, arcade.key.KEY_3)


def clamp(value, low, high):
    return max(low, min(high, value))


def distance(a, b):
    return math.hypot(a.x - b.x, a.y - b.y)


def fitted_window(index, screen_width, screen_height):
    width, height = WINDOW_SIZES[index]
    scale = min(1, screen_width/width, max(405,screen_height-80)/height)
    return max(640,int(width*scale)), max(405,int(height*scale))


def view_size(width, height):
    scale = min(max(1, width)/1080, max(1, height)/HEIGHT)
    return max(1, width)/scale, max(1, height)/scale


def circle_entry(x, y, dx, dy, target):
    zx, zy = x-target.x, y-target.y
    length_sq = dx*dx + dy*dy
    offset = zx*zx + zy*zy - target.radius*target.radius
    if offset <= 0:
        return 0
    if not length_sq:
        return math.inf
    projection = zx*dx + zy*dy
    discriminant = projection*projection - length_sq*offset
    if discriminant < 0:
        return math.inf
    entry = (-projection-math.sqrt(discriminant))/length_sq
    return entry if 0 <= entry <= 1 else math.inf


def box(x, y, w, h, color):
    arcade.draw_lbwh_rectangle_filled(x, y, w, h, color)


@dataclass(frozen=True)
class Difficulty:
    name: str
    description: str
    count: float
    health: float
    damage: float
    speed: float
    interval: float
    rest: float
    supplies: int


DIFFICULTIES = (
    Difficulty("Разведка", "Меньше зомби, длиннее передышка", .84, .90, .86, 1.0, 1.15, 6, 54),
    Difficulty("Выживание", "Плотные волны и ранняя броня", 1.31, 1.46, 1.38, 1.13, .70, 3.5, 42),
    Difficulty("Кошмар", "Быстрые враги и мало припасов", 1.65, 1.86, 1.75, 1.25, .54, 2.5, 32),
)


@dataclass(frozen=True)
class Weapon:
    name: str
    damage: int
    interval: float
    capacity: int
    spread: tuple = (0,)
    velocity: int = 880
    flight_time: float = .75
    reload_time: float = 1.15
    sprite: str = "carbine"
    muzzle: int = 32


WEAPONS = (
    Weapon("Карабин", 28, .24, 18),
    Weapon("Дробовик", 14, .65, 7, (-.19, -.095, 0, .095, .19), sprite="shotgun", muzzle=35),
    Weapon("Пистолет-пулемёт", 15, .115, 26, sprite="smg", muzzle=26),
    Weapon("Винтовка", 59, .53, 9, sprite="rifle", muzzle=38),
)
CACHE_WEAPONS = WEAPONS[1:] + (
    Weapon("Пистолет", 24, .20, 15, reload_time=.78, sprite="pistol", muzzle=22),
    Weapon("Двустволка", 21, .46, 2, (-.24,-.16,-.08,0,.08,.16,.24), 760, .34, 1.03, "double", 36),
    Weapon("Штурмовая винтовка", 26, .14, 30, velocity=1030, reload_time=1.52, sprite="assault", muzzle=34),
    Weapon("Автодробовик", 13, .31, 10, (-.22,-.13,-.05,.05,.13,.22), 800, .44, 1.62, "auto_shotgun", 34),
    Weapon("Ручной пулемёт", 21, .10, 60, velocity=960, reload_time=2.45, sprite="lmg", muzzle=38),
    Weapon("Марксманская винтовка", 87, .73, 6, velocity=1320, flight_time=.77, reload_time=1.36, sprite="marksman", muzzle=40),
)

UPGRADES = (
    ("Усиленные патроны", "+25% базового урона"),
    ("Лёгкое снаряжение", "+12% базовой скорости"),
    ("Быстрые руки", "Перезарядка на 20% быстрее"),
    ("Аптечка", "+35 здоровья"),
    ("Запас патронов", "+60 патронов"),
    ("Ускоренный спуск", "+20% базового темпа огня"),
    ("Бронежилет", "На 15% меньше получаемого урона"),
    ("Полевой медик", "+1 здоровье в секунду вне контакта"),
    ("Длинные магазины", "+4 патрона к ёмкости магазина"),
    ("Второе дыхание", "+20 к максимуму здоровья"),
    ("Быстрый рывок", "На 20% короче откат рывка"),
    ("Дальнобойные пули", "+30% к дальности выстрелов"),
)


@dataclass
class DashMotion:
    x: float
    y: float
    angle: float
    distance: float
    elapsed: float = 0

    def position(self, time):
        t = clamp(time/DASH_DURATION,0,1)
        progress = t*t*(3-2*t)
        step = self.distance*progress
        return self.x+math.cos(self.angle)*step, self.y+math.sin(self.angle)*step


@dataclass
class Fighter:
    x: float
    y: float
    name: str
    color: tuple
    weapon: Weapon
    magazine: int
    reserve: int = 100
    hp: float = 100
    max_hp: int = 100
    cooldown: float = 0
    reload: float = 0
    angle: float = 0
    radius: int = 13
    dash_ready: float = 0
    hurt: float = 0
    move_angle: float = 0
    walking: bool = False
    muzzle_flash: float = 0
    shot_angle: float = 0


@dataclass
class Zombie:
    x: float
    y: float
    hp: float
    speed: float
    radius: int
    color: tuple
    boss: bool = False
    flash: float = 0
    max_hp: float = 0
    kind: str = "walker"
    armor: float = 0
    windup: float = 0
    attack_ready: float = 0
    charge: float = 0
    heading: float = 0
    angle: float = 0
    stride: float = 0
    walking: bool = False
    called: bool = False


@dataclass
class Shot:
    x: float
    y: float
    vx: float
    vy: float
    damage: float
    life: float = .75
    muzzle_x: float = 0
    muzzle_y: float = 0
    trail: tuple[float, float] | None = None


@dataclass
class Casing:
    x: float
    y: float
    vx: float
    vy: float
    angle: float
    life: float = .8


@dataclass
class Loot:
    x: float
    y: float
    weapon: Weapon | None
    magazine: int
    reserve: int
    heal: int = 0


@dataclass
class Spark:
    x: float
    y: float
    vx: float
    vy: float
    color: tuple
    life: float


COVER_TYPES = {
    "Контейнер": ((155,195), (48,66), "container"),
    "Автобус": ((170,195), (60,78), "bus"),
    "Баррикада": ((105,180), (32,49), "barricade"),
    "Склад": ((145,195), (110,156), "warehouse"),
    "Ящики": ((60,110), (56,95), "crates"),
    "Киоск": ((72,110), (65,99), "kiosk"),
    "Клумба": ((80,150), (56,84), "planter"),
    "Блокпост": ((100,145), (85,116), "checkpoint"),
}
ZOMBIE_ART = ("walker", "runner", "armored", "charger", "boss", "spitter", "caller")
PALETTES = (
    ("Дневной парк", "", (134,151,166), (239,216,126), (160,184,176)),
    ("Янтарный квартал", "_ochre", (158,144,154), (255,209,140), (207,179,153)),
    ("Северный сектор", "_blue", (115,144,181), (183,228,237), (163,192,217)),
)
ASSET_NAMES = (
    "player_idle", "player_walk",
    *(f"{kind}_{frame}" for kind in ZOMBIE_ART for frame in range(3)),
    *(weapon.sprite for weapon in WEAPONS[:1] + CACHE_WEAPONS),
    *(sprite for _, _, sprite in COVER_TYPES.values()),
    "supply", "ammo", "bullet", "casing",
    *(base+suffix for _, suffix, *_ in PALETTES for base in ("ground", "asphalt", "concrete")),
)


def load_art():
    return {name: arcade.load_texture(ASSET_DIR / f"{name}.png") for name in ASSET_NAMES}



def load_player_models(art):
    models = {}
    for weapon in WEAPONS[:1] + CACHE_WEAPONS:
        length = weapon.muzzle + 7
        grip = weapon.muzzle - length*.43
        width, height = round(length*4/3), round(length/2)
        gun = art[weapon.sprite].image.resize((width, height), Image.Resampling.LANCZOS)
        for pose in ("player_idle", "player_walk"):
            image = Image.new("RGBA", (128,96))
            image.alpha_composite(art[pose].image, (32,16))
            image.alpha_composite(gun, (round(64+grip*4/3-width/2), 48-height//2))
            models[weapon.sprite, pose] = arcade.Texture(image)
    return models


DISTRICTS = (
    (.88, ("Склад", "Контейнер", "Ящики", "Баррикада")),
    (.76, ("Автобус", "Киоск", "Баррикада", "Контейнер")),
    (.82, ("Киоск", "Ящики", "Клумба", "Склад")),
    (.58, ("Клумба", "Киоск", "Ящики", "Баррикада")),
    (.70, ("Блокпост", "Баррикада", "Контейнер", "Ящики")),
)


@dataclass(frozen=True)
class Cover:
    x: float
    y: float
    w: float
    h: float
    kind: str

    def contains(self, x, y, margin=0):
        return (self.x - margin <= x <= self.x + self.w + margin
                and self.y - margin <= y <= self.y + self.h + margin)

    def segment(self, x, y, end_x, end_y, margin=0):
        if (max(x,end_x) < self.x-margin or min(x,end_x) > self.x+self.w+margin
                or max(y,end_y) < self.y-margin or min(y,end_y) > self.y+self.h+margin):
            return None
        entry, exit_at = 0, 1
        for start, end, low, high in (
            (x, end_x, self.x-margin, self.x+self.w+margin),
            (y, end_y, self.y-margin, self.y+self.h+margin),
        ):
            if end == start:
                continue
            near, far = sorted(((low-start)/(end-start), (high-start)/(end-start)))
            entry, exit_at = max(entry, near), min(exit_at, far)
            if entry > exit_at:
                return None
        return entry


class Arena:
    def __init__(self, generated=False, seed=None):
        self.generated = generated
        self.cover = []
        self.lanes_x = self.lanes_y = (710,1600,2490)
        self.road = 118
        self.plaza = 158
        rng = random.Random(seed if generated else 104)
        self.palette = rng.choice(PALETTES) if generated else PALETTES[0]
        if generated:
            self.generate(rng)

    def generate(self, rng):
        self.road = rng.choice((84,104,124,144,164))
        self.plaza = self.road + rng.choice((38,62,86,110))
        slots = (425,1000,1600,2200,2775)
        self.lanes_x, self.lanes_y = (
            tuple(base + rng.randint(-95,95)
                  for base in sorted(rng.sample(slots, rng.randint(2,4))))
            for _ in range(2)
        )
        districts = [[rng.choice(DISTRICTS) for _ in range(len(self.lanes_y)+1)]
                     for _ in range(len(self.lanes_x)+1)]
        # A 315-unit grid leaves at least 76 units between adjacent covers.
        for x in range(185, SIZE-185, 315):
            for y in range(185, SIZE-185, 315):
                cx, cy = x+rng.randint(-22,22), y+rng.randint(-22,22)
                density, kinds = districts[bisect_right(self.lanes_x,cx)][bisect_right(self.lanes_y,cy)]
                if rng.random() >= density:
                    continue
                kind = rng.choice(kinds)
                length, depth, _ = COVER_TYPES[kind]
                w, h = rng.randint(*length), rng.randint(*depth)
                if rng.choice((True,False)):
                    w,h = h,w
                item = Cover(cx-w/2, cy-h/2, w, h, kind)
                road_margin = self.road / 2 + 28
                if (item.contains(SIZE/2,SIZE/2,245)
                        or any(abs(cx-lane) <= w/2+road_margin for lane in self.lanes_x)
                        or any(abs(cy-lane) <= h/2+road_margin for lane in self.lanes_y)
                        or any(item.contains(lx,ly,self.plaza/2+24)
                               for lx in self.lanes_x for ly in self.lanes_y)):
                    continue
                self.cover.append(item)

    def blocked(self, x, y, margin):
        return any(c.contains(x,y,margin) for c in self.cover)

    def obstruction(self, x, y, ex, ey, margin=0):
        hits = ((t,c) for c in self.cover if (t := c.segment(x,y,ex,ey,margin)) is not None)
        return min(hits, key=lambda hit: hit[0], default=(math.inf,None))

    def route(self, unit, target_x, target_y):
        x,y,r = unit.x,unit.y,unit.radius
        span = math.hypot(target_x-x,target_y-y)
        lookahead = min(1,180/span) if span else 1
        _, cover = self.obstruction(x,y,x+(target_x-x)*lookahead,y+(target_y-y)*lookahead,r)
        if cover is None:
            return target_x,target_y
        pad = r+5
        corners = [(cx,cy) for cx in (cover.x-pad, cover.x+cover.w+pad)
                   for cy in (cover.y-pad, cover.y+cover.h+pad)]
        if cover.contains(target_x,target_y,r):
            target_x,target_y = min(corners, key=lambda p: math.hypot(p[0]-target_x,p[1]-target_y))
        routes = []
        for cx,cy in corners:
            first = math.hypot(cx-x,cy-y)
            if first < .5 or cover.segment(x,y,cx,cy,r) is not None:
                continue
            for ex,ey in corners:
                if cover.segment(cx,cy,ex,ey,r) is None and cover.segment(ex,ey,target_x,target_y,r) is None:
                    routes.append((first+math.hypot(cx-ex,cy-ey)+math.hypot(ex-target_x,ey-target_y),cx,cy))
        if routes:
            _,target_x,target_y = min(routes)
        return target_x,target_y

    def move(self, unit, dx, dy, step):
        span = math.hypot(dx,dy)
        if not span:
            return
        fraction = min(step/span,1)
        x = clamp(unit.x+dx*fraction,unit.radius,SIZE-unit.radius)
        y = clamp(unit.y+dy*fraction,unit.radius,SIZE-unit.radius)
        hit_x, _ = self.obstruction(unit.x, unit.y, x, unit.y, unit.radius)
        if hit_x < math.inf:
            delta = x - unit.x
            x = unit.x + math.copysign(max(0, abs(delta)*hit_x - .01), delta)
        unit.x = x
        hit_y, _ = self.obstruction(unit.x, unit.y, unit.x, y, unit.radius)
        if hit_y < math.inf:
            delta = y - unit.y
            y = unit.y + math.copysign(max(0, abs(delta)*hit_y - .01), delta)
        unit.y = y

    def walk(self, unit, dx, dy, step):
        x, y = unit.x, unit.y
        self.move(unit, dx, dy, step)
        moved = math.hypot(unit.x-x, unit.y-y)
        unit.walking = moved > .01
        unit.stride += moved
        return unit.walking


@dataclass(frozen=True)
class MenuButton:
    action: str
    title: str
    x: float
    y: float
    w: float
    h: float
    hint: str = ""
    accent: tuple | None = None

    def contains(self, point):
        px, py = point
        return self.x <= px <= self.x+self.w and self.y <= py <= self.y+self.h


class Game(arcade.Window):
    def __init__(self):
        self.switching_display = False
        directory = Path.home()
        self.settings_path = directory / ".arcade-zone04-settings.json"
        self.preferences = Preferences.load(self.settings_path, directory / ".arcade-zone04-display")
        width, height = fitted_window(self.preferences.window_size_index, *arcade.get_display_size())
        super().__init__(width, height, "Зона 04 / Карантин", resizable=True,
                         fullscreen=self.preferences.fullscreen)
        self.set_minimum_size(640, 405)
        self.view_width, self.view_height = view_size(*self.get_size())
        self.game_camera = arcade.Camera2D(
            position=(0, 0), projection=arcade.LRBT(0, self.view_width, 0, self.view_height), window=self
        )
        self.art = load_art()
        self.player_models = load_player_models(self.art)
        self.best_path = directory / ".arcade-zone04-best"
        self.sounds = {}
        self.settings_return = "title"
        try:
            self.best = int(self.best_path.read_text())
        except (OSError, ValueError):
            self.best = 0
        self.labels = {}
        self.difficulty = self.preferences.difficulty
        self.pointer_ratio = (.65, .5)
        self.cursor_hidden = False
        self.reset()
        self.state = "title"

    def reset(self, generated=False):
        self.arena = Arena(generated)
        weapon = WEAPONS[0]
        self.player = Fighter(SIZE/2, SIZE/2, "Сокол", COLORS[0], weapon, weapon.capacity)
        self.keys = set()

        self.firing = False
        self.zombies, self.shots, self.loot, self.sparks, self.casings, self.acid = [], [], [], [], [], []
        self.state = "play"
        self.match_time = 0
        self.wave = self.spawn_left = self.kills = self.xp = 0
        self.level = 1
        self.spawn_timer = 0
        self.break_time = self.rules.rest
        self.damage = self.speed = self.reload_speed = self.fire_rate = 1
        self.options = []
        self.notice = ""
        self.notice_until = 0
        self.regeneration = 0
        self.armor = 1
        self.magazine_bonus = 0
        self.dash_cooldown = 2.4
        self.dash_motion = None
        self.shot_range = 1.0
        self.armory = random.sample(CACHE_WEAPONS, len(CACHE_WEAPONS))

    @property
    def rules(self):
        return DIFFICULTIES[self.difficulty]

    @property
    def pointer(self):
        return self.pointer_ratio[0]*self.view_width, self.pointer_ratio[1]*self.view_height

    @property
    def origin(self):
        return (
            clamp(self.player.x-self.view_width/2, 0, max(0,SIZE-self.view_width)),
            clamp(self.player.y-self.view_height/2, -92, max(-92,SIZE-self.view_height+92)),
        )

    @property
    def xp_goal(self):
        return 5 + (self.level-1)*3

    def notify(self, message):
        self.notice, self.notice_until = message, self.match_time+2.5

    def capacity(self, fighter):
        return fighter.weapon.capacity + self.magazine_bonus

    def sound(self, name, gain=1):
        if not self.preferences.volume:
            return
        try:
            if name not in self.sounds:
                self.sounds[name] = arcade.load_sound(ASSET_DIR / f"{name}.wav")
            if self.sounds[name] is not None:
                arcade.play_sound(self.sounds[name], self.preferences.volume*gain/100)
        except (OSError, RuntimeError):
            self.sounds[name] = None

    def burst(self, x, y, color, count):
        if not self.preferences.effects:
            return
        for _ in range(count):
            angle = random.uniform(0, math.tau)
            speed = random.uniform(30, 150)
            self.sparks.append(Spark(x, y, math.cos(angle)*speed, math.sin(angle)*speed, color, .22))

    def aim_angle(self):
        x, y = self.origin
        return math.atan2(self.pointer[1]+y-self.player.y, self.pointer[0]+x-self.player.x)

    def dash(self):
        p = self.player
        if p.dash_ready > self.match_time:
            return
        dx,dy = self.movement()
        angle = math.atan2(dy,dx) if dx or dy else self.aim_angle()
        dx,dy = math.cos(angle),math.sin(angle)
        distance = DASH_DISTANCE
        for coordinate, direction in ((p.x,dx), (p.y,dy)):
            if abs(direction) > 1e-8:
                edge = SIZE-p.radius if direction > 0 else p.radius
                distance = min(distance,(edge-coordinate)/direction)
        hit, cover = self.arena.obstruction(p.x,p.y,p.x+dx*distance,p.y+dy*distance,p.radius)
        if cover is not None:
            distance = distance*hit-.04
        if distance <= 1:
            return
        self.dash_motion = DashMotion(p.x,p.y,angle,distance)
        p.dash_ready = self.match_time+self.dash_cooldown
        p.muzzle_flash = 0
        self.sound("dash")
        self.burst(p.x,p.y,p.color,8)

    def reload_weapon(self, fighter):
        if fighter.reload <= 0 and fighter.magazine < self.capacity(fighter) and fighter.reserve:
            fighter.reload = fighter.weapon.reload_time/self.reload_speed
            self.sound("reload")

    def fire(self, fighter):
        if fighter.cooldown > 0 or fighter.reload > 0:
            return
        if fighter.magazine == 0:
            self.reload_weapon(fighter)
            return
        fighter.magazine -= 1
        self.sound("shot", .82)
        weapon = fighter.weapon
        fighter.cooldown = weapon.interval / self.fire_rate
        fighter.muzzle_flash = .065
        fighter.shot_angle = fighter.angle
        dx, dy = math.cos(fighter.angle), math.sin(fighter.angle)
        muzzle_x, muzzle_y = weapon.muzzle*dx, weapon.muzzle*dy
        if self.preferences.effects:
            self.casings.append(Casing(fighter.x+14*dx, fighter.y+14*dy, 82*dy, -82*dx, fighter.angle))
        for spread in weapon.spread:
            angle = fighter.angle + spread
            self.shots.append(Shot(
                fighter.x, fighter.y, weapon.velocity*math.cos(angle), weapon.velocity*math.sin(angle),
                weapon.damage*self.damage, weapon.flight_time*self.shot_range, muzzle_x, muzzle_y,
            ))

    def nearby(self, weapon):
        p = self.player
        options = (item for item in self.loot
                   if (item.weapon if weapon else item.magazine+item.reserve+item.heal)
                   and distance(p,item) <= 65
                   and self.arena.obstruction(p.x,p.y,item.x,item.y)[1] is None)
        item = min(options,key=lambda drop: distance(self.player,drop),default=None)
        return item

    def collect(self, swap=False):
        item = self.nearby(swap)
        if item is None:
            return
        self.sound("pickup")
        f = self.player
        if swap:
            f.weapon,item.weapon = item.weapon,f.weapon
            f.magazine,item.magazine = item.magazine,f.magazine
            f.reserve += item.reserve
            item.reserve = 0
            f.reload = 0
            self.notify(f"В руках — {f.weapon.name}")
        else:
            amount = item.magazine+item.reserve
            f.reserve += amount
            item.magazine = item.reserve = 0
            if item.weapon is None:
                self.loot.remove(item)
            if item.heal:
                healed = min(item.heal, f.max_hp-f.hp)
                f.hp += healed
                self.notify(f"+{amount} патронов   ·   +{math.ceil(healed)} здоровья")
            else:
                self.notify(f"+{amount} патронов")

    def end_match(self):
        self.player.hp = 0
        self.state = "over"
        self.firing = False
        if self.kills > self.best:
            self.best = self.kills
            try:
                self.best_path.write_text(str(self.best))
            except OSError:
                pass

    def spawn(self, boss=False):
        p = self.player
        edge = 42 if boss else 28
        ox, oy = self.origin
        w, h = self.view_width, self.view_height
        # Spawn on all sides of the camera, including on wider monitors.
        for _ in range(42):
            angle = random.uniform(0, math.tau)
            radius = random.uniform(635, max(920, math.hypot(w,h)/2+175))
            x = clamp(p.x+math.cos(angle)*radius,edge,SIZE-edge)
            y = clamp(p.y+math.sin(angle)*radius,edge,SIZE-edge)
            in_view = ox-42 < x < ox+w+42 and oy-42 < y < oy+h+42
            if not in_view and math.hypot(x-p.x,y-p.y) > 580 and not self.arena.blocked(x,y,42):
                break
        else:
            corners = [(x,y) for x in (edge,SIZE-edge) for y in (edge,SIZE-edge)]
            x,y = max(corners, key=lambda q: math.hypot(q[0]-p.x,q[1]-p.y))
        roll = random.random()
        hp = (36+4*self.wave)*self.rules.health
        if boss:
            zombie = Zombie(x,y,hp*7,83,34,(229,126,82),boss=True,kind="boss")
        elif self.wave >= 6 and roll < .13:
            zombie = Zombie(x,y,hp*1.12,90,17,CALL_COLOR,kind="caller")
        elif self.wave >= 4 and roll < (.26 if self.wave >= 6 else .13):
            zombie = Zombie(x,y,hp*.93,96,16,ACID_COLOR,kind="spitter")
        elif self.wave >= (6 if self.difficulty == 0 else 4) and roll < (.38 if self.wave >= 6 else .25):
            zombie = Zombie(x,y,hp*1.25,110,17,(219,140,93),kind="charger")
        elif self.wave >= (3 if self.difficulty == 0 else 2) and roll < (.51 if self.wave >= 4 else .38):
            zombie = Zombie(x,y,hp*1.65,70,22,(125,150,169),kind="armored",armor=hp*.8)
        elif self.wave >= (1 if self.difficulty == 2 else 2) and roll < (.74 if self.wave >= 4 else .62):
            zombie = Zombie(x,y,hp*.68,156,13,(202,111,100),kind="runner")
        else:
            zombie = Zombie(x,y,hp,random.uniform(75,112),16,(143,172,104))
        zombie.speed *= self.rules.speed
        zombie.max_hp = zombie.hp
        self.zombies.append(zombie)

    def update_wave(self, dt):
        if self.spawn_left:
            self.spawn_timer -= dt
            if self.spawn_timer <= 0:
                self.spawn(boss=self.wave % 5 == 0 and self.spawn_left == 1)
                self.spawn_left -= 1
                self.spawn_timer = max(.23,.85-.045*self.wave)*self.rules.interval
        elif not self.zombies:
            self.break_time -= dt
            if self.break_time <= 0:
                self.wave += 1
                self.sound("wave", .7)
                if self.wave > 1:
                    self.drop_supplies()
                if self.wave % 2 == 0:
                    self.drop_supplies(weapon=self.armory.pop())
                    if not self.armory:
                        self.armory = random.sample(CACHE_WEAPONS, len(CACHE_WEAPONS))
                self.spawn_left = min(96, round((8+self.wave*5)*self.rules.count))
                self.spawn_timer = 0
                self.break_time = self.rules.rest
                if self.wave % 5 == 0:
                    self.notify("В этой волне появится громила-босс")

    def drop_supplies(self, weapon=None):
        p = self.player
        for angle in random.sample(range(0, 360, 30), 12):
            radians = math.radians(angle)
            x = clamp(p.x + 140*math.cos(radians),24,SIZE-24)
            y = clamp(p.y + 140*math.sin(radians),24,SIZE-24)
            if (math.hypot(x-p.x,y-p.y) > 65
                    and all(math.hypot(x-item.x,y-item.y) > 42 for item in self.loot)
                    and self.arena.obstruction(p.x,p.y,x,y,13)[1] is None):
                break
        else:
            x,y = p.x,p.y
        if weapon:
            self.loot.append(Loot(x,y,weapon,weapon.capacity,24))
        else:
            self.loot.append(Loot(x,y,None,0,self.rules.supplies,16 if self.difficulty != 2 else 10))

    def movement(self):
        k = arcade.key
        dx = bool(self.keys & {k.D,k.RIGHT}) - bool(self.keys & {k.A,k.LEFT})
        dy = bool(self.keys & {k.W,k.UP}) - bool(self.keys & {k.S,k.DOWN})
        return dx,dy

    def update_player(self, dt):
        p = self.player
        motion = self.dash_motion
        dashing = motion is not None and motion.elapsed < DASH_DURATION
        if motion:
            motion.elapsed += dt
            if motion.elapsed >= DASH_DURATION+DASH_FADE:
                self.dash_motion = None
        if dashing:
            p.x,p.y = motion.position(motion.elapsed)
            p.walking = False
        else:
            dx,dy = self.movement()
            old_x,old_y = p.x,p.y
            self.arena.move(p,dx*100,dy*100,250*self.speed*dt)
            dx,dy = p.x-old_x,p.y-old_y
            p.walking = math.hypot(dx,dy) > .01
            if p.walking:
                p.move_angle = math.atan2(dy,dx)
        p.angle = self.aim_angle()
        p.cooldown = max(0, p.cooldown-dt)
        p.muzzle_flash = max(0, p.muzzle_flash-dt)
        p.hurt = max(0, p.hurt-dt)
        if not p.hurt:
            p.hp = min(p.max_hp, p.hp+self.regeneration*dt)
        if p.reload > 0:
            p.reload -= dt
            if p.reload <= 0:
                amount = min(self.capacity(p)-p.magazine, p.reserve)
                p.magazine += amount
                p.reserve -= amount
        if self.firing and not dashing:
            self.fire(p)

    def update_shots(self, dt):
        remaining = []
        for shot in self.shots:
            if shot.life <= 0:
                continue
            travel_time = min(dt, shot.life)
            dx,dy = shot.vx*travel_time,shot.vy*travel_time
            if shot.muzzle_x or shot.muzzle_y:
                # Sweep the short barrel segment separately to avoid firing through cover.
                mx, my = shot.x+shot.muzzle_x, shot.y+shot.muzzle_y
                if self.projectile_hit(shot, mx, my):
                    continue
                shot.x, shot.y = mx, my
                shot.muzzle_x = shot.muzzle_y = 0
            length_sq = dx*dx+dy*dy
            if not length_sq:
                remaining.append(shot)
                continue
            ex,ey = shot.x+dx,shot.y+dy
            if not self.projectile_hit(shot, ex, ey):
                shot.trail = (shot.x, shot.y)
                shot.x, shot.y = ex, ey
                shot.life -= travel_time
                if shot.life > 0 and 0 < ex < SIZE and 0 < ey < SIZE:
                    remaining.append(shot)
        self.shots = remaining

    def projectile_hit(self, shot, ex, ey):
        dx, dy = ex-shot.x, ey-shot.y
        wall_at, cover = self.arena.obstruction(shot.x, shot.y, ex, ey)
        hit, hit_at = None, wall_at
        for z in self.zombies:
            entry = circle_entry(shot.x, shot.y, dx, dy, z)
            if entry < hit_at:
                hit, hit_at = z, entry
        if hit is None and cover is None:
            return False
        x, y = shot.x+dx*hit_at, shot.y+dy*hit_at
        if hit is None:
            self.burst(x, y, (218, 188, 143), 5)
            return True
        absorbed = min(hit.armor, shot.damage*.65)
        hit.armor -= absorbed
        hit.hp -= shot.damage-absorbed
        hit.flash = .09
        self.burst(x, y, (221,210,165) if absorbed else hit.color, 5)
        if hit.hp <= 0:
            self.zombies.remove(hit)
            self.kills += 1
            self.xp += 5 if hit.boss else 1
            if hit.boss:
                self.loot.append(Loot(hit.x,hit.y,None,0,80,35))
            elif self.kills % 3 == 0:
                self.loot.append(Loot(hit.x,hit.y,None,0,16))
        return True

    def hurt_player(self, amount):
        self.sound("hit", .86)
        self.player.hp -= amount * self.rules.damage * self.armor
        self.player.hurt = 1.5
        if self.player.hp <= 0:
            self.end_match()

    def update_acid(self, dt):
        p = self.player
        remaining = []
        for droplet in self.acid:
            travel = min(dt, droplet.life)
            dx, dy = droplet.vx*travel, droplet.vy*travel
            x, y = droplet.x, droplet.y
            ex, ey = x+dx, y+dy
            wall_at, _ = self.arena.obstruction(x,y,ex,ey)
            hit_at = circle_entry(x,y,dx,dy,p)
            if hit_at < wall_at:
                self.burst(x+dx*hit_at,y+dy*hit_at,ACID_COLOR,8)
                self.hurt_player(droplet.damage)
                if self.state == "over":
                    remaining.clear()
                    break
            elif wall_at < math.inf:
                self.burst(x+dx*wall_at,y+dy*wall_at,ACID_COLOR,6)
            else:
                droplet.x, droplet.y = ex,ey
                droplet.life -= travel
                if droplet.life > 0 and 0 < ex < SIZE and 0 < ey < SIZE:
                    remaining.append(droplet)
        self.acid = remaining

    def call_runners(self, zombie, reinforcements):
        self.sound("call", .7)
        self.burst(zombie.x,zombie.y,CALL_COLOR,21)
        zombie.called = True
        for direction in (zombie.heading+1.7, zombie.heading-1.7):
            for turn in (0,.6,-.6,1.2,-1.2):
                x = zombie.x+math.cos(direction+turn)*52
                y = zombie.y+math.sin(direction+turn)*52
                if (15 < x < SIZE-15 and 15 < y < SIZE-15
                        and math.hypot(x-self.player.x,y-self.player.y) > self.player.radius+15
                        and not self.arena.blocked(x,y,15)):
                    hp = (36+4*self.wave)*self.rules.health*.42
                    reinforcements.append(Zombie(x,y,hp,152*self.rules.speed,13,(221,128,154),kind="runner"))
                    break

    def update_zombies(self, dt):
        target = self.player
        reinforcements = []
        for z in self.zombies:
            z.walking = False
            z.flash = max(0,z.flash-dt)
            gap = distance(z,target)
            clear = self.arena.obstruction(z.x,z.y,target.x,target.y)[1] is None
            reach = z.radius + 26
            charger = z.kind in ("charger","boss")
            caller = z.kind == "caller" and not z.called and len(self.zombies)+len(reinforcements) < 90
            spitter = z.kind == "spitter"
            if z.charge > 0:
                z.charge = max(0,z.charge-dt)
                dx,dy = math.cos(z.heading),math.sin(z.heading)
                step = 390*dt
                wall = self.arena.obstruction(z.x,z.y,z.x+dx*step,z.y+dy*step,z.radius)[1]
                if wall is not None:
                    z.charge = 0
                else:
                    self.arena.walk(z,dx*100,dy*100,step)
                    if (distance(z,target) <= reach
                            and self.arena.obstruction(z.x,z.y,target.x,target.y)[1] is None):
                        z.charge = 0
                        self.hurt_player(34 if z.boss else 21)
                        if self.state == "over":
                            return
                continue
            if z.windup > 0:
                z.windup = max(0,z.windup-dt)
                if not z.windup:
                    z.attack_ready = self.match_time + (2.5 if charger or spitter else .7)
                    if charger:
                        z.charge = .44
                    elif spitter:
                        speed = 425
                        self.acid.append(Shot(z.x,z.y,speed*math.cos(z.heading),speed*math.sin(z.heading),18,1.02))
                        self.sound("spit", .65)
                    elif caller:
                        self.call_runners(z, reinforcements)
                    elif gap <= reach and clear:
                        self.hurt_player(15 if z.kind == "armored" else 10)
                        if self.state == "over":
                            return
                continue
            if spitter or caller:
                attack_range = 320
                telegraph = .56 if spitter else .84
            else:
                attack_range = 145 if charger else reach
                telegraph = .55 if charger else .22
            if gap <= attack_range and clear and self.match_time >= z.attack_ready:
                z.windup = telegraph
                z.heading = z.angle = math.atan2(target.y-z.y,target.x-z.x)
                continue
            if spitter and clear and 100 < gap <= attack_range:
                continue
            if gap <= reach-8 and clear:
                continue
            x,y = self.arena.route(z,target.x,target.y)
            dx,dy = x-z.x,y-z.y
            if (x,y) == (target.x,target.y):
                for other in self.zombies:
                    rx, ry = z.x-other.x, z.y-other.y
                    if 0 < rx*rx+ry*ry < (z.radius+other.radius)**2:
                        dx += rx*1.3
                        dy += ry*1.3
            if self.arena.walk(z,dx,dy,z.speed*dt):
                z.angle = math.atan2(dy,dx)
        self.zombies.extend(reinforcements)

    def check_upgrade(self):
        if self.xp >= self.xp_goal:
            self.xp -= self.xp_goal
            self.level += 1
            self.options = random.sample(range(len(UPGRADES)),3)
            self.state = "upgrade"
            self.firing = False

    def choose(self, index):
        choice = self.options[index]
        if choice == 0:
            self.damage += .25
        elif choice == 1:
            self.speed += .12
        elif choice == 2:
            self.reload_speed /= .8
        elif choice == 3:
            self.player.hp = min(self.player.max_hp, self.player.hp+35)
        elif choice == 4:
            self.player.reserve += 60
        elif choice == 5:
            self.fire_rate += .2
        elif choice == 6:
            self.armor *= .85
        elif choice == 7:
            self.regeneration += 1
        elif choice == 8:
            self.magazine_bonus += 4
        elif choice == 9:
            self.player.max_hp += 20
            self.player.hp += 20
        elif choice == 10:
            self.dash_cooldown *= .8
        else:
            self.shot_range += .30
        self.state = "play"
        self.check_upgrade()

    def on_update(self, delta_time):
        if self.state != "play" or delta_time <= 0:
            return
        dt = min(delta_time,.05)
        self.match_time += dt
        for spark in self.sparks:
            spark.x += spark.vx*dt
            spark.y += spark.vy*dt
            spark.life -= dt
        self.sparks = [spark for spark in self.sparks if spark.life > 0]
        for casing in self.casings:
            casing.x += casing.vx*dt
            casing.y += casing.vy*dt
            casing.angle += 9*dt
            casing.vx *= max(0, 1-7*dt)
            casing.vy *= max(0, 1-7*dt)
            casing.life -= dt
        self.casings = [casing for casing in self.casings if casing.life > 0]
        self.update_wave(dt)
        self.update_player(dt)
        self.update_shots(dt)
        self.update_zombies(dt)
        if self.state == "play":
            self.update_acid(dt)
        if self.state == "play":
            self.check_upgrade()

    def on_resize(self, width, height):
        self.view_width, self.view_height = view_size(width, height)

    def apply_window_size(self):
        size = fitted_window(self.preferences.window_size_index, self.screen.width, self.screen.height)
        self.set_size(*size)
        self.center_window()
        self.on_resize(*self.get_size())

    def toggle_display(self):
        self.firing = False
        self.switching_display = True
        try:
            self.set_fullscreen(not self.fullscreen)
            if not self.fullscreen:
                self.apply_window_size()
            self.on_resize(*self.get_size())
        finally:
            self.switching_display = False
        self.preferences.fullscreen = self.fullscreen
        self.preferences.save(self.settings_path)

    def menu_buttons(self):
        x, y = self.view_width/2, self.view_height/2
        if self.state == "title":
            left = x-440
            return [
                *(MenuButton(f"difficulty:{i}", rules.name, left+i*160, y+6, 151, 42,
                             accent=COLORS[1] if self.difficulty == i else None)
                  for i, rules in enumerate(DIFFICULTIES)),
                MenuButton("classic", "Классическая карта", left, y-115, 231, 66, "1  /  Открытая арена", COLORS[1]),
                MenuButton("generated", "Случайная карта", left+244, y-115, 231, 66, "2  /  Кварталы и укрытия", COLORS[0]),
                MenuButton("settings", "Настройки", left, y-184, 231, 43),
                MenuButton("quit", "Выйти", left+244, y-184, 231, 43),
            ]
        if self.state in ("pause", "over"):
            pause = self.state == "pause"
            return [
                MenuButton("resume" if pause else "restart", "Продолжить" if pause else "Сыграть снова",
                           x-206, y-15, 412, 58, "Esc" if pause else "Enter", COLORS[1]),
                MenuButton("settings", "Настройки", x-206, y-79, 412, 50),
                MenuButton("title", "Главное меню", x-206, y-137, 412, 46, "M"),
            ]
        if self.state == "settings":
            size = self.preferences.window_size_index
            return [
                MenuButton("windowed", "В окне", x-20, y+106, 152, 42,
                           accent=None if self.fullscreen else COLORS[0]),
                MenuButton("fullscreen", "Полный экран", x+145, y+106, 152, 42,
                           accent=COLORS[0] if self.fullscreen else None),
                *(MenuButton(f"size:{i}", f"{width} × {height}", x-20+i*108, y+50, 101, 42,
                             accent=COLORS[0] if size == i else None)
                  for i,(width,height) in enumerate(WINDOW_SIZES)),
                MenuButton("volume:-10", "−", x-20, y-7, 51, 42),
                MenuButton("volume:10", "+", x+246, y-7, 51, 42),
                MenuButton("minimap", "Показана" if self.preferences.minimap else "Скрыта", x-20, y-63,
                           317, 42, accent=COLORS[0] if self.preferences.minimap else None),
                MenuButton("effects", "Полные" if self.preferences.effects else "Сдержанные", x-20, y-119,
                           317, 42, accent=COLORS[0] if self.preferences.effects else None),
                MenuButton("back", "Назад", x-296, y-193, 593, 48, "Esc", COLORS[1]),
            ]
        if self.state == "upgrade":
            return [
                MenuButton(f"upgrade:{i}", UPGRADES[choice][0], x-462+i*312, y-56, 300, 112,
                           UPGRADES[choice][1], COLORS[i])
                for i, choice in enumerate(self.options)
            ]
        return []

    def activate_menu(self, action):
        name, _, value = action.partition(":")
        if name == "difficulty":
            self.difficulty = int(value)
            self.preferences.difficulty = self.difficulty
            self.preferences.save(self.settings_path)
        elif name == "upgrade":
            self.choose(int(value))
        elif name == "settings":
            self.settings_return = self.state
            self.state = "settings"
        elif name == "back":
            self.state = self.settings_return
        elif name in ("windowed", "fullscreen"):
            if self.fullscreen != (name == "fullscreen"):
                self.toggle_display()
        elif name == "size":
            self.preferences.window_size_index = int(value)
            if not self.fullscreen:
                self.apply_window_size()
            self.preferences.save(self.settings_path)
        elif name == "volume":
            self.preferences.volume = clamp(self.preferences.volume+int(value),0,100)
            self.preferences.save(self.settings_path)
            self.sound("pickup", .7)
        elif name in ("minimap", "effects"):
            enabled = not getattr(self.preferences,name)
            setattr(self.preferences,name,enabled)
            self.preferences.save(self.settings_path)
            if name == "effects" and not enabled:
                self.sparks.clear()
                self.casings.clear()
        elif name == "resume":
            self.state = "play"
        elif name == "title":
            self.state = "title"
        elif name == "quit":
            self.close()
        elif name == "restart":
            self.reset(self.arena.generated)
        elif name in ("classic", "generated"):
            self.reset(name == "generated")

    def on_key_press(self, key, modifiers):
        k = arcade.key
        repeated = key in self.keys
        self.keys.add(key)
        if repeated:
            return
        if key == k.F11 or (key == k.ENTER and modifiers & k.MOD_ALT):
            self.toggle_display()
            return
        if self.state == "settings":
            if key == k.ESCAPE:
                self.activate_menu("back")
            return
        if self.state in ("title","over"):
            if key in NUMBERS[:2]:
                self.reset(key == NUMBERS[1])
                self.keys.add(key)
            elif key == k.ENTER:
                self.reset(self.arena.generated)
                self.keys.add(key)
            elif key == k.F2:
                self.activate_menu(f"difficulty:{(self.difficulty+1) % len(DIFFICULTIES)}")
            elif key == k.M and self.state == "over":
                self.state = "title"
        elif self.state == "upgrade":
            if key in NUMBERS[:3]:
                self.choose(NUMBERS.index(key))
        elif key == k.ESCAPE:
            self.state = "pause" if self.state == "play" else "play"
            self.firing = False
        elif self.state == "pause" and key == k.M:
            self.state = "title"
        elif self.state == "play":
            if key == k.SPACE:
                self.dash()
            elif key == k.R:
                self.reload_weapon(self.player)
            elif key == k.E:
                self.collect()
            elif key == k.F:
                self.collect(swap=True)

    def on_key_release(self, key, modifiers):
        self.keys.discard(key)

    def update_pointer(self, x, y):
        w, h = self.get_size()
        self.pointer_ratio = clamp(x/max(1,w),0,1), clamp(y/max(1,h),0,1)

    def on_mouse_motion(self, x, y, dx, dy):
        self.update_pointer(x, y)

    def on_mouse_drag(self, x, y, dx, dy, buttons, modifiers):
        self.update_pointer(x, y)

    def on_mouse_press(self, x, y, button, modifiers):
        self.update_pointer(x, y)
        if button != arcade.MOUSE_BUTTON_LEFT:
            return
        if self.state == "play":
            self.firing = True
            return
        for item in self.menu_buttons():
            if item.contains(self.pointer):
                self.activate_menu(item.action)
                break

    def on_mouse_release(self, x, y, button, modifiers):
        if button == arcade.MOUSE_BUTTON_LEFT:
            self.firing = False

    def on_deactivate(self):
        if self.switching_display:
            return
        self.keys.clear()
        self.firing = False
        if self.state == "play":
            self.state = "pause"

    def label(self, key, content, x, y, size=13, color=(232,240,235), center=False, bold=False):
        if key not in self.labels:
            self.labels[key] = arcade.Text(content,x,y,color,size,font_name="DejaVu Sans",
                                          anchor_x="center" if center else "left",bold=bold)
        label = self.labels[key]
        label.text = content
        label.x,label.y,label.color = x,y,color
        label.draw()

    def texture(self, name, x, y, w, h, angle=0, alpha=255):
        arcade.draw_texture_rect(
            self.art[name], arcade.XYWH(x, y, w, h), angle=math.degrees(angle), alpha=alpha
        )

    def draw_arena(self, ox, oy):
        arena = self.arena
        _, suffix, curb, stripe, stone_edge = arena.palette
        box(0, 0, self.view_width, self.view_height, (76,110,95))
        tile = 192
        for x in range(int(ox)//tile*tile, int(ox+self.view_width)+1, tile):
            for y in range(int(oy)//tile*tile, int(oy+self.view_height)+1, tile):
                self.texture("ground"+suffix, x+tile/2-ox, y+tile/2-oy, tile, tile)
        for lane in arena.lanes_x:
            x = lane-ox
            if not -arena.road < x < self.view_width+arena.road:
                continue
            box(x-arena.road/2-4, -oy, arena.road+8, SIZE, curb)
            for y in range(max(0,int(oy)//tile*tile), min(SIZE,int(oy+self.view_height)+1), tile):
                height = min(tile,SIZE-y)
                self.texture("asphalt"+suffix, x, y+height/2-oy, arena.road, height)
            for y in range(max(0,int(oy)//84*84), min(SIZE-30,int(oy+self.view_height)+1), 84):
                box(x-1,y-oy,2,30,stripe)
        for lane in arena.lanes_y:
            y = lane-oy
            if not -arena.road < y < self.view_height+arena.road:
                continue
            box(-ox, y-arena.road/2-4, SIZE, arena.road+8, curb)
            for x in range(max(0,int(ox)//tile*tile), min(SIZE,int(ox+self.view_width)+1), tile):
                width = min(tile,SIZE-x)
                self.texture("asphalt"+suffix, x+width/2-ox, y, width, arena.road)
            for x in range(max(0,int(ox)//84*84), min(SIZE-30,int(ox+self.view_width)+1), 84):
                box(x-ox,y-1,30,2,stripe)
        for lane_x in arena.lanes_x:
            for lane_y in arena.lanes_y:
                x, y = lane_x-ox, lane_y-oy
                size = arena.plaza if arena.generated else arena.road
                if -size < x < self.view_width+size and -size < y < self.view_height+size:
                    self.texture("concrete"+suffix, x, y, size, size)
                    arcade.draw_lbwh_rectangle_outline(x-size/2+5,y-size/2+5,size-10,size-10,stone_edge,1)
        arcade.draw_lbwh_rectangle_outline(5-ox,5-oy,SIZE-10,SIZE-10,(255,207,98),8)
        for c in arena.cover:
            x, y = c.x-ox, c.y-oy
            if x < self.view_width and y < self.view_height and x+c.w > 0 and y+c.h > 0:
                item = COVER_TYPES[c.kind][2]
                box(x+7,y-7,c.w,c.h,(11,22,20,165))
                if c.w >= c.h:
                    self.texture(item, x+c.w/2, y+c.h/2, c.w, c.h)
                else:
                    self.texture(item, x+c.w/2, y+c.h/2, c.h, c.w, math.pi/2)

    def draw_dash_trail(self, ox, oy):
        motion = self.dash_motion
        if motion is None or not self.preferences.effects:
            return
        model = self.player_models[self.player.weapon.sprite,"player_walk"]
        fade = 1-clamp((motion.elapsed-DASH_DURATION)/DASH_FADE,0,1)
        for delay, opacity in ((.085,45),(.058,70),(.030,105)):
            time = motion.elapsed-delay
            if 0 <= time < DASH_DURATION:
                x,y = motion.position(time)
                arcade.draw_texture_rect(model,arcade.XYWH(x-ox,y-oy,111,58),
                                         alpha=round(opacity*fade),angle=math.degrees(motion.angle))

    def draw_units(self, ox, oy):
        for item in self.loot:
            x, y = item.x-ox, item.y-oy
            if not (-45 < x < self.view_width+45 and -45 < y < self.view_height+45):
                continue
            if item.weapon:
                arcade.draw_circle_outline(x,y,18,COLORS[1],1)
                self.texture(item.weapon.sprite, x, y, 32, 12, .2)
            else:
                self.texture("supply" if item.heal else "ammo", x, y, 28, 24)
        for casing in self.casings:
            self.texture(
                "casing", casing.x-ox, casing.y-oy, 8, 4, casing.angle, min(255,int(475*casing.life))
            )
        for z in self.zombies:
            x, y = z.x-ox, z.y-oy
            if not (-150 < x < self.view_width+150 and -150 < y < self.view_height+150):
                continue
            size = z.radius*3.35
            frame = 1+int(z.stride/11)%2 if z.walking else 0
            arcade.draw_ellipse_filled(x+3,y-5,z.radius*2.1,z.radius*1.6,(11,19,18,180))
            self.texture(f"{z.kind}_{frame}", x, y, size, size, z.angle)
            if z.flash:
                arcade.draw_circle_outline(x,y,z.radius+2,(255,224,182),2)
            if z.armor > 0:
                arcade.draw_circle_outline(x,y,z.radius+2,(128,185,208),1)
            if z.windup:
                alert = ACID_COLOR if z.kind == "spitter" else CALL_COLOR if z.kind == "caller" and not z.called else (255,209,109)
                arcade.draw_circle_outline(x,y,z.radius+7,alert,2)
                if z.kind in ("charger","boss","spitter"):
                    arcade.draw_line(x,y,x+math.cos(z.heading)*118,y+math.sin(z.heading)*118,alert,2)
            if z.boss:
                box(x-36,y+44,72,5,(74,49,45))
                box(x-36,y+44,72*z.hp/z.max_hp,5,z.color)
        f = self.player
        if f.hp > 0:
            self.draw_dash_trail(ox,oy)
            x,y = f.x-ox,f.y-oy
            motion = self.dash_motion
            dashing = motion is not None and motion.elapsed < DASH_DURATION
            pose = "player_walk" if f.walking or dashing else "player_idle"
            angle = f.move_angle if f.walking and not self.firing else f.angle
            if f.muzzle_flash:
                angle = f.shot_angle
            arcade.draw_ellipse_filled(x+3,y-4,29,22,(11,19,18,180))
            model = self.player_models[f.weapon.sprite, pose]
            stretch = 0
            if dashing:
                angle = motion.angle
                stretch = math.sin(math.pi*motion.elapsed/DASH_DURATION)
            arcade.draw_texture_rect(model, arcade.XYWH(x,y,96+17*stretch,72-13*stretch),
                                     angle=math.degrees(angle))
            dx, dy = math.cos(angle), math.sin(angle)
            if f.muzzle_flash:
                mx, my = f.x+dx*f.weapon.muzzle, f.y+dy*f.weapon.muzzle
                wall_at, cover = self.arena.obstruction(f.x, f.y, mx, my)
                if cover is not None:
                    mx = f.x+(mx-f.x)*wall_at
                    my = f.y+(my-f.y)*wall_at
                arcade.draw_circle_filled(mx-ox,my-oy,5,(255,177,70,135))
                arcade.draw_circle_filled(mx-ox,my-oy,2.5,(255,243,190))
            box(x-14,y+27,28,3,(69,74,68))
            box(x-14,y+27,28*f.hp/f.max_hp,3,f.color)
        for droplet in self.acid:
            x, y = droplet.x-ox, droplet.y-oy
            arcade.draw_circle_filled(x,y,9,(79,108,52,190))
            arcade.draw_circle_filled(x,y,6,ACID_COLOR)
            arcade.draw_circle_filled(x+1,y+2,2,(248,255,190))
        for spark in self.sparks:
            arcade.draw_circle_filled(spark.x-ox,spark.y-oy,1+spark.life*9,spark.color)
        for shot in self.shots:
            x, y = shot.x-ox, shot.y-oy
            if self.preferences.effects and shot.trail:
                start_x, start_y = shot.trail
                arcade.draw_line(start_x-ox,start_y-oy,x,y,(255,189,79,135),1)
            self.texture("bullet", x, y, 12, 4.3, math.atan2(shot.vy,shot.vx))

    def panel(self, x, y, w, h, color=(25,38,58,246), edge=(98,136,170)):
        box(x, y, w, h, color)
        arcade.draw_lbwh_rectangle_outline(x+.5, y+.5, w-1, h-1, edge, 1)

    def meter(self, x, y, w, h, value, color):
        box(x, y, w, h, (49,62,64))
        if value > 0:
            box(x, y, w*clamp(value,0,1), h, color)

    def draw_hud(self, ox, oy):
        w,h = self.view_width,self.view_height
        center = w/2
        p = self.player
        teal, gold, muted = COLORS[0], COLORS[1], (179,203,226)
        self.panel(22,h-80,267,58)
        self.label("brand","ЗОНА 04",39,h-45,19,teal,bold=True)
        self.label("mode",f"{self.arena.palette[0]}  /  {self.rules.name}",39,h-65,10,muted)

        self.panel(center-145,h-98,290,76)
        threats = len(self.zombies)+self.spawn_left
        title = f"ВОЛНА {self.wave:02}" if threats else f"ВОЛНА {self.wave+1:02}  ·  {math.ceil(self.break_time)} с"
        self.label("wave",title,center,h-56,21,gold,True,True)
        detail = f"{threats} осталось   ·   {self.kills} устранено" if threats else f"Устранено {self.kills}"
        self.label("threats",detail,center,h-80,11,muted,True)
        if self.match_time < self.notice_until:
            self.label("notice",self.notice,center,h-125,13,gold,True,True)

        self.panel(22,22,270,80)
        self.texture("player_idle",58,62,63,63)
        hp_color = (252,127,114) if p.hp < 33 else teal
        self.label("hp_title","ЗДОРОВЬЕ",93,74,10,muted)
        self.label("hp",f"{math.ceil(p.hp):02} / {p.max_hp}",93,49,17,hp_color,bold=True)
        self.meter(93,35,176,5,p.hp/p.max_hp,hp_color)

        self.panel(center-144,22,288,80)
        self.label("level",f"УРОВЕНЬ {self.level}     {self.xp} / {self.xp_goal} ОПЫТА",
                   center,77,11,teal,True,True)
        self.meter(center-119,62,238,4,self.xp/self.xp_goal,teal)
        dash_left = max(0,p.dash_ready-self.match_time)
        hint = f"ПРОБЕЛ   Рывок через {dash_left:.1f} с" if dash_left else "ПРОБЕЛ   Рывок готов"
        self.label("dash",hint,center,39,11,muted if dash_left else gold,True)

        right = w-313
        self.panel(right,22,291,80)
        self.texture(p.weapon.sprite,right+47,62,69,26)
        self.label("gun",p.weapon.name,right+91,78,11,muted)
        self.label("reload","R",right+258,34,11,muted)
        if p.reload > 0:
            self.label("reloading","Перезарядка",right+91,47,15,gold,bold=True)
            remaining = p.reload*self.reload_speed/p.weapon.reload_time
            self.meter(right+91,34,158,3,1-remaining,gold)
        else:
            ammo = f"{p.magazine:02}  /  {p.reserve:03}"
            self.label("ammo",ammo,right+91,44,21,gold if p.magazine == 0 else teal,bold=True)

        ammo_drop,weapon_drop = self.nearby(False),self.nearby(True)
        actions = []
        if ammo_drop:
            actions.append("E   Припасы" if ammo_drop.heal else "E   Патроны")
        if weapon_drop:
            actions.append(f"F   {weapon_drop.weapon.name}")
        if actions and p.hp > 0:
            self.panel(center-244,109,488,35,(17,25,28,236))
            self.label("loot","     /     ".join(actions),center,120,12,gold,True,True)

        if not self.preferences.minimap:
            self.panel(w-173,h-58,151,36)
            minutes, seconds = divmod(int(self.match_time),60)
            self.label("score",f"{minutes:02}:{seconds:02}  ·  ESC ПАУЗА",w-157,h-44,9,muted)
            return
        x,y,size = w-173,h-198,137
        scale = size/SIZE
        self.panel(x-7,y-7,size+14,size+46)
        minutes, seconds = divmod(int(self.match_time),60)
        self.label("score",f"{minutes:02}:{seconds:02}  ·  ESC ПАУЗА",x+7,y+153,9,muted)
        arcade.draw_lbwh_rectangle_outline(x,y,size,size,(76,97,102),1)
        bottom, top = max(0,oy), min(SIZE,oy+h)
        arcade.draw_lbwh_rectangle_outline(
            x+ox*scale,y+bottom*scale,min(SIZE-ox,w)*scale,(top-bottom)*scale,(74,126,125),1
        )
        for c in self.arena.cover:
            box(x+c.x*scale,y+c.y*scale,c.w*scale,c.h*scale,(105,111,91))
        for z in self.zombies:
            arcade.draw_circle_filled(x+z.x*scale,y+z.y*scale,2.8 if z.boss else 1.5,(239,120,102))
        if p.hp > 0:
            arcade.draw_circle_filled(x+p.x*scale,y+p.y*scale,3,teal)

    def draw_button(self, item):
        hover = item.contains(self.pointer)
        accent = item.accent or (232,240,235)
        fill = (61,88,119) if hover else (34,52,79)
        edge = accent if hover or item.accent else (89,119,157)
        self.panel(item.x,item.y,item.w,item.h,fill,edge)
        if item.accent:
            box(item.x+1,item.y+1,3,item.h-2,accent)
        tx = item.x+15
        if self.state == "upgrade":
            index = int(item.action.split(":")[1])+1
            self.label(f"key:{item.action}", f"{index}",tx,item.y+item.h-31,12,accent,bold=True)
            self.label(f"button:{item.action}",item.title,tx,item.y+46,16,bold=True)
            self.label(f"hint:{item.action}",item.hint,tx,item.y+22,10,(178,197,198))
        elif self.state == "settings" and item.action in ("windowed", "fullscreen", "volume:-10", "volume:10"):
            self.label(f"button:{item.action}",item.title,item.x+item.w/2,item.y+item.h/2-6,
                       11,accent,True,True)
        elif item.action.startswith("size:"):
            self.label(f"button:{item.action}",item.title,item.x+item.w/2,item.y+item.h/2-6,
                       10,accent,True,True)
        elif item.h >= 60:
            self.label(f"button:{item.action}",item.title,tx,item.y+33,12,bold=True)
            self.label(f"hint:{item.action}",item.hint,tx,item.y+14,10,(173,191,191))
        else:
            self.label(f"button:{item.action}",item.title,tx,item.y+item.h/2-6,13,accent,bold=True)
            if item.hint:
                self.label(f"hint:{self.state}:{item.action}",item.hint,item.x+item.w-54,
                           item.y+item.h/2-5,10,(173,191,191))

    def draw_title(self, x, y):
        self.panel(x-476,y-250,952,502,(26,40,66,254),(98,136,170))
        box(x-476,y+248,952,4,COLORS[1])
        left = x-440
        self.label("title","ЗОНА 04",left,y+153,62,bold=True)
        self.label("subtitle","ОДИН ПРОТИВ ОРДЫ",left,y+120,14,COLORS[1],bold=True)
        self.label("difficulty_label","СЛОЖНОСТЬ",left,y+64,11,(173,191,191),bold=True)
        self.label("difficulty_description",self.rules.description,left,y-19,12,(173,191,191))
        self.label("keys","WASD   Движение     ЛКМ   Огонь     R   Перезарядка",
                   left,y-224,11,(173,191,191))
        self.panel(x+73,y-187,366,369,(45,78,102),(114,163,180))
        box(x+74,y+166,364,15,(59,96,125))
        for i in range(14):
            arcade.draw_line(x+83+i*25,y+167,x+94+i*25,y+179,(180,152,91),2)
        for name,dx,dy,size,angle in (
            ("walker_1", 209,78,100,-1.1), ("armored_0",340,84,120,-2),
            ("spitter_1",354,-38,100,-2.9), ("caller_1",175,-58,95,.35),
        ):
            self.texture(name,x+dx,y+dy,size,size,angle)
        p = self.player
        model = self.player_models[p.weapon.sprite, "player_idle"]
        arcade.draw_texture_rect(model,arcade.XYWH(x+267,y-2,285,214),angle=34)
        self.label("record",f"РЕКОРД   {self.best} УСТРАНЕНО",
                   x+256,y-154,12,COLORS[1],True,True)

    def draw_settings(self, x, y):
        self.panel(x-328,y-222,656,462,(26,40,66,254))
        box(x-328,y+237,656,3,COLORS[0])
        self.label("settings_title","НАСТРОЙКИ",x-296,y+177,32,COLORS[1],bold=True)
        for name, title, row_y in (
            ("display","Режим экрана",126),
            ("resolution","Размер окна",70),
            ("volume","Громкость",13),
            ("minimap","Мини-карта", -43),
            ("effects","Частицы и трассеры", -99),
        ):
            self.label(f"setting:{name}",title,x-296,y+row_y-4,13,(203,218,237),bold=True)
        self.label("volume_value",f"{self.preferences.volume}%",x+139,y+17,13,COLORS[0],True,True)
        self.meter(x+53,y+4,174,4,self.preferences.volume/100,COLORS[0])

    def draw_overlay(self):
        x,y = self.view_width/2,self.view_height/2
        box(0,0,self.view_width,self.view_height,(17,28,49,173))
        if self.state == "title":
            self.draw_title(x,y)
        elif self.state == "settings":
            self.draw_settings(x,y)
        elif self.state == "upgrade":
            self.panel(x-484,y-99,968,250,(26,40,66,251))
            self.label("upgrade_title",f"УРОВЕНЬ {self.level}",x,y+96,32,COLORS[1],True,True)
            self.label("upgrade_hint","Выбери одно улучшение",x,y+70,12,(170,185,185),True)
        else:
            self.panel(x-236,y-166,472,342,(26,40,66,252))
            pause = self.state == "pause"
            self.label("overlay","ПАУЗА" if pause else "ТЫ ПОГИБ",x,y+103,40,COLORS[1],True,True)
            detail = f"Волна {self.wave}   ·   Устранено {self.kills}"
            if not pause:
                detail += f"   ·   Рекорд {self.best}"
            self.label("result",detail,x,y+66,12,(173,191,191),True)
        for item in self.menu_buttons():
            self.draw_button(item)

    def on_draw(self):
        self.on_resize(*self.get_size())
        self.clear((9,14,16))
        fb_w, fb_h = self.get_framebuffer_size()
        if min(fb_w, fb_h) <= 0:
            return
        self.game_camera.viewport = arcade.LBWH(0,0,fb_w,fb_h)
        self.game_camera.projection = arcade.LRBT(0,self.view_width,0,self.view_height)
        with self.game_camera.activate():
            ox, oy = self.origin
            self.draw_arena(ox, oy)
            self.draw_units(ox, oy)
            if self.state != "title" and not (self.state == "settings" and self.settings_return == "title"):
                self.draw_hud(ox, oy)
            if self.state == "play":
                if self.player.hp < 33:
                    amount = int((33-self.player.hp)*2)
                    arcade.draw_lbwh_rectangle_outline(0,0,self.view_width,self.view_height,
                                                      (229,79,63,amount),11)
                x,y = self.pointer
                color = (244,239,220)
                arcade.draw_circle_outline(x,y,8,color,1)
                arcade.draw_line(x-12,y,x-6,y,color,1)
                arcade.draw_line(x+6,y,x+12,y,color,1)
            else:
                self.draw_overlay()
        hide = self.state == "play"
        if self.cursor_hidden != hide:
            self.set_mouse_visible(not hide)
            self.cursor_hidden = hide


if __name__ == "__main__":
    if sys.argv[1:] == ["--check-build"]:
        shader = arcade.resources.resolve(
            ":system:shaders/shape_element_list_fs.glsl"
        )
        if not shader.read_bytes():
            raise RuntimeError("Arcade shader is empty")
        art = load_art()
        if len(art) != len(ASSET_NAMES) or len(load_player_models(art)) != 20:
            raise RuntimeError("Game sprite list is incomplete")
        for name in SOUNDS:
            with wave.open(str(ASSET_DIR / f"{name}.wav"), "rb") as sound:
                if sound.getnframes() <= 0:
                    raise RuntimeError(f"Empty sound effect {name}")
        arcade.load_sound(ASSET_DIR / "shot.wav")
    else:
        Game()
        arcade.run()
