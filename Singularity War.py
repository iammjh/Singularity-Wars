# Singularity Wars
from OpenGL.GL import *
from OpenGL.GLU import *
from OpenGL.GLUT import *
from OpenGL.GLUT import GLUT_BITMAP_HELVETICA_18
import math, random

fovY = 50
first_person = False
WORLD_MIN = -2500
WORLD_MAX = 2500
WORLD_Z_MIN = -600.0
WORLD_Z_MAX = 600.0

vel_x, vel_y = 0.0, 0.0
ACCELERATION = 1.00
MAX_SPEED = 24.0
DRAG = 0.785

vel_z = 0.0
ACCELERATION_Z = 0.9
MAX_SPEED_Z = 18.0
DRAG_Z = 0.785

keys = {'w': False, 's': False, 'a': False, 'd': False, 'q': False, 'e': False}

top5_scores = []
last_round_score = 0
_scoreboard_locked = False

gun_level = 1
game_over = False
controls_disabled = False

#Ship
SHIP_SCALE = 0.6
SHIP_COLLISION_R = 45.0 * SHIP_SCALE
player_x, player_y, player_z = 0.0, 0.0, 30.0
player_angle = 0.0
rot_step = 1

player_bullets = []
player_bullet_cd = 0

PLAYER_BULLET_DRAW_SCALE = 0.22
PLAYER_BULLET_HIT_R = 18.0
ENEMY_HIT_R = 38.0

AUTOAIM_MAX_RANGE = 1400.0
AUTOAIM_CONE_DEG = 14.0
AUTOAIM_CONE_COS = math.cos(math.radians(AUTOAIM_CONE_DEG))
def _pick_autoaim_target(muzzle_x, muzzle_y, muzzle_z, fx, fy):
    best_i = -1
    best_score = -1e9
    best_pos = None

    f_len = math.sqrt(fx*fx + fy*fy)
    if f_len < 1e-6:
        return -1, 0, 0, 0
    fux, fuy = fx / f_len, fy / f_len

    for i, e in enumerate(enemies):
        ex, ey, ez = e[0], e[1], e[2]

        dx = ex - muzzle_x
        dy = ey - muzzle_y
        dz = ez - muzzle_z

        d2 = dx*dx + dy*dy + dz*dz
        if d2 < 1.0:
            continue
        if d2 > (AUTOAIM_MAX_RANGE * AUTOAIM_MAX_RANGE):
            continue

        d_xy = math.sqrt(dx*dx + dy*dy)
        if d_xy < 1e-6:
            continue

        ux, uy = dx / d_xy, dy / d_xy
        cosang = (ux * fux + uy * fuy)
        if cosang < AUTOAIM_CONE_COS:
            continue

        dist = math.sqrt(d2)
        score = (cosang * 2.0) - (dist / AUTOAIM_MAX_RANGE)
        if score > best_score:
            best_score = score
            best_i = i
            best_pos = (ex, ey, ez)

    if best_i == -1:
        return -1, 0, 0, 0
    return best_i, best_pos[0], best_pos[1], best_pos[2]


SHIP_STATS_BY_LEVEL = {
    1: {"hp": 200, "speed_mult": 1.00, "thrust": 0.5},
    2: {"hp": 270, "speed_mult": 1.08, "thrust": 0.9},
    3: {"hp": 350, "speed_mult": 1.15, "thrust": 1.3},
    4: {"hp": 420, "speed_mult": 1.23, "thrust": 1.6},
    5: {"hp": 500, "speed_mult": 1.29, "thrust": 2.0},
}

ship_level = 1
player_max_hp = SHIP_STATS_BY_LEVEL[ship_level]["hp"]
player_life = player_max_hp

SHIP_UPGRADE_REQUIREMENTS = [
    (1, 0),
    (2, 7),
    (3, 13),
    (4, 19),
    (5, 25),
]

def _update_ship_level_from_progress():
    global ship_level
    new_level = ship_level
    for lvl, need_kills in SHIP_UPGRADE_REQUIREMENTS:
        if enemy_kills_total >= need_kills:
            new_level = lvl
    if new_level != ship_level:
        set_ship_level(new_level)

player_score = 0

#Weapon
WEAPON_STATS_BY_LEVEL = {
    1: {"dmg": 40, "fire_mult": 1.00, "speed_mult": 1.00},
    2: {"dmg": 50, "fire_mult": 1.15, "speed_mult": 1.10},
    3: {"dmg": 60, "fire_mult": 1.25, "speed_mult": 1.20},
    4: {"dmg": 70, "fire_mult": 1.35, "speed_mult": 1.27},
    5: {"dmg": 90, "fire_mult": 1.50, "speed_mult": 1.32},
}

BASE_PLAYER_BULLET_SPEED = 26.0
BASE_PLAYER_BULLET_COOLDOWN_FRAMES = 8

GUN_LEVEL_BY_TOTAL_KILLS = [
    (1, 0),
    (2, 5),
    (3, 9),
    (4, 15),
    (5, 25),
]
enemy_kills_total = 0

def _weapon_stats():
    lvl = clamp(int(gun_level), 1, 5)
    return WEAPON_STATS_BY_LEVEL.get(lvl, WEAPON_STATS_BY_LEVEL[1])

def _update_gun_level_from_kills():
    global gun_level
    lvl = 1
    for L, need in GUN_LEVEL_BY_TOTAL_KILLS:
        if enemy_kills_total >= need:
            lvl = L
    gun_level = lvl

def register_enemy_kill():
    global enemy_kills_total
    enemy_kills_total += 1
    _update_gun_level_from_kills()
    _update_ship_level_from_progress()

def _player_bullet_speed():
    s = _weapon_stats()
    return BASE_PLAYER_BULLET_SPEED * s["speed_mult"]

def _player_bullet_damage():
    s = _weapon_stats()
    return int(s["dmg"])

def _player_bullet_cooldown_frames():
    s = _weapon_stats()
    return max(1, int(round(BASE_PLAYER_BULLET_COOLDOWN_FRAMES / max(0.001, s["fire_mult"]))))

def _player_bullet_life_frames(spd):
    map_len = float(WORLD_MAX - WORLD_MIN)
    return max(10, int(map_len / max(0.001, spd)))


def _spawn_player_bullet():
    global player_bullet_cd

    if game_over or controls_disabled:
        return
    if player_bullet_cd > 0:
        return

    rad = math.radians(player_angle)
    fx, fy = math.cos(rad), math.sin(rad)

    muzzle_dist = 135.0 * SHIP_SCALE
    sx = player_x + fx * muzzle_dist
    sy = player_y + fy * muzzle_dist
    sz = player_z

    spd = _player_bullet_speed()
    dmg = _player_bullet_damage()
    life_frames = _player_bullet_life_frames(spd)

    ti, tx, ty, tz = _pick_autoaim_target(sx, sy, sz, fx, fy)

    if ti != -1:
        dx = tx - sx
        dy = ty - sy
        dz = tz - sz
        d2 = dx*dx + dy*dy + dz*dz
        if d2 < 1.0:
            return
        d = math.sqrt(d2)
        vx = (dx / d) * spd
        vy = (dy / d) * spd
        vz = (dz / d) * spd
    else:
        vx = fx * spd
        vy = fy * spd
        vz = 0.0

    player_bullets.append([sx, sy, sz, vx, vy, vz, life_frames, dmg])
    player_bullet_cd = _player_bullet_cooldown_frames()

