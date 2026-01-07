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

#Game State
game_paused = False
difficulty = "Normal"  # Easy, Normal, Hard
game_started = False

#Visual Effects State
damage_flash_frames = 0
shield_pulse_frames = 0
DAMAGE_FLASH_DURATION = 15
SHIELD_PULSE_DURATION = 30

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

def get_difficulty_setting(key):
    return DIFFICULTY_SETTINGS[difficulty].get(key, 1.0)

def _update_gun_level_from_kills():
    global gun_level
    lvl = 1
    for L, need in GUN_LEVEL_BY_TOTAL_KILLS:
        if enemy_kills_total >= need:
            lvl = L
    if lvl != gun_level:
        spawn_levelup_effect(player_x, player_y, player_z, 'gun')
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
    
    # Spawn muzzle flash
    muzzle_flashes.append([sx, sy, sz, MUZZLE_FLASH_LIFE])

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
                    spawn_explosion(ex, ey, ez, 'enemy', s)
                    score_gain = int(25 * get_difficulty_setting("score_mult"))
                    player_score += score_gain
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

DIFFICULTY_SETTINGS = {
    "Easy": {
        "enemy_damage_mult": 0.6,
        "enemy_speed_mult": 0.7,
        "enemy_fire_rate_mult": 1.5,
        "player_damage_mult": 1.3,
        "score_mult": 0.8
    },
    "Normal": {
        "enemy_damage_mult": 1.0,
        "enemy_speed_mult": 1.0,
        "enemy_fire_rate_mult": 1.0,
        "player_damage_mult": 1.0,
        "score_mult": 1.0
    },
    "Hard": {
        "enemy_damage_mult": 1.5,
        "enemy_speed_mult": 1.3,
        "enemy_fire_rate_mult": 0.7,
        "player_damage_mult": 0.8,
        "score_mult": 1.5
    }
}

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
            spawn_explosion(ex, ey, ez, 'enemy', s)
            trigger_damage_flash()
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
            speed = ENEMY_SPEED * get_difficulty_setting("enemy_speed_mult")
            ex += dx * inv * speed
            ey += dy * inv * speed
            ez += dz * inv * speed

            ex = clamp(ex, WORLD_MIN, WORLD_MAX)
            ey = clamp(ey, WORLD_MIN, WORLD_MAX)
            ez = clamp(ez, WORLD_Z_MIN, WORLD_Z_MAX)

            e[0], e[1], e[2] = ex, ey, ez

        if e[4] > 0:
            e[4] -= 1

        if dist3_ <= ENEMY_FIRE_RANGE and e[4] == 0:
            _spawn_enemy_bullet(ex, ey, ez)
            cooldown = int(ENEMY_FIRE_COOLDOWN_FRAMES * get_difficulty_setting("enemy_fire_rate_mult"))
            e[4] = cooldown

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
            trigger_damage_flash()
            damage = int(ENEMY_BULLET_DAMAGE * get_difficulty_setting("enemy_damage_mult"))
            player_life = max(0, player_life - damage)
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
stars = []
engine_particles = []
bh_pull_particles = []
wh_push_particles = []
explosion_particles = []
muzzle_flashes = []
bullet_trails = []
levelup_particles = []
wormhole_vortex_particles = []
space_debris = []
speed_lines = []


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
        # Spawn explosion at old position before respawning
        spawn_explosion(r[0], r[1], r[2], 'rock', r[11])
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

#Stars
STAR_COUNT = 800
STAR_SIZE_MIN = 0.5
STAR_SIZE_MAX = 3.0
STAR_RANGE = 4000.0

#Engine Particles
ENGINE_PARTICLE_SPAWN_RATE = 5
ENGINE_PARTICLE_LIFE = 30
ENGINE_PARTICLE_SIZE = 6.0
ENGINE_PARTICLE_SPEED_FACTOR = 0.7
MIN_SPEED_FOR_PARTICLES = 1.5

#Black Hole Pull Effects
BH_PULL_PARTICLE_SPAWN_RATE = 8
BH_PULL_PARTICLE_LIFE = 60
BH_PULL_EFFECT_RADIUS = 600.0
BH_PULL_VISUAL_STRENGTH = 4.0

#White Hole Push Effects
WH_PUSH_PARTICLE_SPAWN_RATE = 8
WH_PUSH_PARTICLE_LIFE = 60
WH_PUSH_EFFECT_RADIUS = 600.0
WH_PUSH_VISUAL_STRENGTH = 4.5

#Explosion Effects
EXPLOSION_PARTICLE_COUNT = 30
EXPLOSION_PARTICLE_LIFE = 40
EXPLOSION_SPEED_MIN = 2.0
EXPLOSION_SPEED_MAX = 8.0
EXPLOSION_SIZE = 4.0

#Muzzle Flash
MUZZLE_FLASH_LIFE = 5
MUZZLE_FLASH_SIZE = 15.0

#Bullet Trails
BULLET_TRAIL_SPAWN_RATE = 2
BULLET_TRAIL_LIFE = 15
BULLET_TRAIL_SIZE = 2.0

#Level Up Effects
LEVELUP_PARTICLE_COUNT = 50
LEVELUP_PARTICLE_LIFE = 60
LEVELUP_SPEED = 5.0

#Wormhole Vortex
WORMHOLE_VORTEX_PARTICLES_PER_HOLE = 40
WORMHOLE_VORTEX_RADIUS = 60.0
WORMHOLE_VORTEX_SPEED = 0.8

#Speed Lines
SPEED_LINE_COUNT = 20
SPEED_LINE_MIN_SPEED = 15.0
SPEED_LINE_LENGTH = 150.0

#Space Debris
SPACE_DEBRIS_COUNT = 100
DEBRIS_DRIFT_SPEED = 0.3
DEBRIS_SIZE_MIN = 1.0
DEBRIS_SIZE_MAX = 3.0

#Enemy Warning Indicator
ENEMY_WARNING_FLASH_FRAMES = 20

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
        trigger_damage_flash()
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


def trigger_damage_flash():
    global damage_flash_frames, shield_pulse_frames
    damage_flash_frames = DAMAGE_FLASH_DURATION
    shield_pulse_frames = SHIELD_PULSE_DURATION

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


def init_stars():
    stars.clear()
    for _ in range(STAR_COUNT):
        x = random.uniform(-STAR_RANGE, STAR_RANGE)
        y = random.uniform(-STAR_RANGE, STAR_RANGE)
        z = random.uniform(-STAR_RANGE / 2, STAR_RANGE / 2)
        size = random.uniform(STAR_SIZE_MIN, STAR_SIZE_MAX)
        brightness = random.uniform(0.5, 1.0)
        stars.append([x, y, z, size, brightness])

