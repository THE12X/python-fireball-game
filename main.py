import math
import random
import sys
import numpy as np
import pygame

# Initialize Pygame and Mixer
pygame.init()
pygame.mixer.init(frequency=44100, size=-16, channels=2)

# --- CONFIGURATION ---
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
FPS = 60
TOTAL_GAME_TIME_FRAMES = 300 * FPS  # 5 Minutes (300 seconds) to reach Earth

# Setup Display
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("MRX Fireball")
clock = pygame.time.Clock()

# Fonts
font_title = pygame.font.SysFont("Verdana", 42, bold=True)
font_subtitle = pygame.font.SysFont("Verdana", 20, bold=True)
font_ui = pygame.font.SysFont("Consolas", 16, bold=True)
font_pause = pygame.font.SysFont("Verdana", 36, bold=True)

# Audio Mute State
is_muted = False

# --- PROCEDURAL SOUND SYNTHESIZER ---
def generate_sound(freq_start, freq_end, duration, wave_type="sine", volume=0.3):
    """Generates a procedural audio effect without needing external sound files."""
    sample_rate = 44100
    num_samples = int(sample_rate * duration)
    t = np.linspace(0, duration, num_samples, False)
    freq = np.linspace(freq_start, freq_end, num_samples)

    if wave_type == "sine":
        wave = np.sin(2 * np.pi * freq * t)
    elif wave_type == "square":
        wave = np.sign(np.sin(2 * np.pi * freq * t))
    elif wave_type == "noise":
        wave = np.random.uniform(-1, 1, num_samples)
    else:
        wave = np.sin(2 * np.pi * freq * t)

    fade_out = np.linspace(1.0, 0.0, num_samples)
    audio = (wave * fade_out * volume * 32767).astype(np.int16)
    stereo_audio = np.column_stack((audio, audio))
    return pygame.sndarray.make_sound(stereo_audio)

# Pre-generate Sound Effects
sfx_crash = generate_sound(160, 40, 0.18, wave_type="noise", volume=0.35)
sfx_gold = generate_sound(450, 900, 0.30, wave_type="sine", volume=0.45)
sfx_rogue = generate_sound(220, 660, 0.45, wave_type="square", volume=0.35)
sfx_gameover = generate_sound(280, 50, 0.70, wave_type="sine", volume=0.50)
sfx_victory = generate_sound(523, 1046, 1.10, wave_type="sine", volume=0.50)

# --- PARALLAX STARFIELD SETUP ---
stars = []
for _ in range(110):
    stars.append({
        "x": random.randint(0, SCREEN_WIDTH),
        "y": random.randint(0, SCREEN_HEIGHT),
        "size": random.choice([1, 1, 2, 3]),
        "layer": random.choice([0.2, 0.5, 1.0]),
        "color": random.choice([(180, 200, 255), (255, 255, 255), (255, 220, 180)])
    })

# --- PLANET DEFINITIONS ---
PLANET_TYPES = [
    {
        "type": "asteroid",
        "radius_range": (14, 18),
        "color": (100, 95, 90),       # Deep Grey Asteroid
        "accent": (60, 55, 50),
        "min_heat": 0,
        "detail": "craters",
        "tier": 1
    },
    {
        "type": "ice_crystal",
        "radius_range": (18, 24),
        "color": (240, 245, 255),     # Pure White / Ice Blue
        "accent": (140, 210, 250),
        "min_heat": 0,
        "detail": "spikes",
        "tier": 1
    },
    {
        "type": "acid_world",
        "radius_range": (24, 32),
        "color": (30, 190, 60),       # Emerald Green
        "accent": (15, 90, 25),
        "min_heat": 25,
        "detail": "swirls",
        "tier": 2
    },
    {
        "type": "gas_giant",
        "radius_range": (38, 48),
        "color": (140, 75, 30),       # Rust Brown
        "accent": (190, 120, 50),
        "min_heat": 45,
        "detail": "rings",
        "tier": 2
    },
    {
        "type": "crimson_star",       # Dark Crimson Red
        "radius_range": (32, 40),
        "color": (130, 15, 30),
        "accent": (190, 60, 10),
        "min_heat": 65,
        "detail": "solar_flares",
        "tier": 3
    },
    {
        "type": "black_hole",
        "radius_range": (36, 44),
        "color": (10, 10, 18),        # Pitch Black Void
        "accent": (90, 25, 160),
        "min_heat": 85,
        "detail": "event_horizon",
        "tier": 3
    },
]