def _update_player_bullets_and_hits():
    global player_score

    keep = []
    for b in player_bullets:
        x, y, z, vx, vy, vz, life, dmg = b
        x += vx
        y += vy
        z += vz
        life -= 1

        if life <= 0:
            continue
        if x < WORLD_MIN or x > WORLD_MAX or y < WORLD_MIN or y > WORLD_MAX or z < WORLD_Z_MIN or z > WORLD_Z_MAX:
            continue

        hit = False

        for i, r in enumerate(rocks):
            rx, ry, rz, rad_ = r[0], r[1], r[2], r[3]
            dx = x - rx
            dy = y - ry
            dz = z - rz
            rr = rad_ + PLAYER_BULLET_HIT_R
            if (dx*dx + dy*dy + dz*dz) <= (rr * rr):
                damage_rock(i, dmg)
                hit = True
                break

        if hit:
            continue

        for ei in range(len(enemies)):
            ex, ey, ez, ang, cd, s, ehp = enemies[ei]
            dx = x - ex
            dy = y - ey
            dz = z - ez

            rr = (ENEMY_HIT_R * s) + PLAYER_BULLET_HIT_R
            if (dx*dx + dy*dy + dz*dz) <= (rr * rr):
                enemies[ei][6] -= dmg
                if enemies[ei][6] <= 0:
                    player_score += 25
                    enemies.pop(ei)
                    register_enemy_kill()
                hit = True
                break

        if hit:
            continue

        keep.append([x, y, z, vx, vy, vz, life, dmg])

    player_bullets[:] = keep

def draw_player_bullets():
    glColor3f(0.2, 0.9, 1.0)
    for b in player_bullets:
        x, y, z, vx, vy, vz, life, dmg = b
        glPushMatrix()
        glTranslatef(x, y, z)
        glScalef(PLAYER_BULLET_DRAW_SCALE, PLAYER_BULLET_DRAW_SCALE, PLAYER_BULLET_DRAW_SCALE)
        glutSolidCube(10)
        glPopMatrix()


#Enemy/Alien ship
ENEMY_COUNT_BY_SHIP_LEVEL = {1: 5, 2: 6, 3: 8, 4: 10, 5: 13}

ENEMY_SPAWN_RADIUS_MIN = 900.0
ENEMY_SPAWN_RADIUS_MAX = 1500.0
ENEMY_SPEED = 1
ENEMY_STOP_DIST = 380.0

ENEMY_FIRE_RANGE = 850.0
ENEMY_FIRE_COOLDOWN_FRAMES = 60
ENEMY_BULLET_SPEED = 10.0
ENEMY_BULLET_DAMAGE = 40
ENEMY_BULLET_LIFE_FRAMES = 180

enemies = []
enemy_bullets = []

ENEMY_SCALE_MIN = 0.8
ENEMY_SCALE_MAX = 1.5
ENEMY_HP_MIN = 40
ENEMY_HP_MAX = 80

def _enemy_scale_and_hp():
    s = random.uniform(ENEMY_SCALE_MIN, ENEMY_SCALE_MAX)
    t = (s - ENEMY_SCALE_MIN) / max(0.0001, (ENEMY_SCALE_MAX - ENEMY_SCALE_MIN))
    hp = int(ENEMY_HP_MIN + t * (ENEMY_HP_MAX - ENEMY_HP_MIN))
    return s, hp

def _rand_spawn_near_player():
    ang = random.uniform(0.0, 2.0 * math.pi)
    rad = random.uniform(ENEMY_SPAWN_RADIUS_MIN, ENEMY_SPAWN_RADIUS_MAX)
    z = random.uniform(WORLD_Z_MIN + 80, WORLD_Z_MAX - 80)
    x = player_x + math.cos(ang) * rad
    y = player_y + math.sin(ang) * rad
    x = clamp(x, WORLD_MIN + 120, WORLD_MAX - 120)
    y = clamp(y, WORLD_MIN + 120, WORLD_MAX - 120)
    return x, y, z


def _update_enemy_player_collisions():
    global player_life
    if game_over:
        return

    keep = []
    for e in enemies:
        ex, ey, ez, ang, cd, s, ehp = e
        dx = player_x - ex
        dy = player_y - ey
        dz = player_z - ez

        rr = SHIP_COLLISION_R + (ENEMY_HIT_R * s)
        if (dx*dx + dy*dy + dz*dz) <= (rr * rr):
            player_life = max(0, player_life - int(ehp))
            if player_life <= 0:
                _trigger_game_over()
            continue

        keep.append(e)

    enemies[:] = keep

def _target_enemy_count():
    lvl = clamp(int(ship_level), 1, 5)
    return ENEMY_COUNT_BY_SHIP_LEVEL.get(lvl, 5)

def init_enemies():
    enemies.clear()
    enemy_bullets.clear()
    target = _target_enemy_count()
    for _ in range(target):
        x, y, z = _rand_spawn_near_player()
        s, hp = _enemy_scale_and_hp()
        enemies.append([x, y, z, 0.0, random.randint(0, ENEMY_FIRE_COOLDOWN_FRAMES), s, hp])

def _ensure_enemies_alive():
    target = _target_enemy_count()
    while len(enemies) < target:
        x, y, z = _rand_spawn_near_player()
        s, hp = _enemy_scale_and_hp()
        enemies.append([x, y, z, 0.0, ENEMY_FIRE_COOLDOWN_FRAMES, s, hp])
    while len(enemies) > target:
        enemies.pop()

def _spawn_enemy_bullet(ex, ey, ez):
    dx = player_x - ex
    dy = player_y - ey
    dz = player_z - ez
    d2 = dx*dx + dy*dy + dz*dz
    if d2 < 1.0:
        return
    d = math.sqrt(d2)
    vx = (dx / d) * ENEMY_BULLET_SPEED
    vy = (dy / d) * ENEMY_BULLET_SPEED
    vz = (dz / d) * ENEMY_BULLET_SPEED
    enemy_bullets.append([ex, ey, ez, vx, vy, vz, ENEMY_BULLET_LIFE_FRAMES])

def _update_enemies_and_fire():
    if game_over:
        return

    for e in enemies:
        ex, ey, ez, ang, cd, s, hp = e

        dx = player_x - ex
        dy = player_y - ey
        dz = player_z - ez

        dist3_ = math.sqrt(dx*dx + dy*dy + dz*dz) if (dx*dx + dy*dy + dz*dz) > 0.0001 else 0.0
        dist_xy2 = dx*dx + dy*dy

        if dist_xy2 > 0.001:
            e[3] = math.degrees(math.atan2(dy, dx))

        if dist3_ > ENEMY_STOP_DIST:
            inv = 1.0 / dist3_
            ex += dx * inv * ENEMY_SPEED
            ey += dy * inv * ENEMY_SPEED
            ez += dz * inv * ENEMY_SPEED

            ex = clamp(ex, WORLD_MIN, WORLD_MAX)
            ey = clamp(ey, WORLD_MIN, WORLD_MAX)
            ez = clamp(ez, WORLD_Z_MIN, WORLD_Z_MAX)

            e[0], e[1], e[2] = ex, ey, ez

        if e[4] > 0:
            e[4] -= 1

        if dist3_ <= ENEMY_FIRE_RANGE and e[4] == 0:
            _spawn_enemy_bullet(ex, ey, ez)
            e[4] = ENEMY_FIRE_COOLDOWN_FRAMES

def _update_enemy_bullets_and_hit_player():
    global player_life
    if game_over:
        return

    keep = []
    hit_r = SHIP_COLLISION_R + 10.0

    for b in enemy_bullets:
        x, y, z, vx, vy, vz, life = b
        x += vx
        y += vy
        z += vz
        life -= 1

        if life <= 0:
            continue
        if x < WORLD_MIN or x > WORLD_MAX or y < WORLD_MIN or y > WORLD_MAX or z < WORLD_Z_MIN or z > WORLD_Z_MAX:
            continue

        dx = x - player_x
        dy = y - player_y
        dz = z - player_z
        if (dx*dx + dy*dy + dz*dz) <= (hit_r * hit_r):
            player_life = max(0, player_life - ENEMY_BULLET_DAMAGE)
            if player_life <= 0:
                _trigger_game_over()
            continue

        keep.append([x, y, z, vx, vy, vz, life])

    enemy_bullets[:] = keep