def _spawn_engine_particles():
    if game_over or controls_disabled:
        return
    
    speed = math.sqrt(vel_x**2 + vel_y**2 + vel_z**2)
    if speed > MIN_SPEED_FOR_PARTICLES:
        pass
    else:
        return
    
    rad = math.radians(player_angle)
    fx, fy = math.cos(rad), math.sin(rad)
    
    # Engine positions (relative to ship center, scaled)
    engine_offsets = [
        (-40 * SHIP_SCALE, 20.5 * SHIP_SCALE, -8 * SHIP_SCALE),
        (-40 * SHIP_SCALE, -20.5 * SHIP_SCALE, -8 * SHIP_SCALE)
    ]
    
    for _ in range(ENGINE_PARTICLE_SPAWN_RATE):
        for offset in engine_offsets:
            # Rotate offset by player angle
            ox, oy, oz = offset
            rot_x = ox * fx - oy * fy
            rot_y = ox * fy + oy * fx
            
            px = player_x + rot_x
            py = player_y + rot_y
            pz = player_z + oz
            
            # Particle velocity opposite to ship direction
            vx = -vel_x * ENGINE_PARTICLE_SPEED_FACTOR + random.uniform(-0.5, 0.5)
            vy = -vel_y * ENGINE_PARTICLE_SPEED_FACTOR + random.uniform(-0.5, 0.5)
            vz = -vel_z * ENGINE_PARTICLE_SPEED_FACTOR + random.uniform(-0.3, 0.3)
            
            # Color varies based on speed (blue to cyan)
            intensity = min(1.0, speed / MAX_SPEED)
            r = 0.2 * intensity
            g = 0.6 + 0.3 * intensity
            b = 0.9 + 0.1 * intensity
            
            engine_particles.append([px, py, pz, vx, vy, vz, ENGINE_PARTICLE_LIFE, r, g, b])

def _update_engine_particles():
    keep = []
    for p in engine_particles:
        x, y, z, vx, vy, vz, life, r, g, b = p
        x += vx
        y += vy
        z += vz
        life -= 1
        
        if life > 0:
            keep.append([x, y, z, vx, vy, vz, life, r, g, b])
    
    engine_particles[:] = keep

def draw_engine_particles():
    glPointSize(ENGINE_PARTICLE_SIZE)
    glBegin(GL_POINTS)
    for p in engine_particles:
        x, y, z, vx, vy, vz, life, r, g, b = p
        alpha = life / float(ENGINE_PARTICLE_LIFE)
        glColor3f(r * alpha, g * alpha, b * alpha)
        glVertex3f(x, y, z)
    glEnd()

def _spawn_bh_pull_particles():
    if game_over:
        return
    
    for bh in black_holes:
        bx, by, bz = bh["pos"]
        core_r = bh["core_r"]
        effect_r = core_r * HOLE_EFFECT_RANGE_MULT
        
        # Check if player is in range
        dx_p = player_x - bx
        dy_p = player_y - by
        dz_p = player_z - bz
        dist_p = math.sqrt(dx_p**2 + dy_p**2 + dz_p**2)
        
        if dist_p < BH_PULL_EFFECT_RADIUS:
            # Spawn particles around the player being pulled
            for _ in range(BH_PULL_PARTICLE_SPAWN_RATE):
                angle = random.uniform(0, 2 * math.pi)
                radius = random.uniform(40, 120)
                
                px = player_x + math.cos(angle) * radius
                py = player_y + math.sin(angle) * radius
                pz = player_z + random.uniform(-30, 30)
                
                bh_pull_particles.append([px, py, pz, bx, by, bz, BH_PULL_PARTICLE_LIFE])
        
        # Also check enemies
        for e in enemies:
            ex, ey, ez = e[0], e[1], e[2]
            dx_e = ex - bx
            dy_e = ey - by
            dz_e = ez - bz
            dist_e = math.sqrt(dx_e**2 + dy_e**2 + dz_e**2)
            
            if dist_e < BH_PULL_EFFECT_RADIUS and random.random() < 0.3:
                for _ in range(2):
                    angle = random.uniform(0, 2 * math.pi)
                    radius = random.uniform(30, 80)
                    
                    px = ex + math.cos(angle) * radius
                    py = ey + math.sin(angle) * radius
                    pz = ez + random.uniform(-20, 20)
                    
                    bh_pull_particles.append([px, py, pz, bx, by, bz, BH_PULL_PARTICLE_LIFE])

def _update_bh_pull_particles():
    keep = []
    for p in bh_pull_particles:
        x, y, z, bx, by, bz, life = p
        
        # Pull towards black hole
        dx = bx - x
        dy = by - y
        dz = bz - z
        dist = math.sqrt(dx**2 + dy**2 + dz**2)
        
        if dist > 1.0:
            # Accelerate towards black hole
            pull_speed = BH_PULL_VISUAL_STRENGTH * (1.0 - life / BH_PULL_PARTICLE_LIFE)
            x += (dx / dist) * pull_speed
            y += (dy / dist) * pull_speed
            z += (dz / dist) * pull_speed
        
        life -= 1
        
        # Keep particle if still alive and not too close to black hole
        if life > 0 and dist > 5.0:
            keep.append([x, y, z, bx, by, bz, life])
    
    bh_pull_particles[:] = keep

def draw_bh_pull_particles():
    glPointSize(3.0)
    glBegin(GL_POINTS)
    for p in bh_pull_particles:
        x, y, z, bx, by, bz, life = p
        alpha = life / float(BH_PULL_PARTICLE_LIFE)
        
        # Color gradient: orange to red as it gets pulled in
        r = 0.8 + 0.2 * (1.0 - alpha)
        g = 0.3 * alpha
        b = 0.1 * alpha
        
        glColor3f(r, g, b)
        glVertex3f(x, y, z)
    glEnd()
    
    # Draw lines from particles to black holes for extra effect
    glLineWidth(1.0)
    glBegin(GL_LINES)
    for p in bh_pull_particles:
        x, y, z, bx, by, bz, life = p
        if random.random() < 0.15:  # Only draw some lines to avoid clutter
            alpha = life / float(BH_PULL_PARTICLE_LIFE) * 0.3
            glColor4f(0.9, 0.4, 0.1, alpha)
            glVertex3f(x, y, z)
            glColor4f(0.5, 0.1, 0.05, 0.0)
            glVertex3f(bx, by, bz)
    glEnd()