# --- GAME STATES ---
STATE_MENU = 0
STATE_PLAYING = 1
STATE_PAUSED = 2
STATE_GAMEOVER = 3
STATE_WIN_SEQUENCE = 4
STATE_VICTORY = 5
game_state = STATE_MENU

# --- RESET GAME STATE ---
def reset_game():
    global player_x, player_y, heat, player_radius, core_angle
    global planets, spaceships, wormholes, particles, score, spawn_timer, ship_spawn_timer, wormhole_timer, grace_period
    global rogue_mode_timer, slowdown_debuff_timer, game_progress_frames, earth_y, earth_exploded

    player_x = SCREEN_WIDTH // 2
    player_y = SCREEN_HEIGHT - 100
    heat = 80.0
    player_radius = 22
    core_angle = 0.0

    planets = []
    spaceships = []
    wormholes = []
    particles = []
    score = 0
    spawn_timer = 0
    ship_spawn_timer = 0
    wormhole_timer = 0
    grace_period = 180          # 3 seconds setup grace period
    rogue_mode_timer = 0        # Rogue Mode Timer
    slowdown_debuff_timer = 0   # Wormhole Slowdown Timer
    game_progress_frames = 0    # Progress tracker
    earth_y = -180              # Y position for Earth arrival
    earth_exploded = False

reset_game()

def spawn_planet():
    if random.random() < 0.15 and score > 200:
        radius = random.randint(22, 28)
        x = random.randint(radius, SCREEN_WIDTH - radius)
        planets.append({
            "x": x,
            "y": -radius - 20,
            "radius": radius,
            "spec": {
                "type": "golden_planet",
                "color": (255, 215, 0),
                "accent": (255, 255, 180),
                "min_heat": 0,
                "detail": "golden"
            },
            "angle": 0
        })
        return

    if game_progress_frames < 60 * FPS:
        available_specs = [p for p in PLANET_TYPES if p["tier"] == 1]
    elif game_progress_frames < 180 * FPS:
        available_specs = [p for p in PLANET_TYPES if p["tier"] <= 2]
    else:
        available_specs = PLANET_TYPES

    p_spec = random.choice(available_specs)
    radius = random.randint(*p_spec["radius_range"])
    x = random.randint(radius, SCREEN_WIDTH - radius)
    y = -radius - 20
    planets.append({
        "x": x,
        "y": y,
        "radius": radius,
        "spec": p_spec,
        "angle": random.uniform(0, 360)
    })

def spawn_spaceship():
    direction = random.choice([-1, 1])
    x = -30 if direction == 1 else SCREEN_WIDTH + 30
    y = random.randint(100, SCREEN_HEIGHT - 250)
    vx = direction * random.uniform(4.0, 7.0)
    spaceships.append({
        "x": x,
        "y": y,
        "vx": vx,
        "radius": 18,
        "color": (220, 30, 30) if direction == 1 else (30, 200, 160)
    })

def spawn_wormhole():
    radius = random.randint(30, 40)
    x = random.randint(radius, SCREEN_WIDTH - radius)
    wormholes.append({
        "x": x,
        "y": -radius - 30,
        "radius": radius,
        "rotation": 0.0
    })