#Objects
rocks = []
black_holes = []
white_holes = []
wormholes = []


#Rocks
ROCK_COUNT = 40
ROCK_DRIFT_MAX = 0.12
ROCK_ROT_SPEED = 0.12

ROCK_SCALE_MIN = 0.6
ROCK_SCALE_MAX = 2.0
ROCK_HP_MIN = 30
ROCK_HP_MAX = 70

rocks_destroyed = 0
ROCK_HIT_COOLDOWN_FRAMES = 30

def _rock_scale_and_hp():
    s = random.uniform(ROCK_SCALE_MIN, ROCK_SCALE_MAX)
    t = (s - ROCK_SCALE_MIN) / max(0.0001, (ROCK_SCALE_MAX - ROCK_SCALE_MIN))
    hp = int(ROCK_HP_MIN + t * (ROCK_HP_MAX - ROCK_HP_MIN))
    return s, hp

def init_rocks():
    rocks.clear()
    player_r = SHIP_COLLISION_R

    for _ in range(ROCK_COUNT):
        x = random.uniform(WORLD_MIN + SPAWN_MARGIN_ROCK, WORLD_MAX - SPAWN_MARGIN_ROCK)
        y = random.uniform(WORLD_MIN + SPAWN_MARGIN_ROCK, WORLD_MAX - SPAWN_MARGIN_ROCK)
        z = random.uniform(WORLD_Z_MIN + 80, WORLD_Z_MAX - 80)

        s, hp = _rock_scale_and_hp()
        rad = player_r * s

        vx = random.uniform(-ROCK_DRIFT_MAX, ROCK_DRIFT_MAX)
        vy = random.uniform(-ROCK_DRIFT_MAX, ROCK_DRIFT_MAX)
        vz = random.uniform(-ROCK_DRIFT_MAX * 0.6, ROCK_DRIFT_MAX * 0.6)

        spin = random.uniform(-ROCK_ROT_SPEED, ROCK_ROT_SPEED)
        ang = random.uniform(0, 360)

        hit_cd = 0
        rocks.append([x, y, z, rad, vx, vy, vz, ang, spin, hp, hit_cd, s])

def damage_rock(rock_index, dmg=1):
    global rocks_destroyed

    if rock_index < 0 or rock_index >= len(rocks):
        return

    r = rocks[rock_index]
    r[9] -= dmg

    if r[9] <= 0:
        rocks_destroyed += 1

        x = random.uniform(WORLD_MIN + SPAWN_MARGIN_ROCK, WORLD_MAX - SPAWN_MARGIN_ROCK)
        y = random.uniform(WORLD_MIN + SPAWN_MARGIN_ROCK, WORLD_MAX - SPAWN_MARGIN_ROCK)
        z = random.uniform(WORLD_Z_MIN + 80, WORLD_Z_MAX - 80)

        s, hp = _rock_scale_and_hp()
        rad = SHIP_COLLISION_R * s

        vx = random.uniform(-ROCK_DRIFT_MAX, ROCK_DRIFT_MAX)
        vy = random.uniform(-ROCK_DRIFT_MAX, ROCK_DRIFT_MAX)
        vz = random.uniform(-ROCK_DRIFT_MAX * 0.6, ROCK_DRIFT_MAX * 0.6)

        spin = random.uniform(-ROCK_ROT_SPEED, ROCK_ROT_SPEED)
        ang = random.uniform(0, 360)

        r[0], r[1], r[2] = x, y, z
        r[3] = rad
        r[4], r[5], r[6] = vx, vy, vz
        r[7], r[8] = ang, spin
        r[9] = hp
        r[10] = 0
        r[11] = s

def _resolve_ship_rock_collision(r):
    global player_x, player_y, player_z
    global vel_x, vel_y, vel_z

    dx = player_x - r[0]
    dy = player_y - r[1]
    dz = player_z - r[2]

    dist2 = dx*dx + dy*dy + dz*dz
    min_dist = r[3] + SHIP_COLLISION_R

    if dist2 <= 0.000001:
        dx, dy, dz = 1.0, 0.0, 0.0
        dist2 = 1.0

    if dist2 < (min_dist * min_dist):
        dist = math.sqrt(dist2)
        nx = dx / dist
        ny = dy / dist
        nz = dz / dist

        penetration = (min_dist - dist) + 0.5
        player_x += nx * penetration
        player_y += ny * penetration
        player_z += nz * penetration

        vdot = vel_x*nx + vel_y*ny + vel_z*nz
        if vdot < 0.0:
            vel_x -= vdot * nx
            vel_y -= vdot * ny
            vel_z -= vdot * nz

#Holes
BLACK_HOLE_COUNT = 5
WHITE_HOLE_COUNT = 5
WORMHOLE_COUNT = 5

BLACK_HOLE_MIN_R = 20
BLACK_HOLE_MAX_R = 45
BH_PARTICLES = 80

WHITE_HOLE_MIN_R = 22
WHITE_HOLE_MAX_R = 50
WH_PARTICLES = 70

WORMHOLE_MIN_R = 28
WORMHOLE_MAX_R = 55
WORM_RINGS = 14
WORM_SPARKS = 120

FPS_ASSUMED = 60.0
HOLE_SOFTENING = 220.0
BH_PULL_STRENGTH = 9000.0
WH_PUSH_STRENGTH = 9000.0

HOLE_EFFECT_RANGE_MULT = 15.00
MAX_HOLE_ACCEL = 55.0

BH_DAMAGE_ZONE_MULT = 3.0
BH_DMG_MIN_PER_SEC = 80.0
BH_DMG_MAX_PER_SEC = 150.0

HOLE_COLLISION_BUFFER = 260.0
HOLE_INFLUENCE_BUFFER = 320.0
PLAYER_SAFE_RADIUS = 650.0
MAX_SPAWN_TRIES = 25000


#Wormhole teleport
WORMHOLE_TELEPORT_COOLDOWN_SEC = 5.0
FPS_WORM = 60.0
WORMHOLE_TELEPORT_COOLDOWN_FRAMES = int(WORMHOLE_TELEPORT_COOLDOWN_SEC * FPS_WORM)
wormhole_tp_cd = 0

SPAWN_MARGIN_ROCK = 150
SPAWN_MARGIN_BH = 350
SPAWN_MARGIN_WH = 350
SPAWN_MARGIN_WORM = 350

def init_black_holes():
    black_holes.clear()
    for _ in range(BLACK_HOLE_COUNT):
        core_r = random.uniform(BLACK_HOLE_MIN_R, BLACK_HOLE_MAX_R)
        disk_tilt = random.uniform(25.0, 60.0)

        new_r_eff = core_r * 3.2
        new_r_inf = core_r * HOLE_EFFECT_RANGE_MULT

        x, y, z = _find_non_overlapping_position(SPAWN_MARGIN_BH, new_r_eff, new_r_inf)

        debris = []
        for _p in range(BH_PARTICLES):
            ang = random.uniform(0, 2 * math.pi)
            rad = random.uniform(core_r * 1.6, core_r * 3.0)
            zoff = random.uniform(-4.0, 4.0)
            size = random.uniform(1.2, 3.0)
            debris.append([ang, rad, zoff, size])

        black_holes.append({"pos": [x, y, z], "core_r": core_r, "disk_tilt": disk_tilt, "debris": debris})