def _spawn_wh_push_particles():
    if game_over:
        return
    
    for wh in white_holes:
        wx, wy, wz = wh["pos"]
        core_r = wh["core_r"]
        effect_r = core_r * HOLE_EFFECT_RANGE_MULT
        
        # Check if player is in range
        dx_p = player_x - wx
        dy_p = player_y - wy
        dz_p = player_z - wz
        dist_p = math.sqrt(dx_p**2 + dy_p**2 + dz_p**2)
        
        if dist_p < WH_PUSH_EFFECT_RADIUS:
            # Spawn particles at the white hole core, pushing outward
            for _ in range(WH_PUSH_PARTICLE_SPAWN_RATE):
                angle = random.uniform(0, 2 * math.pi)
                elevation = random.uniform(-0.5, 0.5)
                
                # Start near white hole center
                start_r = core_r + random.uniform(5, 20)
                px = wx + math.cos(angle) * start_r
                py = wy + math.sin(angle) * start_r
                pz = wz + elevation * start_r
                
                # Direction away from white hole
                dx = px - wx
                dy = py - wy
                dz = pz - wz
                d = math.sqrt(dx**2 + dy**2 + dz**2)
                if d > 0.1:
                    dx /= d
                    dy /= d
                    dz /= d
                
                wh_push_particles.append([px, py, pz, dx, dy, dz, WH_PUSH_PARTICLE_LIFE])
        
        # Also check enemies
        for e in enemies:
            ex, ey, ez = e[0], e[1], e[2]
            dx_e = ex - wx
            dy_e = ey - wy
            dz_e = ez - wz
            dist_e = math.sqrt(dx_e**2 + dy_e**2 + dz_e**2)
            
            if dist_e < WH_PUSH_EFFECT_RADIUS and random.random() < 0.3:
                for _ in range(2):
                    angle = random.uniform(0, 2 * math.pi)
                    start_r = core_r + random.uniform(5, 15)
                    px = wx + math.cos(angle) * start_r
                    py = wy + math.sin(angle) * start_r
                    pz = wz + random.uniform(-10, 10)
                    
                    dx = px - wx
                    dy = py - wy
                    dz = pz - wz
                    d = math.sqrt(dx**2 + dy**2 + dz**2)
                    if d > 0.1:
                        dx /= d
                        dy /= d
                        dz /= d
                    
                    wh_push_particles.append([px, py, pz, dx, dy, dz, WH_PUSH_PARTICLE_LIFE])

def _update_wh_push_particles():
    keep = []
    for p in wh_push_particles:
        x, y, z, dx, dy, dz, life = p
        
        # Push away from white hole
        push_speed = WH_PUSH_VISUAL_STRENGTH * (1.0 - life / WH_PUSH_PARTICLE_LIFE)
        x += dx * push_speed
        y += dy * push_speed
        z += dz * push_speed
        
        life -= 1
        
        # Keep particle if still alive
        if life > 0:
            keep.append([x, y, z, dx, dy, dz, life])
    
    wh_push_particles[:] = keep

def draw_wh_push_particles():
    glPointSize(3.0)
    glBegin(GL_POINTS)
    for p in wh_push_particles:
        x, y, z, dx, dy, dz, life = p
        alpha = life / float(WH_PUSH_PARTICLE_LIFE)
        
        # Color gradient: bright cyan/white fading to blue
        r = 0.6 * alpha + 0.3 * (1.0 - alpha)
        g = 0.8 * alpha + 0.5 * (1.0 - alpha)
        b = 1.0
        
        glColor3f(r, g, b)
        glVertex3f(x, y, z)
    glEnd()
    
    # Draw radial lines from white holes for extra effect
    glLineWidth(1.0)
    glBegin(GL_LINES)
    for wh in white_holes:
        wx, wy, wz = wh["pos"]
        core_r = wh["core_r"]
        
        # Draw some radial burst lines
        if random.random() < 0.5:
            for _ in range(3):
                angle = random.uniform(0, 2 * math.pi)
                elevation = random.uniform(-0.3, 0.3)
                
                start_r = core_r * 1.2
                end_r = core_r * 3.0
                
                sx = wx + math.cos(angle) * start_r
                sy = wy + math.sin(angle) * start_r
                sz = wz + elevation * start_r
                
                ex = wx + math.cos(angle) * end_r
                ey = wy + math.sin(angle) * end_r
                ez = wz + elevation * end_r
                
                glColor4f(0.7, 0.9, 1.0, 0.3)
                glVertex3f(sx, sy, sz)
                glColor4f(0.3, 0.5, 0.8, 0.0)
                glVertex3f(ex, ey, ez)
    glEnd()

def spawn_explosion(x, y, z, color_type='enemy', scale=1.0):
    """Spawn explosion particles at given position
    color_type: 'enemy' (orange/red), 'rock' (gray/brown), 'player' (blue/white)
    """
    particle_count = int(EXPLOSION_PARTICLE_COUNT * scale)
    
    for _ in range(particle_count):
        # Random direction
        angle = random.uniform(0, 2 * math.pi)
        elevation = random.uniform(-math.pi/3, math.pi/3)
        
        speed = random.uniform(EXPLOSION_SPEED_MIN, EXPLOSION_SPEED_MAX) * scale
        
        vx = math.cos(angle) * math.cos(elevation) * speed
        vy = math.sin(angle) * math.cos(elevation) * speed
        vz = math.sin(elevation) * speed
        
        # Color based on type
        if color_type == 'enemy':
            r = random.uniform(0.8, 1.0)
            g = random.uniform(0.3, 0.6)
            b = random.uniform(0.0, 0.2)
        elif color_type == 'rock':
            gray = random.uniform(0.4, 0.7)
            r = gray + random.uniform(0.0, 0.2)
            g = gray
            b = gray - random.uniform(0.0, 0.1)
        else:  # player
            r = random.uniform(0.5, 0.8)
            g = random.uniform(0.7, 0.9)
            b = random.uniform(0.9, 1.0)
        
        life = int(EXPLOSION_PARTICLE_LIFE * random.uniform(0.7, 1.3))
        size = random.uniform(0.7, 1.3) * scale
        
        explosion_particles.append([x, y, z, vx, vy, vz, life, r, g, b, size])

def _update_explosion_particles():
    keep = []
    for p in explosion_particles:
        x, y, z, vx, vy, vz, life, r, g, b, size = p
        
        # Move particle
        x += vx
        y += vy
        z += vz
        
        # Apply drag
        vx *= 0.96
        vy *= 0.96
        vz *= 0.96
        
        life -= 1
        
        if life > 0:
            keep.append([x, y, z, vx, vy, vz, life, r, g, b, size])
    
    explosion_particles[:] = keep

def draw_explosion_particles():
    for p in explosion_particles:
        x, y, z, vx, vy, vz, life, r, g, b, size = p
        alpha = life / float(EXPLOSION_PARTICLE_LIFE)
        
        # Fade out and change color as particles age
        glPointSize(EXPLOSION_SIZE * size * alpha)
        glBegin(GL_POINTS)
        glColor3f(r * alpha, g * alpha, b * alpha)
        glVertex3f(x, y, z)
        glEnd()

def _update_muzzle_flashes():
    keep = []
    for mf in muzzle_flashes:
        x, y, z, life = mf
        life -= 1
        if life > 0:
            keep.append([x, y, z, life])
    muzzle_flashes[:] = keep

