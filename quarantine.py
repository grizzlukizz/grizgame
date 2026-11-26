import math
import random
import sys
from bisect import bisect_right
from dataclasses import dataclass
from pathlib import Path

import arcade
from PIL import Image

SIZE = 3200
WIDTH, HEIGHT = 1200, 760
ASSET_DIR = Path(__file__).resolve().parent / "assets"
COLORS = [(99,222,232), (246,189,103), (198,155,248), (146,214,154)]
NUMBERS = (arcade.key.KEY_1, arcade.key.KEY_2, arcade.key.KEY_3)


def clamp(value, low, high):
    return max(low, min(high, value))


def distance(a, b):
    return math.hypot(a.x - b.x, a.y - b.y)


def view_size(width, height):
    scale = min(max(1, width)/1080, max(1, height)/HEIGHT)
    return max(1, width)/scale, max(1, height)/scale


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
)


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
ZOMBIE_ART = ("walker", "runner", "armored", "charger", "boss")
ASSET_NAMES = (
    "player_idle", "player_walk",
    *(f"{kind}_{frame}" for kind in ZOMBIE_ART for frame in range(3)),
    *(weapon.sprite for weapon in WEAPONS[:1] + CACHE_WEAPONS),
    *(sprite for _, _, sprite in COVER_TYPES.values()),
    "supply", "ammo", "bullet", "casing", "ground", "asphalt", "concrete",
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
        self.screen_path = Path.home() / ".arcade-zone04-display"
        try:
            full = self.screen_path.read_text().strip() == "fullscreen"
        except (OSError, UnicodeError):
            full = False
        super().__init__(WIDTH, HEIGHT, "Зона 04 / Карантин", resizable=True, fullscreen=full)
        self.set_minimum_size(640, 405)
        self.view_width, self.view_height = view_size(*self.get_size())
        self.game_camera = arcade.Camera2D(
            position=(0, 0), projection=arcade.LRBT(0, self.view_width, 0, self.view_height), window=self
        )
        self.art = load_art()
        self.player_models = load_player_models(self.art)
        self.best_path = Path.home() / ".arcade-zone04-best"
        try:
            self.best = int(self.best_path.read_text())
        except (OSError, ValueError):
            self.best = 0
        self.labels = {}
        self.difficulty = 1
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
        self.zombies, self.shots, self.loot, self.sparks, self.casings = [], [], [], [], []
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

    def burst(self, x, y, color, count):
        for _ in range(count):
            angle = random.uniform(0, math.tau)
            speed = random.uniform(30, 150)
            self.sparks.append(Spark(x, y, math.cos(angle)*speed, math.sin(angle)*speed, color, .22))

    def aim_angle(self):
        x, y = self.origin
        return math.atan2(self.pointer[1]+y-self.player.y, self.pointer[0]+x-self.player.x)

    def dash(self):
        fighter = self.player
        if fighter.dash_ready > self.match_time:
            return
        dx, dy = self.movement()
        if not (dx or dy):
            angle = self.aim_angle()
            dx, dy = math.cos(angle), math.sin(angle)
        x, y = fighter.x, fighter.y
        self.arena.move(fighter, dx*160, dy*160, 145)
        if math.hypot(x-fighter.x, y-fighter.y) > 1:
            fighter.dash_ready = self.match_time + 2.4
            self.burst(x, y, fighter.color, 14)

    def reload_weapon(self, fighter):
        if fighter.reload <= 0 and fighter.magazine < self.capacity(fighter) and fighter.reserve:
            fighter.reload = fighter.weapon.reload_time/self.reload_speed

    def fire(self, fighter):
        if fighter.cooldown > 0 or fighter.reload > 0:
            return
        if fighter.magazine == 0:
            self.reload_weapon(fighter)
            return
        fighter.magazine -= 1
        weapon = fighter.weapon
        fighter.cooldown = weapon.interval / self.fire_rate
        fighter.muzzle_flash = .065
        fighter.shot_angle = fighter.angle
        dx, dy = math.cos(fighter.angle), math.sin(fighter.angle)
        muzzle_x, muzzle_y = weapon.muzzle*dx, weapon.muzzle*dy
        self.casings.append(Casing(fighter.x+14*dx, fighter.y+14*dy, 82*dy, -82*dx, fighter.angle))
        for spread in weapon.spread:
            angle = fighter.angle + spread
            self.shots.append(Shot(
                fighter.x, fighter.y, weapon.velocity*math.cos(angle), weapon.velocity*math.sin(angle),
                weapon.damage*self.damage, weapon.flight_time, muzzle_x, muzzle_y,
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
                f.hp = min(100, f.hp+item.heal)
                self.notify(f"Припасы дают {amount} патронов и {item.heal} здоровья")
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
        elif self.wave >= (6 if self.difficulty == 0 else 4) and roll < .21:
            zombie = Zombie(x,y,hp*1.25,110,17,(219,140,93),kind="charger")
        elif self.wave >= (3 if self.difficulty == 0 else 2) and roll < .42:
            zombie = Zombie(x,y,hp*1.65,70,22,(125,150,169),kind="armored",armor=hp*.8)
        elif self.wave >= (1 if self.difficulty == 2 else 2) and roll < .67:
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
        dx, dy = self.movement()
        old_x, old_y = p.x, p.y
        self.arena.move(p, dx*100, dy*100, 250*self.speed*dt)
        dx, dy = p.x-old_x, p.y-old_y
        p.walking = math.hypot(dx, dy) > .01
        if p.walking:
            p.move_angle = math.atan2(dy, dx)
        p.angle = self.aim_angle()
        p.cooldown = max(0, p.cooldown-dt)
        p.muzzle_flash = max(0, p.muzzle_flash-dt)
        p.hurt = max(0, p.hurt-dt)
        if not p.hurt:
            p.hp = min(100, p.hp+self.regeneration*dt)
        if p.reload > 0:
            p.reload -= dt
            if p.reload <= 0:
                amount = min(self.capacity(p)-p.magazine, p.reserve)
                p.magazine += amount
                p.reserve -= amount
        if self.firing:
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
        length_sq = dx*dx + dy*dy
        wall_at, cover = self.arena.obstruction(shot.x, shot.y, ex, ey)
        hit, hit_at = None, wall_at
        for z in self.zombies:
            zx, zy = shot.x-z.x, shot.y-z.y
            projection = zx*dx + zy*dy
            offset = zx*zx + zy*zy - z.radius*z.radius
            discriminant = projection*projection - length_sq*offset
            if discriminant < 0:
                continue
            root = math.sqrt(discriminant)
            entry = max(0, (-projection-root)/length_sq)
            exit_at = (-projection+root)/length_sq
            if exit_at >= 0 and entry <= 1 and entry < hit_at:
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
        self.player.hp -= amount * self.rules.damage * self.armor
        self.player.hurt = 1.5
        if self.player.hp <= 0:
            self.end_match()

    def update_zombies(self, dt):
        target = self.player
        for z in self.zombies:
            z.walking = False
            z.flash = max(0,z.flash-dt)
            gap = distance(z,target)
            clear = self.arena.obstruction(z.x,z.y,target.x,target.y)[1] is None
            reach = z.radius + 26
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
                    z.attack_ready = self.match_time + (2.5 if z.kind in ("charger","boss") else .7)
                    if z.kind in ("charger","boss"):
                        z.charge = .44
                    elif gap <= reach and clear:
                        self.hurt_player(15 if z.kind == "armored" else 10)
                        if self.state == "over":
                            return
                continue
            attack_range = 145 if z.kind in ("charger","boss") else reach
            if gap <= attack_range and clear and self.match_time >= z.attack_ready:
                z.windup = .55 if z.kind in ("charger","boss") else .22
                z.heading = z.angle = math.atan2(target.y-z.y,target.x-z.x)
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
            self.player.hp = min(100, self.player.hp+35)
        elif choice == 4:
            self.player.reserve += 60
        elif choice == 5:
            self.fire_rate += .2
        elif choice == 6:
            self.armor *= .85
        elif choice == 7:
            self.regeneration += 1
        else:
            self.magazine_bonus += 4
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
            self.check_upgrade()

    def on_resize(self, width, height):
        self.view_width, self.view_height = view_size(width, height)

    def toggle_display(self):
        self.firing = False
        self.switching_display = True
        try:
            self.set_fullscreen(not self.fullscreen)
            self.on_resize(*self.get_size())
        finally:
            self.switching_display = False
        try:
            self.screen_path.write_text("fullscreen" if self.fullscreen else "windowed")
        except OSError:
            pass

    def menu_buttons(self):
        x, y = self.view_width/2, self.view_height/2
        display = "Полный экран" if self.fullscreen else "В окне"
        if self.state == "title":
            left = x-440
            return [
                *(MenuButton(f"difficulty:{i}", rules.name, left+i*160, y+6, 151, 42,
                             accent=COLORS[1] if self.difficulty == i else None)
                  for i, rules in enumerate(DIFFICULTIES)),
                MenuButton("classic", "Классическая карта", left, y-115, 231, 66, "1  /  Открытая арена", COLORS[1]),
                MenuButton("generated", "Случайная карта", left+244, y-115, 231, 66, "2  /  Кварталы и укрытия", COLORS[0]),
                MenuButton("display", display, left, y-184, 231, 43, "F11"),
                MenuButton("quit", "Выйти", left+244, y-184, 231, 43),
            ]
        if self.state in ("pause", "over"):
            pause = self.state == "pause"
            return [
                MenuButton("resume" if pause else "restart", "Продолжить" if pause else "Сыграть снова",
                           x-206, y-15, 412, 58, "Esc" if pause else "Enter", COLORS[1]),
                MenuButton("display", display, x-206, y-79, 412, 50, "F11"),
                MenuButton("title", "Главное меню", x-206, y-137, 412, 46, "M"),
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
        elif name == "upgrade":
            self.choose(int(value))
        elif name == "display":
            self.toggle_display()
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
        if self.state in ("title","over"):
            if key in NUMBERS[:2]:
                self.reset(key == NUMBERS[1])
                self.keys.add(key)
            elif key == k.ENTER:
                self.reset(self.arena.generated)
                self.keys.add(key)
            elif key == k.F2:
                self.difficulty = (self.difficulty+1) % len(DIFFICULTIES)
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
        box(0, 0, self.view_width, self.view_height, (20,28,28))
        tile = 192
        for x in range(int(ox)//tile*tile, int(ox+self.view_width)+1, tile):
            for y in range(int(oy)//tile*tile, int(oy+self.view_height)+1, tile):
                self.texture("ground", x+tile/2-ox, y+tile/2-oy, tile, tile)
        for lane in arena.lanes_x:
            x = lane-ox
            if not -arena.road < x < self.view_width+arena.road:
                continue
            box(x-arena.road/2-4, -oy, arena.road+8, SIZE, (89,99,88))
            for y in range(max(0,int(oy)//tile*tile), min(SIZE,int(oy+self.view_height)+1), tile):
                height = min(tile,SIZE-y)
                self.texture("asphalt", x, y+height/2-oy, arena.road, height)
            for y in range(max(0,int(oy)//84*84), min(SIZE-30,int(oy+self.view_height)+1), 84):
                box(x-1,y-oy,2,30,(134,126,89))
        for lane in arena.lanes_y:
            y = lane-oy
            if not -arena.road < y < self.view_height+arena.road:
                continue
            box(-ox, y-arena.road/2-4, SIZE, arena.road+8, (89,99,88))
            for x in range(max(0,int(ox)//tile*tile), min(SIZE,int(ox+self.view_width)+1), tile):
                width = min(tile,SIZE-x)
                self.texture("asphalt", x+width/2-ox, y, width, arena.road)
            for x in range(max(0,int(ox)//84*84), min(SIZE-30,int(ox+self.view_width)+1), 84):
                box(x-ox,y-1,30,2,(134,126,89))
        for lane_x in arena.lanes_x:
            for lane_y in arena.lanes_y:
                x, y = lane_x-ox, lane_y-oy
                size = arena.plaza if arena.generated else arena.road
                if -size < x < self.view_width+size and -size < y < self.view_height+size:
                    self.texture("concrete", x, y, size, size)
                    arcade.draw_lbwh_rectangle_outline(x-size/2+5,y-size/2+5,size-10,size-10,(100,112,99),1)
        arcade.draw_lbwh_rectangle_outline(5-ox,5-oy,SIZE-10,SIZE-10,(193,139,75),8)
        for c in arena.cover:
            x, y = c.x-ox, c.y-oy
            if x < self.view_width and y < self.view_height and x+c.w > 0 and y+c.h > 0:
                item = COVER_TYPES[c.kind][2]
                box(x+7,y-7,c.w,c.h,(11,22,20,165))
                if c.w >= c.h:
                    self.texture(item, x+c.w/2, y+c.h/2, c.w, c.h)
                else:
                    self.texture(item, x+c.w/2, y+c.h/2, c.h, c.w, math.pi/2)

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
                arcade.draw_circle_outline(x,y,z.radius+7,(255,199,109),2)
                if z.kind in ("charger","boss"):
                    arcade.draw_line(x,y,x+math.cos(z.heading)*118,y+math.sin(z.heading)*118,(255,199,109),2)
            if z.boss:
                box(x-36,y+44,72,5,(74,49,45))
                box(x-36,y+44,72*z.hp/z.max_hp,5,z.color)
        f = self.player
        if f.hp > 0:
            x, y = f.x-ox, f.y-oy
            pose = "player_walk" if f.walking else "player_idle"
            angle = f.move_angle if f.walking and not self.firing else f.angle
            if f.muzzle_flash:
                angle = f.shot_angle
            arcade.draw_ellipse_filled(x+3,y-4,29,22,(11,19,18,180))
            model = self.player_models[f.weapon.sprite, pose]
            arcade.draw_texture_rect(model, arcade.XYWH(x,y,96,72), angle=math.degrees(angle))
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
            box(x-14,y+27,28*f.hp/100,3,f.color)
        for spark in self.sparks:
            arcade.draw_circle_filled(spark.x-ox,spark.y-oy,1+spark.life*9,spark.color)
        for shot in self.shots:
            x, y = shot.x-ox, shot.y-oy
            if shot.trail:
                start_x, start_y = shot.trail
                arcade.draw_line(start_x-ox,start_y-oy,x,y,(255,189,79,135),1)
            self.texture("bullet", x, y, 12, 4.3, math.atan2(shot.vy,shot.vx))

    def panel(self, x, y, w, h, color=(20,29,32,244), edge=(57,73,76)):
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
        teal, gold, muted = COLORS[0], COLORS[1], (157,177,179)
        self.panel(22,h-80,248,58)
        self.label("brand","ЗОНА 04",39,h-45,19,teal,bold=True)
        mode = "Случайная" if self.arena.generated else "Классическая"
        self.label("mode",f"{mode}  /  {self.rules.name}",39,h-65,10,muted)

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
        self.label("hp",f"{math.ceil(p.hp):02} / 100",93,49,17,hp_color,bold=True)
        self.meter(93,35,176,5,p.hp/100,hp_color)

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
        fill = (48,63,64) if hover else (27,40,43)
        edge = accent if hover or item.accent else (60,78,82)
        self.panel(item.x,item.y,item.w,item.h,fill,edge)
        if item.accent:
            box(item.x+1,item.y+1,3,item.h-2,accent)
        tx = item.x+15
        if self.state == "upgrade":
            index = int(item.action.split(":")[1])+1
            self.label(f"key:{item.action}", f"{index}",tx,item.y+item.h-31,12,accent,bold=True)
            self.label(f"button:{item.action}",item.title,tx,item.y+46,16,bold=True)
            self.label(f"hint:{item.action}",item.hint,tx,item.y+22,10,(178,197,198))
        elif item.h >= 60:
            self.label(f"button:{item.action}",item.title,tx,item.y+33,12,bold=True)
            self.label(f"hint:{item.action}",item.hint,tx,item.y+14,10,(173,191,191))
        else:
            self.label(f"button:{item.action}",item.title,tx,item.y+item.h/2-6,13,accent,bold=True)
            if item.hint:
                self.label(f"hint:{self.state}:{item.action}",item.hint,item.x+item.w-54,
                           item.y+item.h/2-5,10,(173,191,191))

    def draw_title(self, x, y):
        self.panel(x-476,y-250,952,502,(16,25,29,254),(75,93,91))
        box(x-476,y+248,952,4,COLORS[1])
        left = x-440
        self.label("title","ЗОНА 04",left,y+153,62,bold=True)
        self.label("subtitle","ОДИН ПРОТИВ ОРДЫ",left,y+120,14,COLORS[1],bold=True)
        self.label("difficulty_label","СЛОЖНОСТЬ",left,y+64,11,(173,191,191),bold=True)
        self.label("difficulty_description",self.rules.description,left,y-19,12,(173,191,191))
        self.label("keys","WASD   Движение     ЛКМ   Огонь     R   Перезарядка",
                   left,y-224,11,(173,191,191))
        self.panel(x+73,y-187,366,369,(24,39,39),(65,87,86))
        box(x+74,y+166,364,15,(50,63,57))
        for i in range(14):
            arcade.draw_line(x+83+i*25,y+167,x+94+i*25,y+179,(180,152,91),2)
        for name,dx,dy,size,angle in (
            ("walker_1", 209,78,100,-1.1), ("armored_0",340,84,120,-2),
            ("runner_1",354,-38,100,-2.9), ("charger_1",175,-58,95,.35),
        ):
            self.texture(name,x+dx,y+dy,size,size,angle)
        p = self.player
        model = self.player_models[p.weapon.sprite, "player_idle"]
        arcade.draw_texture_rect(model,arcade.XYWH(x+267,y-2,285,214),angle=34)
        self.label("record",f"РЕКОРД   {self.best} УСТРАНЕНО",
                   x+256,y-154,12,COLORS[1],True,True)

    def draw_overlay(self):
        x,y = self.view_width/2,self.view_height/2
        box(0,0,self.view_width,self.view_height,(8,14,17,188))
        if self.state == "title":
            self.draw_title(x,y)
        elif self.state == "upgrade":
            self.panel(x-484,y-99,968,250,(16,25,29,251))
            self.label("upgrade_title",f"УРОВЕНЬ {self.level}",x,y+96,32,COLORS[1],True,True)
            self.label("upgrade_hint","Выбери одно улучшение",x,y+70,12,(170,185,185),True)
        else:
            self.panel(x-236,y-166,472,342,(16,25,29,252))
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
            if self.state != "title":
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
    else:
        Game()
        arcade.run()