def init_white_holes():
    white_holes.clear()
    for _ in range(WHITE_HOLE_COUNT):
        core_r = random.uniform(WHITE_HOLE_MIN_R, WHITE_HOLE_MAX_R)
        disk_tilt = random.uniform(25.0, 60.0)

        new_r_eff = core_r * 3.2
        new_r_inf = core_r * HOLE_EFFECT_RANGE_MULT

        x, y, z = _find_non_overlapping_position(SPAWN_MARGIN_WH, new_r_eff, new_r_inf)

        debris = []
        for _p in range(WH_PARTICLES):
            ang = random.uniform(0, 2 * math.pi)
            rad = random.uniform(core_r * 1.6, core_r * 3.0)
            zoff = random.uniform(-4.0, 4.0)
            size = random.uniform(1.2, 3.0)
            debris.append([ang, rad, zoff, size])

        white_holes.append({"pos": [x, y, z], "core_r": core_r, "disk_tilt": disk_tilt, "debris": debris})

def init_wormholes():
    wormholes.clear()
    for _ in range(WORMHOLE_COUNT):
        core_r = random.uniform(WORMHOLE_MIN_R, WORMHOLE_MAX_R)
        tilt = random.uniform(20.0, 70.0)
        twist = random.uniform(0.6, 1.6)

        new_r_eff = core_r * 3.1
        new_r_inf = core_r * 6.0

        x, y, z = _find_non_overlapping_position(SPAWN_MARGIN_WORM, new_r_eff, new_r_inf)

        sparks = []
        for _p in range(WORM_SPARKS):
            ang = random.uniform(0, 2 * math.pi)
            rad = random.uniform(core_r * 1.2, core_r * 3.2)
            zoff = random.uniform(-6.0, 6.0)
            size = random.uniform(1.0, 3.2)
            sparks.append([ang, rad, zoff, size])

        wormholes.append({"pos": [x, y, z], "core_r": core_r, "tilt": tilt, "twist": twist, "sparks": sparks})

def _update_wormhole_teleport():
    global player_x, player_y, player_z
    global wormhole_tp_cd

    if wormhole_tp_cd > 0:
        return
    if len(wormholes) < 2:
        return

    for i, w in enumerate(wormholes):
        wx, wy, wz = w["pos"]
        wr = w["core_r"]

        dx = player_x - wx
        dy = player_y - wy
        dz = player_z - wz

        rr = wr + SHIP_COLLISION_R
        if (dx*dx + dy*dy + dz*dz) <= (rr * rr):
            choices = [j for j in range(len(wormholes)) if j != i]
            j = random.choice(choices)
            dest = wormholes[j]
            tx, ty, tz = dest["pos"]
            tr = dest["core_r"]

            rad = math.radians(player_angle)
            fx, fy = math.cos(rad), math.sin(rad)

            push_out = tr + SHIP_COLLISION_R + 25.0
            player_x = tx + fx * push_out
            player_y = ty + fy * push_out
            player_z = tz

            player_x = clamp(player_x, WORLD_MIN, WORLD_MAX)
            player_y = clamp(player_y, WORLD_MIN, WORLD_MAX)
            player_z = clamp(player_z, WORLD_Z_MIN, WORLD_Z_MAX)

            wormhole_tp_cd = WORMHOLE_TELEPORT_COOLDOWN_FRAMES
            return

def _collect_all_hole_centers_and_radii():
    items = []
    for bh in black_holes:
        x, y, z = bh["pos"]
        core = float(bh["core_r"])
        r_eff = core * 3.2
        r_inf = core * HOLE_EFFECT_RANGE_MULT
        items.append((x, y, z, r_eff, r_inf))

    for wh in white_holes:
        x, y, z = wh["pos"]
        core = float(wh["core_r"])
        r_eff = core * 3.2
        r_inf = core * HOLE_EFFECT_RANGE_MULT
        items.append((x, y, z, r_eff, r_inf))

    for w in wormholes:
        x, y, z = w["pos"]
        core = float(w["core_r"])
        r_eff = core * 3.1
        r_inf = core * 6.0
        items.append((x, y, z, r_eff, r_inf))

    return items

def _find_non_overlapping_position(spawn_margin, new_r_eff, new_r_inf):
    existing = _collect_all_hole_centers_and_radii()

    lo = WORLD_MIN + spawn_margin
    hi = WORLD_MAX - spawn_margin
    zlo = WORLD_Z_MIN + spawn_margin * 0.25
    zhi = WORLD_Z_MAX - spawn_margin * 0.25

    for _ in range(MAX_SPAWN_TRIES):
        x = random.uniform(lo, hi)
        y = random.uniform(lo, hi)
        z = random.uniform(zlo, zhi)

        if dist3_2((x, y, z), (player_x, player_y, player_z)) < PLAYER_SAFE_RADIUS * PLAYER_SAFE_RADIUS:
            continue

        ok = True
        for ex, ey, ez, er_eff, er_inf in existing:
            min_sep_visual = (er_eff + new_r_eff + HOLE_COLLISION_BUFFER)

            min_sep_infl = (er_inf + new_r_inf + HOLE_INFLUENCE_BUFFER)

            min_sep = max(min_sep_visual, min_sep_infl)

            if dist3_2((x, y, z), (ex, ey, ez)) < (min_sep * min_sep):
                ok = False
                break

        if ok:
            return x, y, z

    return random.uniform(lo, hi), random.uniform(lo, hi), random.uniform(zlo, zhi)

#Black/white hole Physics
def _hole_accel_at_point(px, py, pz):
    best_kind = None
    best_hole = None
    best_ax = best_ay = best_az = 0.0
    best_mag2 = 0.0
    best_dist_raw = 1e9

    #Black holes pull
    for bh in black_holes:
        bx, by, bz = bh["pos"]
        core = float(bh["core_r"])

        dx = bx - px
        dy = by - py
        dz = bz - pz

        d2_raw = dx*dx + dy*dy + dz*dz
        d_raw = math.sqrt(d2_raw) if d2_raw > 1e-9 else 0.0

        hole_effect_range = core * HOLE_EFFECT_RANGE_MULT
        if d_raw > hole_effect_range:
            continue

        d2 = d2_raw + (HOLE_SOFTENING * HOLE_SOFTENING)
        d = math.sqrt(d2)

        a = (BH_PULL_STRENGTH * (core * core)) / d2
        if a > MAX_HOLE_ACCEL:
            a = MAX_HOLE_ACCEL

        ax = (dx / d) * a
        ay = (dy / d) * a
        az = (dz / d) * a

        mag2 = ax*ax + ay*ay + az*az
        if mag2 > best_mag2:
            best_mag2 = mag2
            best_kind = "BH"
            best_hole = bh
            best_ax, best_ay, best_az = ax, ay, az
            best_dist_raw = d_raw

    #White holes repel
    for wh in white_holes:
        wx, wy, wz = wh["pos"]
        core = float(wh["core_r"])

        dx = px - wx
        dy = py - wy
        dz = pz - wz

        d2_raw = dx*dx + dy*dy + dz*dz
        d_raw = math.sqrt(d2_raw) if d2_raw > 1e-9 else 0.0

        hole_effect_range = core * HOLE_EFFECT_RANGE_MULT
        if d_raw > hole_effect_range:
            continue

        d2 = d2_raw + (HOLE_SOFTENING * HOLE_SOFTENING)
        d = math.sqrt(d2)

        a = (WH_PUSH_STRENGTH * (core * core)) / d2
        if a > MAX_HOLE_ACCEL:
            a = MAX_HOLE_ACCEL

        ax = (dx / d) * a
        ay = (dy / d) * a
        az = (dz / d) * a

        mag2 = ax*ax + ay*ay + az*az
        if mag2 > best_mag2:
            best_mag2 = mag2
            best_kind = "WH"
            best_hole = wh
            best_ax, best_ay, best_az = ax, ay, az
            best_dist_raw = d_raw

    if best_kind is None:
        return 0.0, 0.0, 0.0, None, None, 0.0
    return best_ax, best_ay, best_az, best_kind, best_hole, best_dist_raw