def draw_muzzle_flashes():
    for mf in muzzle_flashes:
        x, y, z, life = mf
        alpha = life / float(MUZZLE_FLASH_LIFE)
        size = MUZZLE_FLASH_SIZE * (1.0 + (1.0 - alpha) * 0.5)
        
        glPointSize(size)
        glBegin(GL_POINTS)
        glColor3f(1.0 * alpha, 0.9 * alpha, 0.5 * alpha)
        glVertex3f(x, y, z)
        glEnd()

def _spawn_bullet_trails():
    # Spawn trails for player bullets
    for b in player_bullets:
        if random.random() < 0.5:
            x, y, z = b[0], b[1], b[2]
            bullet_trails.append([x, y, z, BULLET_TRAIL_LIFE, 0.2, 0.9, 1.0])
    
    # Spawn trails for enemy bullets
    for b in enemy_bullets:
        if random.random() < 0.5:
            x, y, z = b[0], b[1], b[2]
            bullet_trails.append([x, y, z, BULLET_TRAIL_LIFE, 1.0, 0.3, 0.2])

def _update_bullet_trails():
    keep = []
    for bt in bullet_trails:
        x, y, z, life, r, g, b = bt
        life -= 1
        if life > 0:
            keep.append([x, y, z, life, r, g, b])
    bullet_trails[:] = keep

def draw_bullet_trails():
    glPointSize(BULLET_TRAIL_SIZE)
    glBegin(GL_POINTS)
    for bt in bullet_trails:
        x, y, z, life, r, g, b = bt
        alpha = life / float(BULLET_TRAIL_LIFE) * 0.6
        glColor3f(r * alpha, g * alpha, b * alpha)
        glVertex3f(x, y, z)
    glEnd()

def spawn_levelup_effect(x, y, z, effect_type='gun'):
    """Spawn level up particles
    effect_type: 'gun' (cyan) or 'ship' (gold)
    """
    for _ in range(LEVELUP_PARTICLE_COUNT):
        angle = random.uniform(0, 2 * math.pi)
        elevation = random.uniform(-math.pi/2, math.pi/2)
        speed = random.uniform(LEVELUP_SPEED * 0.5, LEVELUP_SPEED)
        
        vx = math.cos(angle) * math.cos(elevation) * speed
        vy = math.sin(angle) * math.cos(elevation) * speed
        vz = math.sin(elevation) * speed
        
        if effect_type == 'gun':
            r, g, b = 0.3, 0.9, 1.0
        else:  # ship
            r, g, b = 1.0, 0.8, 0.2
        
        life = int(LEVELUP_PARTICLE_LIFE * random.uniform(0.8, 1.2))
        levelup_particles.append([x, y, z, vx, vy, vz, life, r, g, b])

def _update_levelup_particles():
    keep = []
    for p in levelup_particles:
        x, y, z, vx, vy, vz, life, r, g, b = p
        x += vx
        y += vy
        z += vz
        vx *= 0.98
        vy *= 0.98
        vz *= 0.98
        life -= 1
        if life > 0:
            keep.append([x, y, z, vx, vy, vz, life, r, g, b])
    levelup_particles[:] = keep

def draw_levelup_particles():
    glPointSize(5.0)
    glBegin(GL_POINTS)
    for p in levelup_particles:
        x, y, z, vx, vy, vz, life, r, g, b = p
        alpha = life / float(LEVELUP_PARTICLE_LIFE)
        glColor3f(r * alpha, g * alpha, b * alpha)
        glVertex3f(x, y, z)
    glEnd()

def draw_shield():
    if shield_pulse_frames <= 0:
        return
    
    glPushMatrix()
    glTranslatef(player_x, player_y, player_z)
    
    alpha = shield_pulse_frames / float(SHIELD_PULSE_DURATION)
    pulse = math.sin(shield_pulse_frames * 0.3) * 0.3 + 0.7
    radius = SHIP_COLLISION_R * 1.5 * pulse
    
    # Draw shield sphere with transparency
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    glColor4f(0.2, 0.6, 1.0, alpha * 0.3)
    
    quad = gluNewQuadric()
    gluSphere(quad, radius, 20, 20)
    
    glDisable(GL_BLEND)
    glPopMatrix()

def draw_damage_flash():
    if damage_flash_frames <= 0:
        return
    
    _begin_2d_overlay()
    
    alpha = damage_flash_frames / float(DAMAGE_FLASH_DURATION) * 0.4
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    glColor4f(1.0, 0.2, 0.2, alpha)
    
    glBegin(GL_QUADS)
    glVertex2f(0, 0)
    glVertex2f(WIN_W, 0)
    glVertex2f(WIN_W, WIN_H)
    glVertex2f(0, WIN_H)
    glEnd()
    
    glDisable(GL_BLEND)
    _end_2d_overlay()

def init_space_debris():
    space_debris.clear()
    for _ in range(SPACE_DEBRIS_COUNT):
        x = random.uniform(-STAR_RANGE, STAR_RANGE)
        y = random.uniform(-STAR_RANGE, STAR_RANGE)
        z = random.uniform(-STAR_RANGE / 2, STAR_RANGE / 2)
        vx = random.uniform(-DEBRIS_DRIFT_SPEED, DEBRIS_DRIFT_SPEED)
        vy = random.uniform(-DEBRIS_DRIFT_SPEED, DEBRIS_DRIFT_SPEED)
        vz = random.uniform(-DEBRIS_DRIFT_SPEED * 0.5, DEBRIS_DRIFT_SPEED * 0.5)
        size = random.uniform(DEBRIS_SIZE_MIN, DEBRIS_SIZE_MAX)
        brightness = random.uniform(0.3, 0.6)
        space_debris.append([x, y, z, vx, vy, vz, size, brightness])

def _update_space_debris():
    for d in space_debris:
        d[0] += d[3]  # x += vx
        d[1] += d[4]  # y += vy
        d[2] += d[5]  # z += vz
        
        # Wrap around
        if d[0] < -STAR_RANGE: d[0] = STAR_RANGE
        if d[0] > STAR_RANGE: d[0] = -STAR_RANGE
        if d[1] < -STAR_RANGE: d[1] = STAR_RANGE
        if d[1] > STAR_RANGE: d[1] = -STAR_RANGE
        if d[2] < -STAR_RANGE/2: d[2] = STAR_RANGE/2
        if d[2] > STAR_RANGE/2: d[2] = -STAR_RANGE/2

def draw_space_debris():
    glPointSize(2.0)
    glBegin(GL_POINTS)
    for d in space_debris:
        x, y, z, vx, vy, vz, size, brightness = d
        glColor3f(brightness * 0.7, brightness * 0.6, brightness * 0.5)
        glVertex3f(x, y, z)
    glEnd()

