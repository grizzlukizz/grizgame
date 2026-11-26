import math
import random
import sys
from bisect import bisect_right
from dataclasses import dataclass
from pathlib import Path

import arcade

SIZE = 3200
WIDTH, HEIGHT = 1200, 760
ASSET_DIR = Path(__file__).resolve().parent / "assets"
COLORS = [(99,222,232), (246,189,103), (198,155,248), (146,214,154)]
DIFFICULTIES = (("Разведка", .75, .72), ("Выживание", 1, 1), ("Кошмар", 1.3, 1.4))
NUMBERS = (arcade.key.KEY_1, arcade.key.KEY_2, arcade.key.KEY_3, arcade.key.KEY_4)


def clamp(value, low, high):
    return max(low, min(high, value))


def distance(a, b):
    return math.hypot(a.x - b.x, a.y - b.y)


def fit_viewport(width, height):
    scale = min(width / WIDTH, height / HEIGHT)
    w, h = max(1, round(WIDTH * scale)), max(1, round(HEIGHT * scale))
    return (width-w)//2, (height-h)//2, w, h


def box(x, y, w, h, color):
    arcade.draw_lbwh_rectangle_filled(x, y, w, h, color)


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
ARMORY = (
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
    ("Быстрые руки", "На 20% меньше времени на перезарядку"),
    ("Аптечка", "+35 здоровья каждому выжившему"),
    ("Запас патронов", "+60 патронов каждому выжившему"),
    ("Ускоренный спуск", "+20% базового темпа огня"),
    ("Бронежилеты", "Отряд получает на 15% меньше урона"),
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
    stride: float = 0
    walking: bool = False
    muzzle_flash: float = 0


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
    fallen: int | None = None


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
    *(f"fighter_{index}_{frame}" for index in range(4) for frame in range(3)),
    *(f"{kind}_{frame}" for kind in ZOMBIE_ART for frame in range(3)),
    *(weapon.sprite for weapon in WEAPONS + ARMORY),
    *(sprite for _, _, sprite in COVER_TYPES.values()),
    "supply", "ammo", "bullet", "casing", "ground", "asphalt", "concrete",
)


def load_art():
    return {name: arcade.load_texture(ASSET_DIR / f"{name}.png") for name in ASSET_NAMES}

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