def _apply_black_hole_damage_if_needed(px, py, pz):
    ax, ay, az, kind, hole, dist_raw = _hole_accel_at_point(px, py, pz)
    if kind != "BH" or hole is None:
        return 0

    core = float(hole["core_r"])
    zone_r = core * BH_DAMAGE_ZONE_MULT
    if dist_raw > zone_r:
        return 0

    t = 1.0 - (dist_raw / max(1e-6, zone_r))
    t = clamp(t, 0.0, 1.0)

    dmg_per_sec = BH_DMG_MIN_PER_SEC + t * (BH_DMG_MAX_PER_SEC - BH_DMG_MIN_PER_SEC)
    dmg_per_frame = dmg_per_sec / float(FPS_ASSUMED)
    return max(1, int(round(dmg_per_frame)))


def _apply_hole_physics():
    global vel_x, vel_y, vel_z
    global player_life

    if game_over:
        return

    dt = 1.0 / float(FPS_ASSUMED)

    #Player acceleration
    ax, ay, az, kind, hole, dist_raw = _hole_accel_at_point(player_x, player_y, player_z)
    vel_x += ax * dt
    vel_y += ay * dt
    vel_z += az * dt

    #Player Black hole damage
    dmg = _apply_black_hole_damage_if_needed(player_x, player_y, player_z)
    if dmg > 0:
        player_life = max(0, player_life - dmg)
        if player_life <= 0:
            _trigger_game_over()

    #Player bullets
    for b in player_bullets:
        bx, by, bz = b[0], b[1], b[2]
        ax, ay, az, kind, hole, dist_raw = _hole_accel_at_point(bx, by, bz)
        b[3] += ax * dt
        b[4] += ay * dt
        b[5] += az * dt

    #Enemy bullets
    for b in enemy_bullets:
        bx, by, bz = b[0], b[1], b[2]
        ax, ay, az, kind, hole, dist_raw = _hole_accel_at_point(bx, by, bz)
        b[3] += ax * dt
        b[4] += ay * dt
        b[5] += az * dt

    keep_enemies = []
    for e in enemies:
        ex, ey, ez = e[0], e[1], e[2]

        ax, ay, az, kind, hole, dist_raw = _hole_accel_at_point(ex, ey, ez)
        ex = clamp(ex + ax * dt * 18.0, WORLD_MIN, WORLD_MAX)
        ey = clamp(ey + ay * dt * 18.0, WORLD_MIN, WORLD_MAX)
        ez = clamp(ez + az * dt * 18.0, WORLD_Z_MIN, WORLD_Z_MAX)
        e[0], e[1], e[2] = ex, ey, ez

        dmg = _apply_black_hole_damage_if_needed(ex, ey, ez)
        if dmg > 0:
            e[6] -= dmg
            if e[6] <= 0:
                register_enemy_kill()  # upgrades only
                continue

        keep_enemies.append(e)

    enemies[:] = keep_enemies


#Scoreboard
def _record_score_on_game_over():
    global last_round_score, top5_scores, _scoreboard_locked
    if _scoreboard_locked:
        return
    _scoreboard_locked = True

    last_round_score = int(player_score)
    top5_scores.append(last_round_score)
    top5_scores.sort(reverse=True)
    top5_scores[:] = top5_scores[:5]


# Draw environment
def draw_rocks():
    quad = gluNewQuadric()
    for r in rocks:
        x, y, z, rad_, vx, vy, vz, ang, spin, hp, hit_cd, s = r
        t = hp / float(ROCK_HP_MAX)
        glColor3f(0.25 + 0.45 * t, 0.25 + 0.45 * t, 0.25 + 0.45 * t)

        glPushMatrix()
        glTranslatef(x, y, z)
        glRotatef(ang, 0, 0, 1)
        gluSphere(quad, rad_, 12, 12)
        glPopMatrix()

def draw_black_holes():
    for bh in black_holes:
        x, y, z = bh["pos"]
        core_r = bh["core_r"]
        tilt = bh["disk_tilt"]

        glPushMatrix()
        glTranslatef(x, y, z)
        glPushMatrix()
        glRotatef(tilt, 1, 0, 0)

        disk_h = 1.2
        layers = 10
        for i in range(layers):
            t = i / (layers - 1)
            r = core_r * (3.2 - 1.6 * t)

            if t < 0.5:
                rr = 0.7 + 0.6 * t
                gg = 0.1 + 0.5 * t
                bb = 0.05
            else:
                tt = (t - 0.5) / 0.5
                rr = 1.0
                gg = 0.6 + 0.4 * tt
                bb = 0.05 + 0.2 * tt

            glColor3f(rr, gg, bb)
            glPushMatrix()
            glTranslatef(0, 0, -0.5 + i * 0.08)
            _draw_flat_disk(r, disk_h, slices=28)
            glPopMatrix()

        glColor3f(1.0, 0.95, 0.8)
        glPushMatrix()
        glTranslatef(0, 0, 0.15)
        _draw_flat_disk(core_r * 1.55, 0.8, slices=32)
        glPopMatrix()

        glColor3f(1.0, 0.7, 0.3)
        for ang, rad_, zoff, size in bh["debris"]:
            glPushMatrix()
            glTranslatef(math.cos(ang) * rad_, math.sin(ang) * rad_, zoff)
            glScalef(size * 0.12, size * 0.12, size * 0.12)
            glutSolidCube(10)
            glPopMatrix()

        glPopMatrix()
        glColor3f(0.02, 0.02, 0.02)
        gluSphere(gluNewQuadric(), core_r, 24, 24)
        glPopMatrix()

def draw_white_holes():
    for wh in white_holes:
        x, y, z = wh["pos"]
        core_r = wh["core_r"]
        tilt = wh["disk_tilt"]

        glPushMatrix()
        glTranslatef(x, y, z)
        glPushMatrix()
        glRotatef(tilt, 1, 0, 0)

        disk_h = 1.2
        layers = 10
        for i in range(layers):
            t = i / (layers - 1)
            r = core_r * (3.2 - 1.6 * t)
            base = 0.75 + 0.25 * t
            glColor3f(base, base, base)

            glPushMatrix()
            glTranslatef(0, 0, -0.5 + i * 0.08)
            _draw_flat_disk(r, disk_h, slices=28)
            glPopMatrix()

        glColor3f(1.0, 1.0, 1.0)
        glPushMatrix()
        glTranslatef(0, 0, 0.15)
        _draw_flat_disk(core_r * 1.55, 0.8, slices=32)
        glPopMatrix()

        glColor3f(0.95, 0.95, 1.0)
        for ang, rad_, zoff, size in wh["debris"]:
            glPushMatrix()
            glTranslatef(math.cos(ang) * rad_, math.sin(ang) * rad_, zoff)
            glScalef(size * 0.12, size * 0.12, size * 0.12)
            glutSolidCube(10)
            glPopMatrix()

        glPopMatrix()
        glColor3f(1.0, 1.0, 1.0)
        gluSphere(gluNewQuadric(), core_r, 24, 24)
        glPopMatrix()