def _spawn_wormhole_vortex_particles():
    for w in wormholes:
        wx, wy, wz = w["pos"]
        core_r = w["core_r"]
        
        # Spawn spiraling particles
        for _ in range(2):  # Spawn a few per frame
            angle = random.uniform(0, 2 * math.pi)
            radius = random.uniform(core_r * 2, core_r * 4)
            height = random.uniform(-core_r, core_r)
            
            x = wx + math.cos(angle) * radius
            y = wy + math.sin(angle) * radius
            z = wz + height
            
            wormhole_vortex_particles.append([x, y, z, wx, wy, wz, angle, 60])

def _update_wormhole_vortex_particles():
    keep = []
    for p in wormhole_vortex_particles:
        x, y, z, wx, wy, wz, angle, life = p
        
        # Spiral inward
        dx = x - wx
        dy = y - wy
        radius = math.sqrt(dx*dx + dy*dy)
        
        if radius > 5.0:
            angle += WORMHOLE_VORTEX_SPEED
            radius *= 0.95  # Move inward
            
            x = wx + math.cos(angle) * radius
            y = wy + math.sin(angle) * radius
            z += (wz - z) * 0.05  # Move toward center z
            
            life -= 1
            if life > 0:
                keep.append([x, y, z, wx, wy, wz, angle, life])
    
    wormhole_vortex_particles[:] = keep

def draw_wormhole_vortex_particles():
    glPointSize(3.0)
    glBegin(GL_POINTS)
    for p in wormhole_vortex_particles:
        x, y, z, wx, wy, wz, angle, life = p
        alpha = life / 60.0
        
        # Purple/magenta color
        glColor3f(0.7 * alpha, 0.3 * alpha, 0.9 * alpha)
        glVertex3f(x, y, z)
    glEnd()

def _update_speed_lines():
    speed = math.sqrt(vel_x**2 + vel_y**2 + vel_z**2)
    
    if speed < SPEED_LINE_MIN_SPEED:
        speed_lines.clear()
        return
    
    # Generate speed lines if moving fast
    if len(speed_lines) < SPEED_LINE_COUNT:
        for _ in range(SPEED_LINE_COUNT - len(speed_lines)):
            angle = random.uniform(0, 2 * math.pi)
            dist = random.uniform(100, 500)
            offset_x = math.cos(angle) * dist
            offset_y = math.sin(angle) * dist
            offset_z = random.uniform(-200, 200)
            
            speed_lines.append([offset_x, offset_y, offset_z])

def draw_speed_lines():
    if len(speed_lines) == 0:
        return
    
    speed = math.sqrt(vel_x**2 + vel_y**2 + vel_z**2)
    if speed < SPEED_LINE_MIN_SPEED:
        return
    
    intensity = min(1.0, (speed - SPEED_LINE_MIN_SPEED) / MAX_SPEED)
    
    glLineWidth(2.0)
    glBegin(GL_LINES)
    for sl in speed_lines:
        offset_x, offset_y, offset_z = sl
        
        # Line starts ahead of player, goes backward
        start_x = player_x + offset_x - vel_x * 5
        start_y = player_y + offset_y - vel_y * 5
        start_z = player_z + offset_z - vel_z * 5
        
        end_x = start_x - vel_x * SPEED_LINE_LENGTH / speed
        end_y = start_y - vel_y * SPEED_LINE_LENGTH / speed
        end_z = start_z - vel_z * SPEED_LINE_LENGTH / speed
        
        glColor4f(0.8 * intensity, 0.9 * intensity, 1.0 * intensity, intensity * 0.6)
        glVertex3f(start_x, start_y, start_z)
        glColor4f(0.3, 0.4, 0.5, 0.0)
        glVertex3f(end_x, end_y, end_z)
    glEnd()

def draw_health_bar():
    _begin_2d_overlay()
    
    # Health bar position and size
    bar_x = 12
    bar_y = WIN_H - 50
    bar_w = 250
    bar_h = 20
    
    # Background
    glColor3f(0.2, 0.2, 0.2)
    glBegin(GL_QUADS)
    glVertex2f(bar_x, bar_y)
    glVertex2f(bar_x + bar_w, bar_y)
    glVertex2f(bar_x + bar_w, bar_y + bar_h)
    glVertex2f(bar_x, bar_y + bar_h)
    glEnd()
    
    # Health fill
    health_percent = max(0.0, min(1.0, player_life / float(player_max_hp)))
    fill_w = bar_w * health_percent
    
    # Color gradient based on health
    if health_percent > 0.6:
        r, g, b = 0.2, 0.9, 0.2  # Green
    elif health_percent > 0.3:
        r, g, b = 0.9, 0.9, 0.2  # Yellow
    else:
        r, g, b = 0.9, 0.2, 0.2  # Red
    
    glColor3f(r, g, b)
    glBegin(GL_QUADS)
    glVertex2f(bar_x, bar_y)
    glVertex2f(bar_x + fill_w, bar_y)
    glVertex2f(bar_x + fill_w, bar_y + bar_h)
    glVertex2f(bar_x, bar_y + bar_h)
    glEnd()
    
    # Border
    glColor3f(0.8, 0.8, 0.8)
    glLineWidth(2.0)
    glBegin(GL_LINE_LOOP)
    glVertex2f(bar_x, bar_y)
    glVertex2f(bar_x + bar_w, bar_y)
    glVertex2f(bar_x + bar_w, bar_y + bar_h)
    glVertex2f(bar_x, bar_y + bar_h)
    glEnd()
    
    # Text
    glColor3f(1.0, 1.0, 1.0)
    draw_text(bar_x + 5, bar_y + 5, f"{player_life} / {player_max_hp}")
    
    _end_2d_overlay()

def draw_enemy_warning_indicators():
    for e in enemies:
        ex, ey, ez, ang, cd, s, ehp = e
        
        # Show warning when about to fire (last 20 frames of cooldown)
        if cd <= ENEMY_WARNING_FLASH_FRAMES and cd > 0:
            flash = (cd % 6) < 3  # Blink effect
            if flash:
                glPushMatrix()
                glTranslatef(ex, ey, ez)
                
                intensity = 1.0 - (cd / float(ENEMY_WARNING_FLASH_FRAMES))
                glColor3f(1.0 * intensity, 0.3 * intensity, 0.0)
                
                # Draw glowing ring
                glBegin(GL_LINE_LOOP)
                for i in range(16):
                    angle = (i / 16.0) * 2 * math.pi
                    radius = (ENEMY_HIT_R * s) * (1.2 + intensity * 0.3)
                    x = math.cos(angle) * radius
                    y = math.sin(angle) * radius
                    glVertex3f(x, y, 0)
                glEnd()
                
                glPopMatrix()