# --- MAIN LOOP ---
running = True
while running:
    # 1. EVENT HANDLING
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        if event.type == pygame.KEYDOWN:
            # Mute / Unmute Audio Toggle
            if event.key == pygame.K_m:
                is_muted = not is_muted
                new_volume = 0.0 if is_muted else 1.0
                sfx_crash.set_volume(new_volume * 0.35)
                sfx_gold.set_volume(new_volume * 0.45)
                sfx_rogue.set_volume(new_volume * 0.35)
                sfx_gameover.set_volume(new_volume * 0.50)
                sfx_victory.set_volume(new_volume * 0.50)

            if event.key == pygame.K_SPACE:
                if game_state in (STATE_MENU, STATE_GAMEOVER, STATE_VICTORY):
                    reset_game()
                    game_state = STATE_PLAYING

            if event.key == pygame.K_p:
                if game_state == STATE_PLAYING:
                    game_state = STATE_PAUSED
                elif game_state == STATE_PAUSED:
                    game_state = STATE_PLAYING

            if game_state == STATE_PAUSED:
                if event.key == pygame.K_c:
                    game_state = STATE_PLAYING
                elif event.key == pygame.K_r:
                    reset_game()
                    game_state = STATE_PLAYING

    # 2. GAME LOGIC UPDATES
    if game_state == STATE_PLAYING:
        game_progress_frames += 1

        if game_progress_frames >= TOTAL_GAME_TIME_FRAMES:
            game_state = STATE_WIN_SEQUENCE

        # Grace Period / Accelerated Heat Decay
        if grace_period > 0:
            grace_period -= 1
        else:
            heat -= 0.55  # Accelerated cooldown rate

        if heat <= 0:
            heat = 0
            sfx_gameover.play()
            game_state = STATE_GAMEOVER

        core_angle += 0.08

        # ROGUE MODE Buff & Color Handling
        score_multiplier = 1
        if rogue_mode_timer > 0:
            rogue_mode_timer -= 1
            score_multiplier = 2
            fireball_color = (255, 30, 30)
            aura_color = (200, 10, 10)
            core_highlight = (255, 120, 120)
            speed_boost = 4.0
        else:
            fireball_color = (255, 120, 0)
            aura_color = (255, 90, 0)
            core_highlight = (255, 170, 40)
            speed_boost = 0.0

        player_radius = int(18 + (heat / 100.0) * 16)

        # Speeds
        base_steering = 8.5 + speed_boost
        base_scroll = 6.0 + (speed_boost * 0.5)

        # Wormhole Slowdown Logic
        for wh in wormholes:
            dx = player_x - wh["x"]
            dy = player_y - wh["y"]
            if math.hypot(dx, dy) < (player_radius + wh["radius"] + 25):
                slowdown_debuff_timer = 5 * FPS
                break

        if slowdown_debuff_timer > 0:
            slowdown_debuff_timer -= 1
            speed_factor = 0.5
        else:
            speed_factor = 1.0

        steering_speed = base_steering * speed_factor
        world_scroll_speed = base_scroll * speed_factor

        # Controls
        keys = pygame.key.get_pressed()
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            player_x -= steering_speed
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            player_x += steering_speed

        player_x = max(player_radius, min(SCREEN_WIDTH - player_radius, player_x))

        # Starfield Motion
        for star in stars:
            star["y"] += world_scroll_speed * 0.2 * star["layer"]
            if star["y"] > SCREEN_HEIGHT:
                star["y"] = 0
                star["x"] = random.randint(0, SCREEN_WIDTH)

        # Particle Tail Generator
        for _ in range(int(2 + (heat / 15.0))):
            p_size = random.uniform(4, 5 + (player_radius * 0.35))
            p_offset_x = random.uniform(-player_radius * 0.6, player_radius * 0.6)
            
            if rogue_mode_timer > 0:
                p_color = random.choice([(255, 40, 40), (220, 10, 10), (255, 80, 80)])
            else:
                p_color = random.choice([(255, 100, 0), (255, 70, 0), (255, 130, 10)])

            particles.append({
                "x": player_x + p_offset_x,
                "y": player_y + (player_radius * 0.4),
                "vx": random.uniform(-1.8, 1.8),
                "vy": random.uniform(3, 6),
                "radius": p_size,
                "color": p_color,
                "life": 1.0
            })

        # Update Flame Particles
        for p in particles[:]:
            p["x"] += p["vx"]
            p["y"] += p["vy"]
            p["radius"] *= 0.90
            p["life"] -= 0.05
            if p["life"] <= 0 or p["radius"] < 0.5:
                particles.remove(p)

        # Entity Spawning
        spawn_timer += 1
        if spawn_timer >= max(20, 45 - int(heat / 2.0)):
            spawn_planet()
            spawn_timer = 0

        ship_spawn_timer += 1
        if ship_spawn_timer >= 220:
            spawn_spaceship()
            ship_spawn_timer = 0

        wormhole_timer += 1
        if wormhole_timer >= 280:
            spawn_wormhole()
            wormhole_timer = 0

        # Update Wormholes
        for wh in wormholes[:]:
            wh["y"] += world_scroll_speed
            wh["rotation"] += 0.05
            if wh["y"] - wh["radius"] > SCREEN_HEIGHT + 50:
                wormholes.remove(wh)

        # Update Spaceships
        for ship in spaceships[:]:
            ship["x"] += ship["vx"]
            dx = player_x - ship["x"]
            dy = player_y - ship["y"]
            if math.hypot(dx, dy) < (player_radius + ship["radius"]):
                heat = min(100.0, heat + 25)
                score += 500 * score_multiplier
                sfx_crash.play()
                for _ in range(15):
                    particles.append({
                        "x": ship["x"], "y": ship["y"],
                        "vx": random.uniform(-5, 5), "vy": random.uniform(-5, 5),
                        "radius": random.uniform(3, 7), "color": (255, 120, 0), "life": 0.8
                    })
                spaceships.remove(ship)
                continue

            if ship["x"] < -50 or ship["x"] > SCREEN_WIDTH + 50:
                spaceships.remove(ship)

        # Update Planets & Collisions
        for planet in planets[:]:
            planet["y"] += world_scroll_speed
            dx = player_x - planet["x"]
            dy = player_y - planet["y"]
            dist = math.hypot(dx, dy)

            if dist < (player_radius + planet["radius"]):
                if rogue_mode_timer > 0 or heat >= planet["spec"]["min_heat"]:
                    if planet["spec"]["type"] == "golden_planet":
                        rogue_mode_timer = 15 * FPS
                        heat = min(100.0, heat + 35)
                        sfx_gold.play()
                        sfx_rogue.play()
                    else:
                        heat_gain = planet["radius"] * 0.90
                        heat = min(100.0, heat + heat_gain)
                        sfx_crash.play()

                    score += int(planet["radius"] * 20 * score_multiplier)
                    
                    for _ in range(14):
                        particles.append({
                            "x": planet["x"], "y": planet["y"],
                            "vx": random.uniform(-5, 5), "vy": random.uniform(-5, 5),
                            "radius": random.uniform(3, 8), "color": planet["spec"]["color"], "life": 0.8
                        })
                    planets.remove(planet)
                else:
                    sfx_gameover.play()
                    game_state = STATE_GAMEOVER
                continue

            if planet["y"] - planet["radius"] > SCREEN_HEIGHT + 50:
                planets.remove(planet)

        score += 1 * score_multiplier

    # 3. WIN SEQUENCE LOGIC
    elif game_state == STATE_WIN_SEQUENCE:
        if earth_y < 220:
            earth_y += 2.5
        else:
            if not earth_exploded:
                earth_exploded = True
                sfx_victory.play()
                for _ in range(80):
                    particles.append({
                        "x": player_x,
                        "y": player_y,
                        "vx": random.uniform(-9, 9),
                        "vy": random.uniform(-9, 9),
                        "radius": random.uniform(4, 12),
                        "color": random.choice([(255, 30, 30), (255, 120, 0), (255, 220, 50)]),
                        "life": 1.5
                    })

        for p in particles[:]:
            p["x"] += p["vx"]
            p["y"] += p["vy"]
            p["radius"] *= 0.94
            p["life"] -= 0.02
            if p["life"] <= 0 or p["radius"] < 0.5:
                particles.remove(p)

        if earth_exploded and len(particles) == 0:
            game_state = STATE_VICTORY

    # 4. RENDER / GRAPHICS
    screen.fill((6, 6, 14))

    # Render Stars
    for star in stars:
        s_color = (min(255, star["color"][0]), min(255, star["color"][1]), min(255, star["color"][2]))
        pygame.draw.circle(screen, s_color, (int(star["x"]), int(star["y"])), star["size"])

    if game_state in (STATE_PLAYING, STATE_PAUSED, STATE_GAMEOVER, STATE_WIN_SEQUENCE, STATE_VICTORY):
        # Render Flame Particles
        for p in particles:
            pygame.draw.circle(screen, p["color"], (int(p["x"]), int(p["y"])), int(p["radius"]))

        # Render Wormholes
        for wh in wormholes:
            wx, wy = int(wh["x"]), int(wh["y"])
            wr = wh["radius"]
            pygame.draw.circle(screen, (80, 20, 140), (wx, wy), wr + 6, 3)
            pygame.draw.circle(screen, (30, 0, 60), (wx, wy), wr)
            for i in range(4):
                ang = wh["rotation"] + (i * math.pi / 2)
                rx = wx + int(math.cos(ang) * (wr * 0.6))
                ry = wy + int(math.sin(ang) * (wr * 0.6))
                pygame.draw.circle(screen, (180, 80, 255), (rx, ry), 4)

        # Render Spaceships
        for ship in spaceships:
            sx, sy = int(ship["x"]), int(ship["y"])
            pygame.draw.polygon(screen, ship["color"], [(sx + 15, sy), (sx - 10, sy - 8), (sx - 10, sy + 8)])
            pygame.draw.circle(screen, (255, 200, 150), (sx, sy), 4)

        # Render Planets
        for planet in planets:
            px, py = int(planet["x"]), int(planet["y"])
            pr = planet["radius"]
            spec = planet["spec"]

            if spec["type"] == "golden_planet":
                pygame.draw.circle(screen, (255, 255, 180), (px, py), pr + 4, 2)
                pygame.draw.circle(screen, spec["color"], (px, py), pr)
            elif spec["type"] == "black_hole":
                pygame.draw.circle(screen, (10, 10, 18), (px, py), pr)
            elif spec["type"] == "crimson_star":
                pygame.draw.circle(screen, spec["color"], (px, py), pr)
                pygame.draw.circle(screen, spec["accent"], (px, py), max(2, pr // 2))
            elif spec["detail"] == "rings":
                pygame.draw.ellipse(screen, spec["accent"], (px - int(pr * 1.7), py - int(pr * 0.3), int(pr * 3.4), int(pr * 0.6)))
                pygame.draw.circle(screen, spec["color"], (px, py), pr)
            else:
                pygame.draw.circle(screen, spec["color"], (px, py), pr)
                if spec["detail"] == "craters":
                    pygame.draw.circle(screen, spec["accent"], (px - int(pr * 0.3), py - int(pr * 0.2)), max(2, pr // 4))
                elif spec["detail"] == "spikes":
                    pygame.draw.line(screen, spec["accent"], (px - pr, py), (px + pr, py), 3)
                elif spec["detail"] == "swirls":
                    pygame.draw.circle(screen, spec["accent"], (px + int(pr * 0.2), py), max(3, pr // 3))

        # Render Earth during Win Sequence
        if game_state in (STATE_WIN_SEQUENCE, STATE_VICTORY):
            e_x, e_y = SCREEN_WIDTH // 2, int(earth_y)
            pygame.draw.circle(screen, (40, 120, 220), (e_x, e_y), 110)
            pygame.draw.circle(screen, (60, 180, 80), (e_x - 30, e_y - 20), 40)
            pygame.draw.circle(screen, (60, 180, 80), (e_x + 20, e_y + 30), 35)
            pygame.draw.circle(screen, (255, 255, 255), (e_x, e_y - 85), 25)
            pygame.draw.circle(screen, (100, 180, 255), (e_x, e_y), 116, 4)

        # Render Fireball Player
        if not earth_exploded:
            px_i, py_i = int(player_x), int(player_y)
            aura_rad = player_radius + int(6 + math.sin(core_angle * 3) * 3)
            pygame.draw.circle(screen, aura_color, (px_i, py_i), aura_rad)
            pygame.draw.circle(screen, fireball_color, (px_i, py_i), player_radius)
            pygame.draw.circle(screen, core_highlight, (px_i, py_i), max(4, player_radius // 2))

        # --- HUD OVERLAY ---
        pygame.draw.rect(screen, (15, 15, 28), (15, 15, 250, 130), border_radius=10)
        pygame.draw.rect(screen, (60, 60, 90), (15, 15, 250, 130), width=2, border_radius=10)

        # 1. HEAT PROGRESS BAR
        pygame.draw.rect(screen, (40, 15, 15), (25, 42, 230, 14), border_radius=4)
        heat_bar_w = int((heat / 100.0) * 230)
        if heat_bar_w > 0:
            pygame.draw.rect(screen, (255, min(255, int(heat * 2.55)), 30), (25, 42, heat_bar_w, 14), border_radius=4)
        pygame.draw.rect(screen, (120, 120, 150), (25, 42, 230, 14), width=1, border_radius=4)

        # 2. JOURNEY PROGRESS BAR
        pygame.draw.rect(screen, (15, 30, 45), (25, 82, 230, 12), border_radius=4)
        prog_ratio = min(1.0, game_progress_frames / TOTAL_GAME_TIME_FRAMES)
        journey_bar_w = int(prog_ratio * 230)
        if journey_bar_w > 0:
            pygame.draw.rect(screen, (50, 200, 255), (25, 82, journey_bar_w, 12), border_radius=4)
        pygame.draw.rect(screen, (100, 150, 200), (25, 82, 230, 12), width=1, border_radius=4)

        for cp in [0.25, 0.50, 0.75]:
            cp_x = 25 + int(cp * 230)
            pygame.draw.line(screen, (255, 255, 255), (cp_x, 80), (cp_x, 96), 2)

        pygame.draw.circle(screen, (60, 220, 100), (255, 88), 5)

        heat_lbl_str = "BOOSTING..." if grace_period > 0 else f"HEAT: {int(heat)}%"
        heat_lbl = font_ui.render(heat_lbl_str, True, (255, 255, 255))
        journey_lbl = font_ui.render(f"EARTH DISTANCE: {int(prog_ratio * 100)}%", True, (180, 220, 255))
        
        # Mute status indicator on HUD
        mute_suffix = " [MUTED]" if is_muted else ""
        score_lbl = font_ui.render(f"SCORE: {score}{mute_suffix}", True, (255, 80, 80) if is_muted else (200, 220, 255))

        screen.blit(heat_lbl, (25, 22))
        screen.blit(journey_lbl, (25, 62))
        screen.blit(score_lbl, (25, 102))

        if rogue_mode_timer > 0:
            secs_left = int(rogue_mode_timer / FPS) + 1
            buff_lbl = font_ui.render(f"ROGUE MODE: {secs_left}s", True, (255, 60, 60))
            screen.blit(buff_lbl, (25, 122))
        elif slowdown_debuff_timer > 0:
            secs_left = int(slowdown_debuff_timer / FPS) + 1
            slow_lbl = font_ui.render(f"SLOWED: {secs_left}s", True, (180, 80, 255))
            screen.blit(slow_lbl, (25, 122))

    # --- STATE OVERLAYS ---
    if game_state == STATE_PAUSED:
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 170))
        screen.blit(overlay, (0, 0))

        p_text = font_pause.render("GAME PAUSED", True, (255, 255, 255))
        opt_continue = font_subtitle.render("Press 'C' or 'P' to Continue", True, (100, 230, 100))
        opt_restart = font_subtitle.render("Press 'R' to Restart", True, (255, 100, 100))

        screen.blit(p_text, (SCREEN_WIDTH // 2 - p_text.get_width() // 2, 220))
        screen.blit(opt_continue, (SCREEN_WIDTH // 2 - opt_continue.get_width() // 2, 290))
        screen.blit(opt_restart, (SCREEN_WIDTH // 2 - opt_restart.get_width() // 2, 330))

    elif game_state == STATE_MENU:
        title = font_title.render("MRX FIREBALL", True, (255, 100, 0))
        sub = font_subtitle.render("5-Minute Cosmic Survival Journey", True, (200, 220, 255))
        prompt = font_subtitle.render("Press SPACE to Play", True, (255, 255, 255))
        info1 = font_ui.render("Use A/D or Arrow Keys to Steer | 'P' to Pause | 'M' to Mute", True, (160, 160, 160))
        info2 = font_ui.render("Smash Gold Planets for ROGUE MODE & Speed Boosts", True, (255, 215, 0))
        info3 = font_ui.render("Reach 100% Earth Distance to Win!", True, (100, 220, 255))

        screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, 160))
        screen.blit(sub, (SCREEN_WIDTH // 2 - sub.get_width() // 2, 220))
        screen.blit(prompt, (SCREEN_WIDTH // 2 - prompt.get_width() // 2, 290))
        screen.blit(info1, (SCREEN_WIDTH // 2 - info1.get_width() // 2, 360))
        screen.blit(info2, (SCREEN_WIDTH // 2 - info2.get_width() // 2, 395))
        screen.blit(info3, (SCREEN_WIDTH // 2 - info3.get_width() // 2, 430))

    elif game_state == STATE_GAMEOVER:
        over = font_title.render("FIREBALL EXTINGUISHED", True, (255, 60, 60))
        final_score = font_subtitle.render(f"Final Score: {score}", True, (255, 255, 255))
        restart = font_subtitle.render("Press SPACE to Restart", True, (160, 160, 160))

        screen.blit(over, (SCREEN_WIDTH // 2 - over.get_width() // 2, 200))
        screen.blit(final_score, (SCREEN_WIDTH // 2 - final_score.get_width() // 2, 280))
        screen.blit(restart, (SCREEN_WIDTH // 2 - restart.get_width() // 2, 340))

    elif game_state == STATE_VICTORY:
        vic = font_title.render("EARTH REACHED!", True, (100, 230, 100))
        sub_vic = font_subtitle.render("VICTORY - EARTH SAVED", True, (255, 215, 0))
        final_score = font_subtitle.render(f"Final Score: {score}", True, (255, 255, 255))
        restart = font_subtitle.render("Press SPACE to Play Again", True, (180, 180, 180))

        screen.blit(vic, (SCREEN_WIDTH // 2 - vic.get_width() // 2, 320))
        screen.blit(sub_vic, (SCREEN_WIDTH // 2 - sub_vic.get_width() // 2, 380))
        screen.blit(final_score, (SCREEN_WIDTH // 2 - final_score.get_width() // 2, 430))
        screen.blit(restart, (SCREEN_WIDTH // 2 - restart.get_width() // 2, 480))

    pygame.display.flip()
    clock.tick(FPS)

pygame.quit()
sys.exit()