def draw_wormholes():
    for w in wormholes:
        x, y, z = w["pos"]
        core_r = w["core_r"]
        tilt = w["tilt"]
        twist = w["twist"]

        glPushMatrix()
        glTranslatef(x, y, z)
        glPushMatrix()
        glRotatef(tilt, 1, 0, 0)

        disk_h = 1.0
        for i in range(WORM_RINGS):
            t = i / (WORM_RINGS - 1)
            r = core_r * (3.1 - 1.7 * t)

            blue = 0.75 + 0.25 * (1 - t)
            green = 0.55 + 0.30 * (1 - t)
            red = 0.25 + 0.20 * (1 - t)
            glColor3f(red, green, blue)

            glPushMatrix()
            glRotatef((i * 18.0) * twist, 0, 0, 1)
            glTranslatef(0, 0, -0.8 + i * 0.12)
            _draw_flat_disk(r, disk_h, slices=30)
            glPopMatrix()

        glColor3f(0.8, 0.95, 1.0)
        glPushMatrix()
        glTranslatef(0, 0, 0.2)
        _draw_flat_disk(core_r * 1.35, 0.8, slices=34)
        glPopMatrix()

        glColor3f(0.7, 0.9, 1.0)
        for ang, rad_, zoff, size in w["sparks"]:
            ang2 = ang + (rad_ / (core_r * 3.2)) * 3.0 * twist
            glPushMatrix()
            glTranslatef(math.cos(ang2) * rad_, math.sin(ang2) * rad_, zoff)
            glScalef(size * 0.10, size * 0.10, size * 0.10)
            glutSolidCube(10)
            glPopMatrix()

        glPopMatrix()
        glColor3f(0.05, 0.05, 0.08)
        gluSphere(gluNewQuadric(), core_r * 0.55, 20, 20)
        glPopMatrix()

# Enemy ship
def draw_enemy_ship_model():
    quad = gluNewQuadric()

    BLACK = (0.05, 0.05, 0.06)
    CYAN  = (0.10, 0.95, 0.90)

    glColor3f(*BLACK)
    glPushMatrix()
    glScalef(1.2, 0.7, 0.5)
    glutSolidCube(30)
    glPopMatrix()

    glColor3f(*BLACK)
    glPushMatrix()
    glTranslatef(18, 0, 0)
    glRotatef(90, 0, 1, 0)
    gluCylinder(quad, 6.0, 2.5, 14.0, 14, 2)
    glPopMatrix()

    glColor3f(*CYAN)
    glPushMatrix()
    glTranslatef(30, 0, 0)
    gluSphere(gluNewQuadric(), 2.4, 12, 12)
    glPopMatrix()

    def wing(side):
        glColor3f(*BLACK)
        glPushMatrix()
        glTranslatef(0, side * 16.0, -2.0)
        glRotatef(15 * side, 0, 0, 1)
        glScalef(1.0, 2.0, 0.25)
        glutSolidCube(30)
        glPopMatrix()

        glColor3f(*CYAN)
        glPushMatrix()
        glTranslatef(0, side * 16.0, 6.5)
        glRotatef(15 * side, 0, 0, 1)
        glScalef(1.05, 2.05, 0.06)
        glutSolidCube(30)
        glPopMatrix()

        glColor3f(*CYAN)
        glPushMatrix()
        glTranslatef(-10, side * 24.0, -1.0)
        gluSphere(gluNewQuadric(), 2.0, 12, 12)
        glPopMatrix()

    wing(+1)
    wing(-1)

    glColor3f(*CYAN)
    glPushMatrix()
    glTranslatef(0, 0, 10.0)
    glScalef(0.9, 0.25, 0.08)
    glutSolidCube(30)
    glPopMatrix()

def draw_enemies():
    for e in enemies:
        ex, ey, ez, ang, cd, s, hp = e
        glPushMatrix()
        glTranslatef(ex, ey, ez)
        glRotatef(ang, 0, 0, 1)
        render_scale = SHIP_SCALE * s
        glScalef(render_scale, render_scale, render_scale)
        draw_enemy_ship_model()
        glPopMatrix()

def draw_enemy_bullets():
    glColor3f(1.0, 0.3, 0.2)
    for b in enemy_bullets:
        x, y, z, vx, vy, vz, life = b
        glPushMatrix()
        glTranslatef(x, y, z)
        glScalef(0.25, 0.25, 0.25)
        glutSolidCube(10)
        glPopMatrix()

def draw_ship_third_person():
    glPushMatrix()
    glTranslatef(player_x, player_y, player_z)
    glRotatef(player_angle, 0, 0, 1)
    glScalef(SHIP_SCALE, SHIP_SCALE, SHIP_SCALE)

    quad = gluNewQuadric()

    RED      = (0.78, 0.12, 0.12)
    RED_DARK = (0.55, 0.08, 0.08)
    DARK     = (0.12, 0.12, 0.14)
    MID      = (0.20, 0.20, 0.24)
    GLASS    = (0.95, 0.45, 0.10)
    GLOW     = (0.25, 0.85, 0.95)

    glColor3f(*DARK)
    glPushMatrix()
    glTranslatef(10, 0, 0)
    glScalef(8.0, 1.2, 1.2)
    glutSolidCube(18)
    glPopMatrix()

    glColor3f(*RED_DARK)
    glPushMatrix()
    glTranslatef(10, 0, 7.0)
    glScalef(7.4, 1.05, 0.35)
    glutSolidCube(18)
    glPopMatrix()

    glColor3f(*RED)
    glPushMatrix()
    glTranslatef(10, 10.0, 1.5)
    glScalef(7.2, 0.35, 0.35)
    glutSolidCube(18)
    glPopMatrix()

    glPushMatrix()
    glTranslatef(10, -10.0, 1.5)
    glScalef(7.2, 0.35, 0.35)
    glutSolidCube(18)
    glPopMatrix()

    glColor3f(*RED)
    glPushMatrix()
    glTranslatef(92, 0, 0)
    glRotatef(90, 0, 1, 0)
    gluCylinder(quad, 9.0, 2.0, 32.0, 18, 2)
    glPopMatrix()

    glColor3f(*MID)
    glPushMatrix()
    glTranslatef(125, 0, 0)
    gluSphere(gluNewQuadric(), 3.0, 14, 14)
    glPopMatrix()

    glColor3f(*GLASS)
    glPushMatrix()
    glTranslatef(30, 0, 10.5)
    glScalef(1.6, 1.1, 0.9)
    gluSphere(gluNewQuadric(), 8.0, 16, 16)
    glPopMatrix()

    glColor3f(*RED_DARK)
    glPushMatrix()
    glTranslatef(28, 0, 8.2)
    glScalef(2.6, 1.2, 0.35)
    glutSolidCube(10)
    glPopMatrix()

    def wing(side):
        glColor3f(*RED)
        glPushMatrix()
        glTranslatef(25, side * 28.0, -1.0)
        glRotatef(18 * side, 0, 0, 1)
        glScalef(2.8, 5.6, 0.25)
        glutSolidCube(10)
        glPopMatrix()

    wing(+1)
    wing(-1)

    def engine_pod(side):
        glColor3f(*MID)
        glPushMatrix()
        glTranslatef(-20, side * 22.0, -4.0)
        glScalef(2.2, 2.0, 1.2)
        glutSolidCube(18)
        glPopMatrix()

        glColor3f(*DARK)
        glPushMatrix()
        glTranslatef(-40, side * 22.0, -4.0)
        glRotatef(90, 0, 1, 0)
        gluCylinder(quad, 5.0, 5.0, 18.0, 14, 2)
        glPopMatrix()

        glColor3f(*GLOW)
        glPushMatrix()
        glTranslatef(-48, side * 22.0, -4.0)
        gluSphere(gluNewQuadric(), 3.0, 12, 12)
        glPopMatrix()

    engine_pod(+1)
    engine_pod(-1)

    glColor3f(*RED)
    glPushMatrix()
    glTranslatef(-35, 10.0, 16.0)
    glRotatef(10, 1, 0, 0)
    glScalef(0.35, 1.2, 2.6)
    glutSolidCube(16)
    glPopMatrix()

    glPushMatrix()
    glTranslatef(-35, -10.0, 16.0)
    glRotatef(-10, 1, 0, 0)
    glScalef(0.35, 1.2, 2.6)
    glutSolidCube(16)
    glPopMatrix()

    glColor3f(*DARK)
    glPushMatrix()
    glTranslatef(8, 0, -10.0)
    glScalef(5.8, 0.55, 0.55)
    glutSolidCube(18)
    glPopMatrix()

    glPopMatrix()