def draw_gravitational_lensing():
    # Simple visual distortion effect around black holes
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    
    for bh in black_holes:
        bx, by, bz = bh["pos"]
        core_r = bh["core_r"]
        
        # Check if player is close enough to see lensing
        dx = player_x - bx
        dy = player_y - by
        dz = player_z - bz
        dist = math.sqrt(dx*dx + dy*dy + dz*dz)
        
        if dist < 800.0:
            glPushMatrix()
            glTranslatef(bx, by, bz)
            
            # Draw concentric distortion rings
            for ring in range(3):
                radius = core_r * (3.0 + ring * 1.5)
                alpha = 0.15 - ring * 0.04
                
                glColor4f(0.1, 0.05, 0.2, alpha)
                glBegin(GL_LINE_LOOP)
                for i in range(32):
                    angle = (i / 32.0) * 2 * math.pi
                    x = math.cos(angle) * radius
                    y = math.sin(angle) * radius
                    glVertex3f(x, y, 0)
                glEnd()
            
            glPopMatrix()
    
    glDisable(GL_BLEND)

# Draw environment
def draw_stars():
    glPointSize(2.0)
    glBegin(GL_POINTS)
    for s in stars:
        x, y, z, size, brightness = s
        glColor3f(brightness, brightness, brightness)
        glVertex3f(x, y, z)
    glEnd()

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
    old_level = ship_level
    ship_level = clamp(int(new_level), 1, 5)
    player_max_hp = SHIP_STATS_BY_LEVEL[ship_level]["hp"]
    player_life = player_max_hp
    if new_level != old_level:
        spawn_levelup_effect(player_x, player_y, player_z, 'ship')

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
    top_y = WIN_H - 85  # Moved down to make room for health bar
    line = 22

    draw_text(left_x, top_y,           f"Player Score: {player_score}")
    draw_text(left_x, top_y - line,    f"Ship Level: {ship_level}")
    draw_text(left_x, top_y - 2*line,  f"Gun Level: {gun_level}")

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
        draw_game_over_screen()

def draw_game_over_screen():
    _begin_2d_overlay()
    
    # Dark overlay
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    glColor4f(0.0, 0.0, 0.0, 0.85)
    glBegin(GL_QUADS)
    glVertex2f(0, 0)
    glVertex2f(WIN_W, 0)
    glVertex2f(WIN_W, WIN_H)
    glVertex2f(0, WIN_H)
    glEnd()
    glDisable(GL_BLEND)
    
    # Title - Top Center
    glColor3f(1.0, 0.2, 0.2)
    title = "GAME OVER"
    title_w = text_width(title, GLUT_BITMAP_HELVETICA_18)
    draw_text(WIN_W/2 - title_w/2, WIN_H - 50, title, GLUT_BITMAP_HELVETICA_18)
    
    # Restart prompt - Below title, centered
    glColor3f(0.5, 1.0, 0.5)
    restart_text = "Press R to Restart"
    restart_w = text_width(restart_text)
    draw_text(WIN_W/2 - restart_w/2, WIN_H - 80, restart_text)
    
    # Stats box - Center of screen
    box_w = 400
    box_h = 280
    box_x = WIN_W / 2 - box_w / 2
    box_y = WIN_H / 2 - box_h / 2
    
    glColor3f(0.2, 0.2, 0.3)
    glBegin(GL_QUADS)
    glVertex2f(box_x, box_y)
    glVertex2f(box_x + box_w, box_y)
    glVertex2f(box_x + box_w, box_y + box_h)
    glVertex2f(box_x, box_y + box_h)
    glEnd()
    
    glColor3f(0.5, 0.5, 0.6)
    glLineWidth(3.0)
    glBegin(GL_LINE_LOOP)
    glVertex2f(box_x, box_y)
    glVertex2f(box_x + box_w, box_y)
    glVertex2f(box_x + box_w, box_y + box_h)
    glVertex2f(box_x, box_y + box_h)
    glEnd()
    
    # Stats
    glColor3f(1.0, 1.0, 1.0)
    line_h = 25
    start_y = box_y + box_h - 30
    
    draw_text(box_x + 20, start_y, f"Final Score: {last_round_score}")
    draw_text(box_x + 20, start_y - line_h, f"Enemies Killed: {enemy_kills_total}")
    draw_text(box_x + 20, start_y - line_h*2, f"Rocks Destroyed: {rocks_destroyed}")
    draw_text(box_x + 20, start_y - line_h*3, f"Final Ship Level: {ship_level}")
    draw_text(box_x + 20, start_y - line_h*4, f"Final Gun Level: {gun_level}")
    draw_text(box_x + 20, start_y - line_h*5, f"Difficulty: {difficulty}")
    
    # Leaderboard
    glColor3f(1.0, 0.8, 0.2)
    draw_text(box_x + 20, start_y - line_h*7, "TOP 5 SCORES:")
    
    glColor3f(0.8, 0.8, 1.0)
    for i, score in enumerate(top5_scores):
        rank_text = f"{i+1}. {score}"
        draw_text(box_x + 40, start_y - line_h*(8+i), rank_text)
    
    _end_2d_overlay()

def draw_minimap():
    if game_over:
        return
    
    _begin_2d_overlay()
    
    # Minimap settings
    map_size = 180
    map_x = WIN_W - map_size - 15
    map_y = 15
    
    # Background
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    glColor4f(0.0, 0.0, 0.0, 0.6)
    glBegin(GL_QUADS)
    glVertex2f(map_x, map_y)
    glVertex2f(map_x + map_size, map_y)
    glVertex2f(map_x + map_size, map_y + map_size)
    glVertex2f(map_x, map_y + map_size)
    glEnd()
    
    # Border
    glColor4f(0.3, 0.6, 0.8, 0.8)
    glLineWidth(2.0)
    glBegin(GL_LINE_LOOP)
    glVertex2f(map_x, map_y)
    glVertex2f(map_x + map_size, map_y)
    glVertex2f(map_x + map_size, map_y + map_size)
    glVertex2f(map_x, map_y + map_size)
    glEnd()
    
    # Scale world to minimap
    world_size = WORLD_MAX - WORLD_MIN
    scale = map_size / world_size
    
    def world_to_map(wx, wy):
        mx = map_x + (wx - WORLD_MIN) * scale
        my = map_y + (wy - WORLD_MIN) * scale
        return mx, my
    
    # Draw black holes
    glPointSize(6.0)
    glBegin(GL_POINTS)
    for bh in black_holes:
        bx, by, _ = bh["pos"]
        mx, my = world_to_map(bx, by)
        glColor4f(0.5, 0.0, 0.5, 0.9)
        glVertex2f(mx, my)
    glEnd()
    
    # Draw white holes
    glPointSize(6.0)
    glBegin(GL_POINTS)
    for wh in white_holes:
        wx, wy, _ = wh["pos"]
        mx, my = world_to_map(wx, wy)
        glColor4f(0.9, 0.9, 1.0, 0.9)
        glVertex2f(mx, my)
    glEnd()
    
    # Draw enemies
    glPointSize(4.0)
    glBegin(GL_POINTS)
    for e in enemies:
        ex, ey = e[0], e[1]
        mx, my = world_to_map(ex, ey)
        glColor4f(1.0, 0.3, 0.3, 0.9)
        glVertex2f(mx, my)
    glEnd()
    
    # Draw player
    px, py = world_to_map(player_x, player_y)
    glPointSize(8.0)
    glBegin(GL_POINTS)
    glColor4f(0.2, 1.0, 0.2, 1.0)
    glVertex2f(px, py)
    glEnd()
    
    # Draw player direction
    rad = math.radians(player_angle)
    dir_len = 15
    glLineWidth(2.0)
    glBegin(GL_LINES)
    glColor4f(0.2, 1.0, 0.2, 1.0)
    glVertex2f(px, py)
    glVertex2f(px + math.cos(rad) * dir_len, py + math.sin(rad) * dir_len)
    glEnd()
    
    glDisable(GL_BLEND)
    _end_2d_overlay()