class Game(arcade.Window):
    def __init__(self):
        self.switching_display = False
        super().__init__(WIDTH, HEIGHT, "Зона 04 / Карантин", resizable=True)
        self.set_minimum_size(640, 405)
        self.canvas = arcade.Camera2D(
            position=(0, 0), projection=arcade.LRBT(0, WIDTH, 0, HEIGHT), window=self
        )
        self.art = load_art()
        self.best_path = Path.home() / ".arcade-zone04-best"
        try:
            self.best = int(self.best_path.read_text())
        except (OSError, ValueError):
            self.best = 0
        self.labels = {}
        self.difficulty = 1
        self.reset()
        self.state = "title"

    def reset(self, generated=False):
        self.arena = Arena(generated)
        self.fighters = [
            Fighter(1600+x,1600+y,name,color,weapon,weapon.capacity)
            for (x,y),name,color,weapon in zip(
                [(0,0),(-65,-42),(65,-42),(0,-108)],
                ["Сокол","Гром","Искра","Ворон"], COLORS, WEAPONS)
        ]
        self.active = 0
        self.keys = set()
        self.mouse = (WIDTH*.65, HEIGHT*.5)
        self.firing = False
        self.zombies, self.shots, self.loot, self.sparks, self.casings = [], [], [], [], []
        self.state = "play"
        self.match_time = 0
        self.wave = self.spawn_left = self.kills = self.xp = 0
        self.level = 1
        self.spawn_timer = 0
        self.break_time = 4
        self.damage = self.speed = self.reload_speed = self.fire_rate = 1
        self.options = []
        self.notice = ""
        self.notice_until = 0
        self.regeneration = 0
        self.armor = 1
        self.magazine_bonus = 0
        self.armory = random.sample(ARMORY, len(ARMORY))

    @property
    def player(self):
        return self.fighters[self.active]

    @property
    def living(self):
        return [f for f in self.fighters if f.hp > 0]

    @property
    def origin(self):
        return (clamp(self.player.x-WIDTH/2,0,SIZE-WIDTH),
                clamp(self.player.y-HEIGHT/2,-91,SIZE-HEIGHT+73))

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
        return math.atan2(self.mouse[1]+y-self.player.y, self.mouse[0]+x-self.player.x)

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
                for fighter in self.living:
                    fighter.hp = min(100, fighter.hp+item.heal)
                self.notify(f"Припасы: +{amount} патронов и лечение отряда")
            else:
                self.notify(f"+{amount} патронов")

    def kill_fighter(self, fighter):
        fighter.hp = 0
        self.loot.append(Loot(
            fighter.x, fighter.y, fighter.weapon, fighter.magazine, fighter.reserve,
            fallen=self.fighters.index(fighter),
        ))
        self.notify(f"{fighter.name} погиб. Снаряжение осталось на месте.")
        if not self.living:
            self.state = "over"
            self.firing = False
            if self.kills > self.best:
                self.best = self.kills
                try:
                    self.best_path.write_text(str(self.best))
                except OSError:
                    pass
        elif fighter is self.player:
            self.active = self.fighters.index(self.living[0])

    def spawn(self, boss=False):
        p = self.player
        edge = 42 if boss else 28
        ox, oy = self.origin
        for _ in range(48):
            angle, radius = random.uniform(0,math.tau), random.uniform(760,1010)
            x = clamp(p.x+math.cos(angle)*radius,edge,SIZE-edge)
            y = clamp(p.y+math.sin(angle)*radius,edge,SIZE-edge)
            in_view = ox-42 < x < ox+WIDTH+42 and oy-42 < y < oy+HEIGHT+42
            if not in_view and math.hypot(x-p.x,y-p.y) > 710 and not self.arena.blocked(x,y,42):
                break
        else:
            x,y = (edge if p.x > SIZE/2 else SIZE-edge),clamp(p.y,edge,SIZE-edge)
        roll = random.random()
        _, health, _ = DIFFICULTIES[self.difficulty]
        hp = (36+4*self.wave)*health
        if boss:
            zombie = Zombie(x,y,hp*7,83,34,(229,126,82),boss=True,kind="boss")
        elif self.wave >= 6 and roll < .13:
            zombie = Zombie(x,y,hp*1.25,110,17,(219,140,93),kind="charger")
        elif self.wave >= 3 and roll < .29:
            zombie = Zombie(x,y,hp*1.65,70,22,(125,150,169),kind="armored",armor=hp*.8)
        elif self.wave >= 2 and roll < .55:
            zombie = Zombie(x,y,hp*.68,156,13,(202,111,100),kind="runner")
        else:
            zombie = Zombie(x,y,hp,random.uniform(75,112),16,(143,172,104))
        zombie.max_hp = zombie.hp
        self.zombies.append(zombie)

    def update_wave(self, dt):
        if self.spawn_left:
            self.spawn_timer -= dt
            if self.spawn_timer <= 0:
                self.spawn(boss=self.wave % 5 == 0 and self.spawn_left == 1)
                self.spawn_left -= 1
                self.spawn_timer = max(.19,.75-.045*self.wave)
        elif not self.zombies:
            self.break_time -= dt
            if self.break_time <= 0:
                self.wave += 1
                if self.wave > 1:
                    self.drop_supplies()
                if self.wave % 2 == 0:
                    self.drop_supplies(weapon=self.armory.pop())
                    if not self.armory:
                        self.armory = random.sample(ARMORY, len(ARMORY))
                self.spawn_left = min(70,8+self.wave*5)
                self.spawn_timer = 0
                self.break_time = 5
                self.notify(f"Волна {self.wave}")

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
            self.loot.append(Loot(x,y,None,0,38,16))

    def movement(self):
        k = arcade.key
        dx = bool(self.keys & {k.D,k.RIGHT}) - bool(self.keys & {k.A,k.LEFT})
        dy = bool(self.keys & {k.W,k.UP}) - bool(self.keys & {k.S,k.DOWN})
        return dx,dy

    def update_fighters(self, dt):
        p = self.player
        dx,dy = self.movement()
        self.arena.walk(p,dx*100,dy*100,250*self.speed*dt)
        p.angle = self.aim_angle()
        for f in self.living:
            f.cooldown = max(0,f.cooldown-dt)
            f.muzzle_flash = max(0,f.muzzle_flash-dt)
            f.hurt = max(0,f.hurt-dt)
            if not f.hurt:
                f.hp = min(100,f.hp+self.regeneration*dt)
            if f.reload > 0:
                f.reload -= dt
                if f.reload <= 0:
                    amount = min(self.capacity(f)-f.magazine,f.reserve)
                    f.magazine += amount
                    f.reserve -= amount
        if self.firing:
            self.fire(p)
        allies = [f for f in self.living if f is not p]
        for f,(dx,dy) in zip(allies,[(-65,-42),(65,-42),(0,-108)]):
            x,y = self.arena.route(f,clamp(p.x+dx,18,SIZE-18),clamp(p.y+dy,18,SIZE-18))
            f.walking = False
            if math.hypot(x-f.x,y-f.y) > 3 and self.arena.walk(f,x-f.x,y-f.y,268*self.speed*dt):
                f.angle = math.atan2(y-f.y,x-f.x)
            targets = sorted((z for z in self.zombies if distance(f,z)<360),
                             key=lambda z: distance(f,z))
            for z in targets:
                if self.arena.obstruction(f.x,f.y,z.x,z.y)[1] is None:
                    f.angle = math.atan2(z.y-f.y,z.x-f.x)
                    self.fire(f)
                    break

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

    def hurt_fighter(self, fighter, amount):
        fighter.hp -= amount * DIFFICULTIES[self.difficulty][2] * self.armor
        fighter.hurt = 1.5
        if fighter.hp <= 0:
            self.kill_fighter(fighter)

    def update_zombies(self, dt):
        for z in self.zombies:
            z.walking = False
            z.flash = max(0,z.flash-dt)
            target = min(self.living,key=lambda f: distance(z,f))
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
                    victim = next((f for f in self.living if distance(z,f) <= reach
                                   and self.arena.obstruction(z.x,z.y,f.x,f.y)[1] is None),None)
                    if victim:
                        z.charge = 0
                        self.hurt_fighter(victim, 34 if z.boss else 21)
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
                        self.hurt_fighter(target, 15 if z.kind == "armored" else 10)
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
            for other in self.zombies:
                if other is z or (x,y) != (target.x,target.y):
                    continue
                separation = distance(z,other)
                if 0 < separation < z.radius+other.radius:
                    dx += (z.x-other.x)*1.3
                    dy += (z.y-other.y)*1.3
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
            for f in self.living:
                f.hp = min(100,f.hp+35)
        elif choice == 4:
            for f in self.living:
                f.reserve += 60
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
        self.update_fighters(dt)
        self.update_shots(dt)
        self.update_zombies(dt)
        if self.state == "play":
            self.check_upgrade()

    def on_key_press(self, key, modifiers):
        k = arcade.key
        repeated = key in self.keys
        self.keys.add(key)
        if repeated:
            return
        if key == k.F11 or (key == k.ENTER and modifiers & k.MOD_ALT):
            self.firing = False
            self.switching_display = True
            try:
                self.set_fullscreen(not self.fullscreen)
            finally:
                self.switching_display = False
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
            elif key in NUMBERS and self.fighters[NUMBERS.index(key)].hp > 0:
                self.active = NUMBERS.index(key)
            elif key == k.TAB:
                positions = [(self.active+i)%4 for i in range(1,5)]
                self.active = next(i for i in positions if self.fighters[i].hp > 0)
            elif key == k.R:
                self.reload_weapon(self.player)
            elif key == k.E:
                self.collect()
            elif key == k.F:
                self.collect(swap=True)

    def on_key_release(self, key, modifiers):
        self.keys.discard(key)

    def update_pointer(self, x, y):
        left, bottom, w, h = fit_viewport(*self.get_size())
        u, v = (x-left)/w, (y-bottom)/h
        self.mouse = clamp(u, 0, 1)*WIDTH, clamp(v, 0, 1)*HEIGHT
        return 0 <= u <= 1 and 0 <= v <= 1

    def on_mouse_motion(self, x, y, dx, dy):
        self.update_pointer(x, y)

    def on_mouse_drag(self, x, y, dx, dy, buttons, modifiers):
        self.update_pointer(x, y)

    def on_mouse_press(self, x, y, button, modifiers):
        inside = self.update_pointer(x, y)
        if inside and button == arcade.MOUSE_BUTTON_LEFT and self.state == "play":
            self.firing = True

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
        box(0, 0, WIDTH, HEIGHT, (20,28,28))
        tile = 192
        for x in range(int(ox)//tile*tile, int(ox+WIDTH)+1, tile):
            for y in range(int(oy)//tile*tile, int(oy+HEIGHT)+1, tile):
                self.texture("ground", x+tile/2-ox, y+tile/2-oy, tile, tile)
        for lane in arena.lanes_x:
            x = lane-ox
            if not -arena.road < x < WIDTH+arena.road:
                continue
            box(x-arena.road/2-4, -oy, arena.road+8, SIZE, (89,99,88))
            for y in range(max(0,int(oy)//tile*tile), min(SIZE,int(oy+HEIGHT)+1), tile):
                height = min(tile,SIZE-y)
                self.texture("asphalt", x, y+height/2-oy, arena.road, height)
            for y in range(max(0,int(oy)//84*84), min(SIZE-30,int(oy+HEIGHT)+1), 84):
                box(x-1,y-oy,2,30,(134,126,89))
        for lane in arena.lanes_y:
            y = lane-oy
            if not -arena.road < y < HEIGHT+arena.road:
                continue
            box(-ox, y-arena.road/2-4, SIZE, arena.road+8, (89,99,88))
            for x in range(max(0,int(ox)//tile*tile), min(SIZE,int(ox+WIDTH)+1), tile):
                width = min(tile,SIZE-x)
                self.texture("asphalt", x+width/2-ox, y, width, arena.road)
            for x in range(max(0,int(ox)//84*84), min(SIZE-30,int(ox+WIDTH)+1), 84):
                box(x-ox,y-1,30,2,(134,126,89))
        for lane_x in arena.lanes_x:
            for lane_y in arena.lanes_y:
                x, y = lane_x-ox, lane_y-oy
                size = arena.plaza if arena.generated else arena.road
                if -size < x < WIDTH+size and -size < y < HEIGHT+size:
                    self.texture("concrete", x, y, size, size)
                    arcade.draw_lbwh_rectangle_outline(x-size/2+5,y-size/2+5,size-10,size-10,(100,112,99),1)
        arcade.draw_lbwh_rectangle_outline(5-ox,5-oy,SIZE-10,SIZE-10,(193,139,75),8)
        for c in arena.cover:
            x, y = c.x-ox, c.y-oy
            if x < WIDTH and y < HEIGHT and x+c.w > 0 and y+c.h > 0:
                item = COVER_TYPES[c.kind][2]
                box(x+7,y-7,c.w,c.h,(11,22,20,165))
                if c.w >= c.h:
                    self.texture(item, x+c.w/2, y+c.h/2, c.w, c.h)
                else:
                    self.texture(item, x+c.w/2, y+c.h/2, c.h, c.w, math.pi/2)

    def draw_units(self, ox, oy):
        for item in self.loot:
            x, y = item.x-ox, item.y-oy
            if not (-45 < x < WIDTH+45 and -45 < y < HEIGHT+45):
                continue
            if item.fallen is not None:
                self.texture(f"fighter_{item.fallen}_0", x-7, y-5, 58, 58, -.9, 145)
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
            if not (-150 < x < WIDTH+150 and -150 < y < HEIGHT+150):
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
        for f in self.living:
            x, y = f.x-ox, f.y-oy
            index = self.fighters.index(f)
            frame = 1+int(f.stride/9)%2 if f.walking else 0
            arcade.draw_ellipse_filled(x+3,y-4,29,22,(11,19,18,180))
            if f is self.player:
                arcade.draw_circle_outline(x,y,21,f.color,2)
            self.texture(f"fighter_{index}_{frame}", x, y, 48, 48, f.angle)
            dx, dy = math.cos(f.angle), math.sin(f.angle)
            length = f.weapon.muzzle+7
            grip = f.weapon.muzzle-length*.43
            self.texture(f.weapon.sprite, x+dx*grip, y+dy*grip, length, length*.375, f.angle)
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

    def draw_hud(self, ox, oy):
        box(0,HEIGHT-71,WIDTH,71,(13,21,23))
        self.label("brand","ЗОНА 04",24,HEIGHT-30,20,COLORS[0],bold=True)
        mode = "СЛУЧАЙНАЯ КАРТА" if self.arena.generated else "КЛАССИЧЕСКАЯ КАРТА"
        self.label("mode",f"{mode}  /  {DIFFICULTIES[self.difficulty][0]}",25,HEIGHT-52,10)
        threats = len(self.zombies)+self.spawn_left
        status = (f"ВОЛНА {self.wave:02}   /   УГРОЗЫ {threats}" if threats
                  else f"ДО ВОЛНЫ {self.wave+1:02}   /   {math.ceil(self.break_time)} с")
        self.label("wave",status,WIDTH/2,HEIGHT-31,16,center=True,bold=True)
        self.label("level",f"УРОВЕНЬ {self.level}",WIDTH/2,HEIGHT-54,10,COLORS[0],True)
        minutes,seconds = divmod(int(self.match_time),60)
        self.label("score",f"УСТРАНЕНО {self.kills:03}   {minutes:02}:{seconds:02}",930,HEIGHT-32)
        box(0,HEIGHT-73,WIDTH,3,(57,73,67))
        box(0,HEIGHT-73,WIDTH*self.xp/self.xp_goal,3,COLORS[0])
        box(0,0,WIDTH,91,(13,21,23))
        for i,f in enumerate(self.fighters):
            x = 20+i*170
            color = f.color if f.hp > 0 else (136,145,143)
            box(x,13,160,63,(31,52,53) if f is self.player else (25,36,37))
            box(x,13,3,63,color)
            self.label(f"name{i}",f"{i+1}   {f.name}",x+12,52,13,color,bold=True)
            self.label(f"gun{i}",f.weapon.name if f.hp>0 else "Погиб",x+12,32,10)
            if f.hp > 0:
                box(x+12,22,135,3,(67,84,81))
                box(x+12,22,135*f.hp/100,3,color)
        p = self.player
        ammo = "ПЕРЕЗАРЯДКА" if p.reload > 0 else f"{p.magazine:02}  /  {p.reserve:03}"
        self.label("ammo",ammo,730,37,21,p.color,bold=True)
        self.label("reload","R  ПЕРЕЗАРЯДИТЬ",731,18,10)
        self.label("controls","WASD ХОДЬБА   ЛКМ ОГОНЬ   ESC ПАУЗА",914,57,10)
        self.label("display", "F11  ПОЛНЫЙ ЭКРАН", 914, 39, 10)
        dash_left = max(0,p.dash_ready-self.match_time)
        self.label("dash",f"ПРОБЕЛ  РЫВОК  {dash_left:.1f} с" if dash_left else "ПРОБЕЛ  РЫВОК ГОТОВ",914,21,10,p.color)
        if self.match_time < self.notice_until:
            self.label("notice",self.notice,WIDTH/2,HEIGHT-104,13,COLORS[1],True,True)
        ammo_drop,weapon_drop = self.nearby(False),self.nearby(True)
        actions = []
        if ammo_drop:
            actions.append("E  подобрать припасы" if ammo_drop.heal else "E  подобрать патроны")
        if weapon_drop:
            actions.append(f"F  взять оружие «{weapon_drop.weapon.name}»")
        if actions and p.hp > 0:
            box(255,105,690,39,(12,21,22,235))
            self.label("loot","    /    ".join(actions),WIDTH/2,118,13,COLORS[1],True)
        x,y,scale = 1054,540,125/SIZE
        box(x-4,y-4,133,133,(12,20,20,228))
        arcade.draw_lbwh_rectangle_outline(x,y,125,125,(92,117,105),1)
        bottom, top = max(0, oy), min(SIZE, oy+HEIGHT)
        arcade.draw_lbwh_rectangle_outline(
            x+ox*scale, y+bottom*scale, WIDTH*scale, (top-bottom)*scale, (71,110,103), 1
        )
        for c in self.arena.cover:
            box(x+c.x*scale,y+c.y*scale,c.w*scale,c.h*scale,(105,111,91))
        for z in self.zombies:
            arcade.draw_circle_filled(x+z.x*scale,y+z.y*scale,1.6,(206,116,102))
        for f in self.living:
            arcade.draw_circle_filled(x+f.x*scale,y+f.y*scale,3 if f is p else 2,f.color)

    def draw_overlay(self):
        box(0,0,WIDTH,HEIGHT,(8,15,16,220))
        title,lines = {
            "title": ("ЗОНА 04", ("Четыре бойца против орды",
                      "1  Классическая карта     /     2  Случайная карта",
                      "WASD или стрелки — ходьба    /    ЛКМ — огонь    /    R — перезарядка",
                      "1–4 или Tab — сменить бойца    /    E — припасы    /    F — оружие",
                      f"Пробел — рывок    /    F2 — сложность: {DIFFICULTIES[self.difficulty][0]}",
                      "F11 или Alt+Enter — полный экран")),
            "pause": ("ПАУЗА",("ESC  Продолжить    /    M  В меню",)),
            "upgrade": (f"УРОВЕНЬ {self.level}",("Выбери одно улучшение для отряда",)),
            "over": ("ОТРЯД ПОГИБ",(f"Волна {self.wave}   /   Устранено {self.kills}   /   Рекорд {self.best}",
                     "ENTER  Повторить режим     /     1  Классическая     /     2  Случайная",
                     f"F2  Сложность: {DIFFICULTIES[self.difficulty][0]}")),
        }[self.state]
        self.label("overlay",title,WIDTH/2,467,55,COLORS[0],True,True)
        for i,line in enumerate(lines):
            self.label(f"overlay{i}",line,WIDTH/2,422-i*36,17,center=True)
        if self.state == "upgrade":
            for i,choice in enumerate(self.options):
                x = 79+i*350
                title,description = UPGRADES[choice]
                box(x,264,342,110,(28,47,48))
                box(x,264,342,3,COLORS[i])
                self.label(f"opt{i}",f"{i+1}   {title}",x+16,327,17,COLORS[i],bold=True)
                self.label(f"desc{i}",description,x+16,294,11)

    def on_draw(self):
        self.clear((9,14,16))
        self.canvas.viewport = arcade.LBWH(*fit_viewport(*self.get_framebuffer_size()))
        with self.canvas.activate():
            ox, oy = self.origin
            self.draw_arena(ox, oy)
            self.draw_units(ox, oy)
            self.draw_hud(ox, oy)
            if self.state == "play":
                x, y = self.mouse
                color = (232,241,224)
                arcade.draw_circle_outline(x,y,8,color,1)
                arcade.draw_line(x-12,y,x-6,y,color,1)
                arcade.draw_line(x+6,y,x+12,y,color,1)
            else:
                self.draw_overlay()


if __name__ == "__main__":
    if sys.argv[1:] == ["--check-build"]:
        shader = arcade.resources.resolve(
            ":system:shaders/shape_element_list_fs.glsl"
        )
        if not shader.read_bytes():
            raise RuntimeError("Arcade shader is empty")
        if len(load_art()) != len(ASSET_NAMES):
            raise RuntimeError("Game sprite list contains duplicate names")
    else:
        Game()
        arcade.run()