def draw_first_person_helm_and_hands():
    glClear(GL_DEPTH_BUFFER_BIT)
    glDisable(GL_DEPTH_TEST)

    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()

    glTranslatef(0.0, -5.5, -18.0)

    glColor3f(0.18, 0.18, 0.18)
    glPushMatrix()
    glScalef(4.2, 1.7, 0.9)
    glutSolidCube(5)
    glPopMatrix()

    glColor3f(0.55, 0.10, 0.10)
    glPushMatrix()
    glTranslatef(0, 0.0, 2.8)
    glScalef(3.8, 1.2, 0.25)
    glutSolidCube(5)
    glPopMatrix()

    glColor3f(0.12, 0.12, 0.14)
    glPushMatrix()
    glTranslatef(0.0, -1.2, 0.6)
    glScalef(1.1, 1.4, 0.9)
    glutSolidCube(5)
    glPopMatrix()

    glColor3f(0.35, 0.35, 0.35)
    glPushMatrix()
    glTranslatef(0.0, -2.8, -0.2)
    glRotatef(90, 1, 0, 0)
    gluCylinder(gluNewQuadric(), 0.55, 0.40, 3.6, 14, 2)
    glPopMatrix()

    glColor3f(0.20, 0.20, 0.20)
    glPushMatrix()
    glTranslatef(0.0, -2.8, -0.2)
    gluSphere(gluNewQuadric(), 0.85, 14, 14)
    glPopMatrix()

    glColor3f(0.80, 0.62, 0.42)
    glPushMatrix()
    glTranslatef(-4.2, -2.6, -1.0)
    glScalef(1.6, 0.9, 1.0)
    glutSolidCube(3)
    glPopMatrix()

    glPushMatrix()
    glTranslatef(4.2, -2.6, -1.0)
    glScalef(1.6, 0.9, 1.0)
    glutSolidCube(3)
    glPopMatrix()

    glPopMatrix()
    glEnable(GL_DEPTH_TEST)

# Helpers
def clamp(v, lo, hi):
    return max(lo, min(hi, v))

def dist3_2(a, b):
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    dz = a[2] - b[2]
    return dx*dx + dy*dy + dz*dz

def _draw_flat_disk(radius, height, slices=24):
    quad = gluNewQuadric()
    gluCylinder(quad, radius, radius, height, slices, 1)

#Camera
def setupCamera():
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    aspect = WIN_W / max(1.0, float(WIN_H))
    gluPerspective(fovY, aspect, 0.1, 8000)

    glMatrixMode(GL_MODELVIEW)
    glLoadIdentity()

    rad = math.radians(player_angle)
    fx, fy = math.cos(rad), math.sin(rad)

    if not first_person:
        cam_dist = 320.0
        cam_up = 220.0
        cam_x = player_x - fx * cam_dist
        cam_y = player_y - fy * cam_dist
        cam_z = player_z + cam_up
        gluLookAt(cam_x, cam_y, cam_z, player_x, player_y, player_z, 0, 0, 1)
    else:
        gluLookAt(
            player_x + fx * 20,
            player_y + fy * 20,
            player_z + 60,
            player_x + fx * 300,
            player_y + fy * 300,
            player_z + 60,
            0, 0, 1
        )


#HUD Helpers
WIN_W, WIN_H = 1000, 800

def set_ship_level(new_level):
    global ship_level, player_max_hp, player_life
    ship_level = clamp(int(new_level), 1, 5)
    player_max_hp = SHIP_STATS_BY_LEVEL[ship_level]["hp"]
    player_life = player_max_hp

def _ship_speed_mult():
    return SHIP_STATS_BY_LEVEL[clamp(int(ship_level), 1, 5)]["speed_mult"]

def _ship_thrust():
    return SHIP_STATS_BY_LEVEL[clamp(int(ship_level), 1, 5)]["thrust"]

def _begin_2d_overlay():
    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    gluOrtho2D(0, WIN_W, 0, WIN_H)

    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()
    glDisable(GL_DEPTH_TEST)

def _end_2d_overlay():
    glEnable(GL_DEPTH_TEST)
    glMatrixMode(GL_MODELVIEW)
    glPopMatrix()
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)

def draw_text(x, y, text, font=GLUT_BITMAP_HELVETICA_18):
    glRasterPos2f(x, y)
    for ch in text:
        glutBitmapCharacter(font, ord(ch))

def text_width(text, font=GLUT_BITMAP_HELVETICA_18):
    return sum(glutBitmapWidth(font, ord(ch)) for ch in text)

def draw_hud():
    _begin_2d_overlay()
    glColor3f(1.0, 1.0, 1.0)

    left_x = 12
    top_y = WIN_H - 28
    line = 22

    draw_text(left_x, top_y,           f"Player Life: {player_life}")
    draw_text(left_x, top_y - line,    f"Player Score: {player_score}")
    draw_text(left_x, top_y - 2*line,  f"Ship Level: {ship_level}")
    draw_text(left_x, top_y - 3*line,  f"Gun Level: {gun_level}")

    controls = [
        "How to Navigate:",
        "W = Forward thrust",
        "S = Backward thrust",
        "A = Rotate Left",
        "D = Rotate Right",
        "Q = Up  |  E = Down",
        "SPACE / Left Click = Fire",
        "Right Click / V = POV",
        "R = Restart"
    ]

    right_pad = 12
    for i, s in enumerate(controls):
        w = text_width(s)
        draw_text(WIN_W - right_pad - w, top_y - i*line, s)

    _end_2d_overlay()

    if game_over:
        _begin_2d_overlay()
        glColor3f(0.2, 0.6, 1.0)

        mid_x = WIN_W * 0.5
        start_y = WIN_H * 0.5 + 120
        line2 = 26

        title = "GAME OVER"
        w = text_width(title, GLUT_BITMAP_HELVETICA_18)
        draw_text(int(mid_x - w * 0.5), int(start_y), title, GLUT_BITMAP_HELVETICA_18)

        s1 = f"Last Round Score: {last_round_score}"
        w = text_width(s1, GLUT_BITMAP_HELVETICA_18)
        draw_text(int(mid_x - w * 0.5), int(start_y - line2), s1, GLUT_BITMAP_HELVETICA_18)

        s2 = "Top 5 Scores"
        w = text_width(s2, GLUT_BITMAP_HELVETICA_18)
        draw_text(int(mid_x - w * 0.5), int(start_y - 2*line2), s2, GLUT_BITMAP_HELVETICA_18)

        for i in range(5):
            val = top5_scores[i] if i < len(top5_scores) else 0
            row = f"{i+1}. {val}"
            w = text_width(row, GLUT_BITMAP_HELVETICA_18)
            draw_text(int(mid_x - w * 0.5), int(start_y - (3+i)*line2), row, GLUT_BITMAP_HELVETICA_18)

        hint = "Press R to Restart"
        w = text_width(hint, GLUT_BITMAP_HELVETICA_18)
        draw_text(int(mid_x - w * 0.5), int(start_y - 9*line2), hint, GLUT_BITMAP_HELVETICA_18)

        _end_2d_overlay()