def draw_offscreen_indicators():
    if game_over or game_paused:
        return
    
    _begin_2d_overlay()
    
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    
    margin = 30
    
    for e in enemies:
        ex, ey, ez = e[0], e[1], e[2]
        
        # Project to screen - simplified check
        dx = ex - player_x
        dy = ey - player_y
        
        # Check if roughly off-screen (simplified)
        dist = math.sqrt(dx*dx + dy*dy)
        if dist < 500:  # Too close, skip
            continue
        
        angle = math.atan2(dy, dx)
        
        # Calculate indicator position
        screen_angle = angle - math.radians(player_angle)
        
        indicator_dist = 150
        ind_x = WIN_W/2 + math.cos(screen_angle) * indicator_dist
        ind_y = WIN_H/2 + math.sin(screen_angle) * indicator_dist
        
        # Clamp to screen edges
        ind_x = clamp(ind_x, margin, WIN_W - margin)
        ind_y = clamp(ind_y, margin, WIN_H - margin)
        
        # Draw arrow
        arrow_size = 8
        glColor4f(1.0, 0.3, 0.3, 0.7)
        glBegin(GL_TRIANGLES)
        # Point toward enemy
        tip_x = ind_x + math.cos(angle - math.radians(player_angle)) * arrow_size
        tip_y = ind_y + math.sin(angle - math.radians(player_angle)) * arrow_size
        
        base_angle1 = angle - math.radians(player_angle) + 2.5
        base_angle2 = angle - math.radians(player_angle) - 2.5
        
        glVertex2f(tip_x, tip_y)
        glVertex2f(ind_x + math.cos(base_angle1) * arrow_size * 0.5,
                   ind_y + math.sin(base_angle1) * arrow_size * 0.5)
        glVertex2f(ind_x + math.cos(base_angle2) * arrow_size * 0.5,
                   ind_y + math.sin(base_angle2) * arrow_size * 0.5)
        glEnd()
    
    glDisable(GL_BLEND)
    _end_2d_overlay()

def draw_pause_menu():
    if not game_paused:
        return
    
    _begin_2d_overlay()
    
    # Dark overlay
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    glColor4f(0.0, 0.0, 0.0, 0.7)
    glBegin(GL_QUADS)
    glVertex2f(0, 0)
    glVertex2f(WIN_W, 0)
    glVertex2f(WIN_W, WIN_H)
    glVertex2f(0, WIN_H)
    glEnd()
    
    # Title
    glColor3f(1.0, 1.0, 1.0)
    title = "PAUSED"
    title_w = text_width(title, GLUT_BITMAP_HELVETICA_18) * 1.5
    draw_text(WIN_W/2 - title_w/3, WIN_H - 100, title, GLUT_BITMAP_HELVETICA_18)
    
    # Menu box
    box_w = 400
    box_h = 300
    box_x = WIN_W/2 - box_w/2
    box_y = WIN_H/2 - box_h/2
    
    glColor4f(0.15, 0.15, 0.2, 0.95)
    glBegin(GL_QUADS)
    glVertex2f(box_x, box_y)
    glVertex2f(box_x + box_w, box_y)
    glVertex2f(box_x + box_w, box_y + box_h)
    glVertex2f(box_x, box_y + box_h)
    glEnd()
    
    glColor3f(0.4, 0.6, 0.8)
    glLineWidth(3.0)
    glBegin(GL_LINE_LOOP)
    glVertex2f(box_x, box_y)
    glVertex2f(box_x + box_w, box_y)
    glVertex2f(box_x + box_w, box_y + box_h)
    glVertex2f(box_x, box_y + box_h)
    glEnd()
    
    # Menu items
    glColor3f(1.0, 1.0, 1.0)
    line_h = 35
    start_y = box_y + box_h - 50
    
    draw_text(box_x + 30, start_y, "Press P to Resume")
    draw_text(box_x + 30, start_y - line_h, "Press R to Restart")
    draw_text(box_x + 30, start_y - line_h*2, "")
    draw_text(box_x + 30, start_y - line_h*3, "Difficulty Settings:")
    
    # Difficulty options
    difficulties = ["Easy", "Normal", "Hard"]
    for i, diff in enumerate(difficulties):
        y_pos = start_y - line_h*(4+i)
        if diff == difficulty:
            glColor3f(0.3, 1.0, 0.3)
            draw_text(box_x + 50, y_pos, f"[{diff}] <-- CURRENT")
        else:
            glColor3f(0.7, 0.7, 0.7)
            draw_text(box_x + 50, y_pos, f" {diff}")
    
    glColor3f(0.8, 0.8, 0.5)
    draw_text(box_x + 30, start_y - line_h*8, "Press 1=Easy, 2=Normal, 3=Hard")
    
    glDisable(GL_BLEND)
    _end_2d_overlay()

def draw_start_screen():
    _begin_2d_overlay()
    
    # Dark overlay
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    glColor4f(0.0, 0.0, 0.1, 0.95)
    glBegin(GL_QUADS)
    glVertex2f(0, 0)
    glVertex2f(WIN_W, 0)
    glVertex2f(WIN_W, WIN_H)
    glVertex2f(0, WIN_H)
    glEnd()
    
    # Title
    glColor3f(0.3, 0.9, 1.0)
    title = "SINGULARITY WARS"
    title_w = text_width(title, GLUT_BITMAP_HELVETICA_18) * 1.2
    draw_text(WIN_W/2 - title_w/2.5, WIN_H - 80, title, GLUT_BITMAP_HELVETICA_18)
    
    # Menu box
    box_w = 450
    box_h = 380
    box_x = WIN_W/2 - box_w/2
    box_y = WIN_H/2 - box_h/2
    
    glColor4f(0.1, 0.15, 0.25, 0.9)
    glBegin(GL_QUADS)
    glVertex2f(box_x, box_y)
    glVertex2f(box_x + box_w, box_y)
    glVertex2f(box_x + box_w, box_y + box_h)
    glVertex2f(box_x, box_y + box_h)
    glEnd()
    
    glColor3f(0.3, 0.6, 0.9)
    glLineWidth(3.0)
    glBegin(GL_LINE_LOOP)
    glVertex2f(box_x, box_y)
    glVertex2f(box_x + box_w, box_y)
    glVertex2f(box_x + box_w, box_y + box_h)
    glVertex2f(box_x, box_y + box_h)
    glEnd()
    
    # Instructions
    glColor3f(1.0, 1.0, 1.0)
    line_h = 35
    start_y = box_y + box_h - 40
    
    draw_text(box_x + 30, start_y, "SELECT DIFFICULTY:")
    
    # Difficulty options
    difficulties = [
        ("Easy", "60% Enemy Damage, 70% Enemy Speed"),
        ("Normal", "Balanced Gameplay"),
        ("Hard", "150% Enemy Damage, 130% Enemy Speed")
    ]
    
    for i, (diff, desc) in enumerate(difficulties):
        y_pos = start_y - line_h*(1.5+i*2)
        
        if diff == difficulty:
            glColor3f(0.3, 1.0, 0.3)
            draw_text(box_x + 40, y_pos, f"[{diff}]")
            glColor3f(0.7, 0.9, 0.7)
            draw_text(box_x + 60, y_pos - 18, desc)
        else:
            glColor3f(0.7, 0.7, 0.7)
            draw_text(box_x + 40, y_pos, f" {diff}")
            glColor3f(0.5, 0.5, 0.5)
            draw_text(box_x + 60, y_pos - 18, desc)
    
    # Controls inside box
    glColor3f(0.9, 0.9, 0.5)
    control_text = "Press 1 = Easy  |  2 = Normal  |  3 = Hard"
    control_w = text_width(control_text)
    draw_text(box_x + (box_w - control_w)/2, box_y + 30, control_text)
    
    # Start prompt below box
    glColor3f(0.5, 1.0, 0.5)
    start_text = "Press SPACE or ENTER to Start Game"
    start_w = text_width(start_text)
    draw_text(WIN_W/2 - start_w/2, box_y - 40, start_text)
    
    glDisable(GL_BLEND)
    _end_2d_overlay()


#Display
def showScreen():
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    glLoadIdentity()
    glViewport(0, 0, WIN_W, WIN_H)

    if not game_started:
        draw_start_screen()
        glutSwapBuffers()
        return

    setupCamera()

    draw_stars()
    draw_space_debris()
    draw_gravitational_lensing()
    draw_black_holes()
    draw_bh_pull_particles()
    draw_white_holes()
    draw_wh_push_particles()
    draw_wormholes()
    draw_wormhole_vortex_particles()
    draw_rocks()
    draw_enemies()
    draw_enemy_warning_indicators()
    draw_enemy_bullets()
    draw_player_bullets()
    draw_bullet_trails()
    draw_muzzle_flashes()
    draw_engine_particles()
    draw_explosion_particles()
    draw_levelup_particles()
    draw_speed_lines()

    if not first_person:
        draw_ship_third_person()
    else:
        draw_first_person_helm_and_hands()
    
    draw_shield()
    draw_health_bar()
    draw_hud()
    draw_minimap()
    draw_offscreen_indicators()
    draw_damage_flash()
    draw_pause_menu()
    glutSwapBuffers()

def idle():
    global player_x, player_y, player_z
    global vel_x, vel_y, vel_z, player_angle
    global player_life
    global player_bullet_cd
    global wormhole_tp_cd
    global damage_flash_frames, shield_pulse_frames

    if not game_started:
        glutPostRedisplay()
        return

    if damage_flash_frames > 0:
        damage_flash_frames -= 1
    if shield_pulse_frames > 0:
        shield_pulse_frames -= 1

    if game_paused:
        glutPostRedisplay()
        return

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
    
    _spawn_engine_particles()
    _update_engine_particles()
    
    _spawn_bh_pull_particles()
    _update_bh_pull_particles()
    
    _spawn_wh_push_particles()
    _update_wh_push_particles()
    
    _update_explosion_particles()
    _update_muzzle_flashes()
    _spawn_bullet_trails()
    _update_bullet_trails()
    _update_levelup_particles()
    
    _update_space_debris()
    _spawn_wormhole_vortex_particles()
    _update_wormhole_vortex_particles()
    _update_speed_lines()

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
    global game_paused
    global game_started

    wormhole_tp_cd = 0
    _scoreboard_locked = False
    game_paused = False
    game_started = True  # Keep game started after restart

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
    engine_particles.clear()
    bh_pull_particles.clear()
    wh_push_particles.clear()
    explosion_particles.clear()
    muzzle_flashes.clear()
    bullet_trails.clear()
    levelup_particles.clear()
    wormhole_vortex_particles.clear()
    speed_lines.clear()

    init_rocks()
    init_black_holes()
    init_white_holes()
    init_wormholes()
    init_enemies()
    init_stars()
    init_space_debris()

def keyboardListener(key, x, y):
    global first_person, controls_disabled, game_paused, difficulty, game_started
    try:
        k = key.decode("utf-8").lower()
    except:
        return

    # Start screen handling
    if not game_started:
        if k in ['1', '2', '3']:
            if k == '1':
                difficulty = "Easy"
            elif k == '2':
                difficulty = "Normal"
            elif k == '3':
                difficulty = "Hard"
            return
        elif k == ' ' or k == '\r':  # Space or Enter
            game_started = True
            return
        return

    if k == 'r':
        reset_game()
        return
    
    if k == 'p':
        game_paused = not game_paused
        return
    
    # Difficulty change (only when paused or game over)
    if (game_paused or game_over) and k in ['1', '2', '3']:
        if k == '1':
            difficulty = "Easy"
        elif k == '2':
            difficulty = "Normal"
        elif k == '3':
            difficulty = "Hard"
        return

    if k == 'v':
        first_person = not first_person
        return

    if k == ' ':
        _spawn_player_bullet()
        return

    if controls_disabled or game_paused:
        return

    if k in keys:
        keys[k] = True

def keyboardUpListener(key, x, y):
    global controls_disabled
    try:
        k = key.decode("utf-8").lower()
    except:
        return

    if controls_disabled or game_paused:
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
    init_stars()
    init_space_debris()

    glutDisplayFunc(showScreen)
    glutIdleFunc(idle)
    glutKeyboardFunc(keyboardListener)
    glutKeyboardUpFunc(keyboardUpListener)
    glutMouseFunc(mouseListener)
    glutReshapeFunc(reshape)

    glutMainLoop()

if __name__ == "__main__":
    main()