#Display
def showScreen():
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    glLoadIdentity()
    glViewport(0, 0, WIN_W, WIN_H)

    setupCamera()

    draw_black_holes()
    draw_white_holes()
    draw_wormholes()
    draw_rocks()
    draw_enemies()
    draw_enemy_bullets()
    draw_player_bullets()

    if not first_person:
        draw_ship_third_person()
    else:
        draw_first_person_helm_and_hands()

    draw_hud()
    glutSwapBuffers()

def idle():
    global player_x, player_y, player_z
    global vel_x, vel_y, vel_z, player_angle
    global player_life
    global player_bullet_cd
    global wormhole_tp_cd

    if wormhole_tp_cd > 0:
        wormhole_tp_cd -= 1

    if game_over:
        vel_x = vel_y = vel_z = 0.0
        glutPostRedisplay()
        return

    if player_bullet_cd > 0:
        player_bullet_cd -= 1

    thrust = _ship_thrust()
    sp_mult = _ship_speed_mult()

    accel_xy = ACCELERATION * thrust
    accel_z  = ACCELERATION_Z * thrust

    if not controls_disabled:
        if keys['a']:
            player_angle += rot_step
        if keys['d']:
            player_angle -= rot_step

        rad = math.radians(player_angle)
        fx, fy = math.cos(rad), math.sin(rad)

        if keys['w']:
            vel_x += fx * accel_xy
            vel_y += fy * accel_xy
        if keys['s']:
            vel_x -= fx * accel_xy
            vel_y -= fy * accel_xy

        if keys['q']:
            vel_z += accel_z
        if keys['e']:
            vel_z -= accel_z

    max_xy = MAX_SPEED * sp_mult
    speed_xy = math.sqrt(vel_x**2 + vel_y**2)
    if speed_xy > max_xy:
        vel_x *= max_xy / speed_xy
        vel_y *= max_xy / speed_xy

    vel_z = clamp(vel_z, -(MAX_SPEED_Z * sp_mult), (MAX_SPEED_Z * sp_mult))

    player_x += vel_x
    player_y += vel_y
    player_z += vel_z

    vel_x *= DRAG
    vel_y *= DRAG
    vel_z *= DRAG_Z

    player_x = clamp(player_x, WORLD_MIN, WORLD_MAX)
    player_y = clamp(player_y, WORLD_MIN, WORLD_MAX)
    player_z = clamp(player_z, WORLD_Z_MIN, WORLD_Z_MAX)

    _apply_hole_physics()
    _update_wormhole_teleport()

    #rocks
    for r in rocks:
        r[0] += r[4]
        r[1] += r[5]
        r[2] += r[6]
        r[7] = (r[7] + r[8]) % 360.0

        r[4] *= 0.999
        r[5] *= 0.999
        r[6] *= 0.999

        if r[0] < WORLD_MIN:
            r[0] = WORLD_MIN
            r[4] = abs(r[4])
        elif r[0] > WORLD_MAX:
            r[0] = WORLD_MAX
            r[4] = -abs(r[4])

        if r[1] < WORLD_MIN:
            r[1] = WORLD_MIN
            r[5] = abs(r[5])
        elif r[1] > WORLD_MAX:
            r[1] = WORLD_MAX
            r[5] = -abs(r[5])

        if r[2] < WORLD_Z_MIN:
            r[2] = WORLD_Z_MIN
            r[6] = abs(r[6])
        elif r[2] > WORLD_Z_MAX:
            r[2] = WORLD_Z_MAX
            r[6] = -abs(r[6])

    for r in rocks:
        if r[10] > 0:
            r[10] -= 1

        dx = player_x - r[0]
        dy = player_y - r[1]
        dz = player_z - r[2]
        rr = r[3] + SHIP_COLLISION_R
        is_colliding = (dx*dx + dy*dy + dz*dz) <= (rr * rr)

        if is_colliding and r[10] == 0 and player_life > 0:
            player_life = max(0, player_life - int(r[9]))
            r[10] = ROCK_HIT_COOLDOWN_FRAMES
            if player_life <= 0:
                _trigger_game_over()

        if is_colliding:
            _resolve_ship_rock_collision(r)

    _update_enemy_player_collisions()

    _ensure_enemies_alive()
    _update_enemies_and_fire()
    _update_enemy_bullets_and_hit_player()
    _update_player_bullets_and_hits()

    glutPostRedisplay()

def _trigger_game_over():
    global game_over, controls_disabled
    if game_over:
        return
    game_over = True
    controls_disabled = True
    _record_score_on_game_over()

def reset_game():
    global player_x, player_y, player_z, player_angle
    global vel_x, vel_y, vel_z
    global player_life, player_max_hp, player_score, ship_level, gun_level
    global game_over, controls_disabled
    global first_person
    global player_bullet_cd
    global enemy_kills_total, rocks_destroyed
    global wormhole_tp_cd
    global _scoreboard_locked

    wormhole_tp_cd = 0
    _scoreboard_locked = False

    player_x, player_y, player_z = 0.0, 0.0, 30.0
    player_angle = 0.0

    vel_x, vel_y = 0.0, 0.0
    vel_z = 0.0

    ship_level = 1
    player_max_hp = SHIP_STATS_BY_LEVEL[ship_level]["hp"]
    player_life = player_max_hp

    player_score = 0

    enemy_kills_total = 0
    gun_level = 1
    rocks_destroyed = 0

    game_over = False
    controls_disabled = False

    for k in keys:
        keys[k] = False

    player_bullets.clear()
    player_bullet_cd = 0

    init_rocks()
    init_black_holes()
    init_white_holes()
    init_wormholes()
    init_enemies()

def keyboardListener(key, x, y):
    global first_person, controls_disabled
    try:
        k = key.decode("utf-8").lower()
    except:
        return

    if k == 'r':
        reset_game()
        return

    if k == 'v':
        first_person = not first_person
        return

    if k == ' ':
        _spawn_player_bullet()
        return

    if controls_disabled:
        return

    if k in keys:
        keys[k] = True

def keyboardUpListener(key, x, y):
    global controls_disabled
    try:
        k = key.decode("utf-8").lower()
    except:
        return

    if controls_disabled:
        return

    if k in keys:
        keys[k] = False

def mouseListener(button, state, x, y):
    global first_person
    if state == GLUT_DOWN:
        if button == GLUT_RIGHT_BUTTON:
            first_person = not first_person
        elif button == GLUT_LEFT_BUTTON:
            _spawn_player_bullet()

def reshape(w, h):
    global WIN_W, WIN_H
    WIN_W = max(1, int(w))
    WIN_H = max(1, int(h))
    glViewport(0, 0, WIN_W, WIN_H)

def main():
    glutInit()
    glutInitDisplayMode(GLUT_DOUBLE | GLUT_RGB | GLUT_DEPTH)
    glutInitWindowSize(1000, 800)
    glutInitWindowPosition(50, 50)
    glutCreateWindow(b"Singularity Wars")

    glEnable(GL_DEPTH_TEST)
    glClearColor(0, 0, 0, 1)

    init_rocks()
    init_black_holes()
    init_white_holes()
    init_wormholes()
    init_enemies()

    glutDisplayFunc(showScreen)
    glutIdleFunc(idle)
    glutKeyboardFunc(keyboardListener)
    glutKeyboardUpFunc(keyboardUpListener)
    glutMouseFunc(mouseListener)
    glutReshapeFunc(reshape)

    glutMainLoop()

if __name__ == "__main__":
    main()