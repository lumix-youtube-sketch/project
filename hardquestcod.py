import arcade
import random
import math
import time
import os
from PIL import Image

# настройки
SCREEN_TITLE = "Hard Quest"
BLOCK_SIZE = 128
PLAYER_START_HP = 100
PLAYER_DAMAGE = 55
PLAYER_SPEED = 9
PLAYER_JUMP_SPEED = 30
GRAVITY = 1.3
INVULNERABILITY_TIME = 1.0
ATTACK_RANGE = 240
ATTACK_DURATION = 0.5
ENEMY_DAMAGE = 15
ENEMY_SPEED = 3.5
GHOST_HP = 80
GHOST_SPEED = 3.0
GHOST_SHOOT_DELAY = 7.0
PROJECTILE_SPEED = 7
PROJECTILE_DAMAGE = 8
PROJECTILE_GRAVITY = 0.08
BOSS_HP = 1300
BOSS_NORMAL_SPEED = 2.5
BOSS_DASH_SPEED = 8.5
BOSS_PROJECTILE_DAMAGE = 5
BOSS_COLLISION_DAMAGE = 8

# режимы
STATE_MENU = 0
STATE_COUNTDOWN = 1
STATE_GAME = 2
STATE_GAME_OVER = 3
STATE_WIN = 4
STATE_PAUSE = 5


def prepare_texture(filename, mirror=False, should_clean_bg=True):
    # если файла нет даем квадрат
    if not os.path.exists(filename):
        return arcade.make_soft_square_texture(64, arcade.color.GRAY)

    if not should_clean_bg:
        return arcade.load_texture(filename)

    try:
        # чистим фон
        raw_image = Image.open(filename).convert("RGBA")
        pixels = raw_image.load()
        w, h = raw_image.size

        for y in range(h):
            for x in range(w):
                r, g, b, a = pixels[x, y]
                if r > 235 and g > 230 and b > 230:
                    pixels[x, y] = (255, 255, 255, 0)

        image_box = raw_image.getbbox()
        if image_box:
            raw_image = raw_image.crop(image_box)

        if mirror:
            raw_image = raw_image.transpose(Image.FLIP_LEFT_RIGHT)

        return arcade.Texture(raw_image)

    except:
        return arcade.make_soft_square_texture(64, arcade.color.GRAY)


class GhostEnemy(arcade.Sprite):
    def __init__(self, texture, scale):
        super().__init__(texture, scale)
        self.hp = GHOST_HP
        self.last_shoot_time = time.time() + random.uniform(0, 5)


class BossEnemy(arcade.Sprite):
    def __init__(self, texture, scale):
        super().__init__(texture, scale)
        self.hp = BOSS_HP
        self.state = "normal"
        self.state_timer = 0
        self.shoot_timer = 0


class Bullet(arcade.Sprite):
    def __init__(self, texture, scale, dx, dy, damage_amount=8):
        super().__init__(texture, scale)
        self.change_x = dx
        self.change_y = dy
        self.damage = damage_amount

    def update(self):
        self.change_y -= PROJECTILE_GRAVITY
        self.center_x += self.change_x
        self.center_y += self.change_y


class MyGame(arcade.Window):
    def __init__(self):
        super().__init__(title=SCREEN_TITLE, fullscreen=True)
        self.screen_width, self.screen_height = self.get_size()

        # переменные
        self.game_state = STATE_MENU
        self.current_level = 1
        self.player_hp = PLAYER_START_HP
        self.last_hit_time = 0
        self.last_attack_time = 0
        self.is_facing_right = True
        self.countdown_value = 3.0
        self.total_time = 0.0
        self.win_timer = 0.0  # таймер для победы

        self.scene = None
        self.player_sprite = None
        self.physics_engine = None
        self.camera = None
        self.gui_camera = None
        self.textures = {}
        self.scales = {}
        self.music_player = None

        self.files = {
            "player": "assets/images/player_idle.jpg",
            "player_attack": "assets/images/player_attack.png",
            "ground": "assets/images/grassMid.png",
            "platform": "assets/images/grassHalfMid.png",
            "enemy": "assets/images/enemyFloating_1.png",
            "ghost": "assets/images/ghost.png",
            "projectile": "assets/images/projectile.png",
            "coin": "assets/images/coinGold.jpg",
            "bg": "assets/images/bg_castle.jpg",
            "bush": "assets/images/bush.jpg",
            "boss": "assets/images/boss_new.png",
            "boss_bg": "assets/images/boss_bg.jpg"
        }

    def load_resources(self):
        if self.textures: return

        # грузим все
        self.textures["player_r"] = prepare_texture(self.files["player"], mirror=False)
        self.textures["player_l"] = prepare_texture(self.files["player"], mirror=True)
        self.textures["player_attack_r"] = prepare_texture(self.files["player_attack"], mirror=False)
        self.textures["player_attack_l"] = prepare_texture(self.files["player_attack"], mirror=True)
        self.textures["enemy"] = prepare_texture(self.files["enemy"])
        self.textures["ghost"] = prepare_texture(self.files["ghost"])
        self.textures["projectile"] = prepare_texture(self.files["projectile"])
        self.textures["boss"] = prepare_texture(self.files["boss"])
        self.textures["bush"] = prepare_texture(self.files["bush"])

        self.textures["bg_1"] = prepare_texture(self.files["bg"], should_clean_bg=False)
        self.textures["bg_boss"] = prepare_texture(self.files["boss_bg"], should_clean_bg=False)
        self.textures["ground"] = prepare_texture(self.files["ground"], should_clean_bg=False)
        self.textures["platform"] = prepare_texture(self.files["platform"], should_clean_bg=False)
        self.textures["coin"] = prepare_texture(self.files["coin"], should_clean_bg=False)

        s_blok = self.textures["ground"].width
        if s_blok == 0: s_blok = 128
        self.scales["tile"] = BLOCK_SIZE / s_blok
        self.scales["player"] = (BLOCK_SIZE * 1.2) / self.textures["player_r"].height
        self.scales["enemy"] = (BLOCK_SIZE * 0.9) / self.textures["enemy"].height
        self.scales["ghost"] = (BLOCK_SIZE * 1.8) / self.textures["ghost"].height
        self.scales["boss"] = (BLOCK_SIZE * 4.5) / self.textures["boss"].height

        try:
            self.sound_jump = arcade.load_sound(":resources:sounds/jump1.wav")
            self.sound_hit = arcade.load_sound(":resources:sounds/hit3.wav")
            self.sound_attack = arcade.load_sound(":resources:sounds/fall3.wav")

            self.bg_music = None
            self.boss_music = None
            try:
                self.bg_music = arcade.load_sound("assets/music.mp3")
            except:
                pass
            try:
                self.boss_music = arcade.load_sound("726ae3d59a7576a.mp3")
            except:
                pass
        except:
            pass

    def setup(self, level_number):
        self.current_level = level_number
        self.camera = arcade.Camera2D()
        self.gui_camera = arcade.Camera2D()
        self.scene = arcade.Scene()

        layers = ["Background", "Walls", "Decorations", "Enemies", "Ghosts", "Projectiles", "Boss", "Portal", "Player"]
        for l in layers:
            self.scene.add_sprite_list(l)

        self.load_resources()

        if level_number == 1:
            self.player_hp = PLAYER_START_HP
            self.total_time = 0.0

        if self.music_player:
            arcade.stop_sound(self.music_player)

        track = self.bg_music if level_number == 1 else self.boss_music
        if track:
            try:
                self.music_player = arcade.play_sound(track, loop=True, volume=0.4)
            except:
                pass

        bg_tex = self.textures["bg_1"] if level_number == 1 else self.textures["bg_boss"]
        bg = arcade.Sprite(bg_tex)
        scale = max(self.screen_width / bg.width, self.screen_height / bg.height) * 1.1
        bg.scale = scale
        bg.center_x = self.screen_width / 2
        bg.center_y = self.screen_height / 2
        self.scene.add_sprite("Background", bg)

        t_scale = self.scales["tile"]
        gx = int(self.textures["ground"].width * t_scale) - 1
        gy = int(self.textures["ground"].height * t_scale * 0.75)

        if level_number == 1:
            end_x = 12000
            for x in range(-2000, end_x + 5000, gx):
                for r in range(7):
                    block = arcade.Sprite(self.textures["ground"], scale=t_scale)
                    block.center_x = x
                    block.center_y = 250 - (r * gy)
                    self.scene.add_sprite("Walls", block)

                    if r == 0 and random.random() < 0.18:
                        bush = arcade.Sprite(self.textures["bush"], scale=t_scale * 0.8)
                        bush.center_x = x
                        bush.bottom = block.top
                        self.scene.add_sprite("Decorations", bush)

            for _ in range(70):
                p = arcade.Sprite(self.textures["platform"], scale=t_scale)
                p.center_x = random.randint(500, end_x - 500)
                p.center_y = random.randint(450, 1400)
                self.scene.add_sprite("Walls", p)

            for _ in range(4):
                g = GhostEnemy(self.textures["ghost"], scale=self.scales["ghost"])
                g.center_x = random.randint(1500, end_x - 1000)
                g.center_y = random.randint(700, 1500)
                self.scene.add_sprite("Ghosts", g)

            for _ in range(18):
                b = arcade.Sprite(self.textures["enemy"], scale=self.scales["enemy"])
                b.center_x = random.randint(1000, end_x - 500)
                b.center_y = random.randint(500, 1000)
                b.hp = 40
                self.scene.add_sprite("Enemies", b)

            portal = arcade.Sprite(self.textures["coin"], scale=t_scale * 2.5)
            portal.position = (end_x, 450)
            self.scene.add_sprite("Portal", portal)
            sx, sy = 200, 450
        else:
            for x in range(-6000, 9000, gx):
                for r in range(7):
                    block = arcade.Sprite(self.textures["ground"], scale=t_scale)
                    block.center_x = x
                    block.center_y = 200 - (r * gy)
                    block.color = (40, 40, 60)
                    self.scene.add_sprite("Walls", block)

                    if r == 0 and random.random() < 0.12:
                        bush = arcade.Sprite(self.textures["bush"], scale=t_scale * 0.8)
                        bush.center_x = x
                        bush.bottom = block.top
                        bush.color = (60, 60, 80)
                        self.scene.add_sprite("Decorations", bush)

            for _ in range(30):
                p = arcade.Sprite(self.textures["platform"], scale=t_scale)
                p.center_x = random.randint(-2000, 5000)
                p.center_y = random.randint(400, 1300)
                p.color = (40, 40, 60)
                self.scene.add_sprite("Walls", p)

            boss = BossEnemy(self.textures["boss"], scale=self.scales["boss"])
            boss.center_x = 3000
            boss.bottom = 250
            self.scene.add_sprite("Boss", boss)
            sx, sy = 200, 400

        self.player_sprite = arcade.Sprite(self.textures["player_r"], scale=self.scales["player"])
        self.player_sprite.position = (sx, sy)
        self.scene.add_sprite("Player", self.player_sprite)

        self.physics_engine = arcade.PhysicsEnginePlatformer(
            self.player_sprite, gravity_constant=GRAVITY, walls=self.scene["Walls"]
        )

        self.countdown_value = 3.5
        self.game_state = STATE_COUNTDOWN

    def on_draw(self):
        self.clear()

        # меню
        if self.game_state == STATE_MENU:
            self.load_resources()
            f = arcade.Sprite(self.textures["bg_1"])
            f.scale = max(self.width / f.width, self.height / f.height) * 1.1
            f.center_x = self.width / 2
            f.center_y = self.height / 2
            sl = arcade.SpriteList()
            sl.append(f)
            sl.draw()

            arcade.draw_text("Hard Quest", self.width / 2, self.height / 2 + 100, arcade.color.GOLD, 60,
                             anchor_x="center", bold=True)
            arcade.draw_text("Жми ENTER чтобы играть", self.width / 2, self.height / 2, arcade.color.WHITE, 30,
                             anchor_x="center")
            return

        # игра
        self.camera.use()
        self.scene.draw()

        # интерфейс
        self.gui_camera.use()
        arcade.draw_lrbt_rectangle_filled(40, 340, self.height - 70, self.height - 30, arcade.color.BLACK)

        zhizn = max(0, self.player_hp / PLAYER_START_HP)
        col = arcade.color.GREEN if zhizn > 0.3 else arcade.color.RED
        arcade.draw_lrbt_rectangle_filled(40, 40 + (zhizn * 300), self.height - 70, self.height - 30, col)
        arcade.draw_text(f"HP: {int(self.player_hp)}", 50, self.height - 65, arcade.color.WHITE, 18, bold=True)

        m = int(self.total_time // 60)
        s = int(self.total_time % 60)
        arcade.draw_text(f"TIME: {m:02d}:{s:02d}", self.width - 250, self.height - 65, arcade.color.GOLD, 24, bold=True)

        if self.current_level == 2 and self.scene["Boss"]:
            bhp = max(0, int(self.scene["Boss"][0].hp))
            arcade.draw_text(f"BOSS HP: {bhp}", self.width / 2, self.height - 60, arcade.color.RED, 35,
                             anchor_x="center", bold=True)

        if self.game_state == STATE_PAUSE:
            arcade.draw_lrbt_rectangle_filled(0, self.width, 0, self.height, (0, 0, 0, 120))
            arcade.draw_text("ПАУЗА", self.width / 2, self.height / 2, arcade.color.WHITE, 80, anchor_x="center",
                             bold=True)

        if self.game_state == STATE_COUNTDOWN:
            txt = str(int(self.countdown_value)) if self.countdown_value > 0 else "GO!"
            arcade.draw_text(txt, self.width / 2, self.height / 2, arcade.color.WHITE, 150, anchor_x="center",
                             bold=True)

        if self.game_state == STATE_GAME_OVER:
            arcade.draw_lrbt_rectangle_filled(0, self.width, 0, self.height, (0, 0, 0, 160))
            arcade.draw_text("GAME OVER", self.width / 2, self.height / 2 + 60, arcade.color.RED, 80, anchor_x="center",
                             bold=True)
            arcade.draw_text("R - Рестарт  |  Q - Выход", self.width / 2, self.height / 2 - 40, arcade.color.WHITE, 30,
                             anchor_x="center")

        elif self.game_state == STATE_WIN:
            arcade.draw_text("ПОБЕДА!", self.width / 2, self.height / 2, arcade.color.GOLD, 100, anchor_x="center",
                             bold=True)

    def boss_ai_tick(self, boss, dt):
        dx = self.player_sprite.center_x - boss.center_x
        dy = self.player_sprite.center_y - boss.center_y
        dist = math.sqrt(dx * dx + dy * dy)

        boss.state_timer -= dt
        boss.shoot_timer -= dt

        if boss.state == "normal":
            spd = BOSS_NORMAL_SPEED
            boss.color = arcade.color.WHITE
            if boss.state_timer <= 0:
                boss.state = "dash"
                boss.state_timer = 1.5
        else:
            spd = BOSS_DASH_SPEED
            boss.color = (255, 100, 100)
            if boss.state_timer <= 0:
                boss.state = "normal"
                boss.state_timer = 3.0

        if dist > 0:
            boss.center_x += (dx / dist) * spd
            boss.center_y += (dy / dist) * spd

        if boss.shoot_timer <= 0 and dist < 1500:
            self.make_projectile(boss, dx, dy, dist, dmg=BOSS_PROJECTILE_DAMAGE, size=0.6)
            boss.shoot_timer = 2.5

    def on_update(self, delta_time):
        # ЛОГИКА ВОЗВРАТА В МЕНЮ ПОСЛЕ ПОБЕДЫ
        if self.game_state == STATE_WIN:
            self.win_timer += delta_time
            if self.win_timer >= 5.0:
                self.game_state = STATE_MENU
            return

        if self.game_state in [STATE_MENU, STATE_PAUSE, STATE_GAME_OVER]: return
        if not self.physics_engine: return

        if self.game_state == STATE_COUNTDOWN:
            self.countdown_value -= delta_time
            if self.countdown_value <= 0.5: self.game_state = STATE_GAME

        if self.game_state == STATE_GAME:
            self.total_time += delta_time

        self.physics_engine.update()
        self.camera.position = (self.player_sprite.center_x, self.player_sprite.center_y)

        if self.scene["Background"]:
            self.scene["Background"][0].position = self.camera.position

        # мыши
        for b in self.scene["Enemies"]:
            bx = self.player_sprite.center_x - b.center_x
            by = self.player_sprite.center_y - b.center_y
            bd = math.sqrt(bx * bx + by * by)

            if bd < 1200:
                b.center_x += (bx / bd) * ENEMY_SPEED
                b.center_y += (by / bd) * ENEMY_SPEED

            if arcade.check_for_collision(self.player_sprite, b):
                self.take_damage(ENEMY_DAMAGE)

            if time.time() - self.last_attack_time > 0.3: b.color = arcade.color.WHITE

        # босс
        if self.scene["Boss"]:
            boss = self.scene["Boss"][0]
            self.boss_ai_tick(boss, delta_time)
            if arcade.check_for_collision(self.player_sprite, boss):
                self.take_damage(BOSS_COLLISION_DAMAGE)

        # призраки
        for g in self.scene["Ghosts"]:
            gx = self.player_sprite.center_x - g.center_x
            gy = self.player_sprite.center_y - g.center_y
            gd = math.sqrt(gx * gx + gy * gy)

            if gd > 600:
                g.center_x += (gx / gd) * GHOST_SPEED
                g.center_y += (gy / gd) * GHOST_SPEED
            elif gd < 450:
                g.center_x -= (gx / gd) * GHOST_SPEED
                g.center_y -= (gy / gd) * GHOST_SPEED

            if time.time() - g.last_shoot_time > GHOST_SHOOT_DELAY and gd < 1100:
                self.make_projectile(g, gx, gy, gd)
                g.last_shoot_time = time.time()

            if arcade.check_for_collision(self.player_sprite, g):
                self.take_damage(10)

            if time.time() - self.last_attack_time > 0.3: g.color = arcade.color.WHITE

        # пули
        for p in self.scene["Projectiles"]:
            p.update()
            if arcade.check_for_collision(self.player_sprite, p):
                self.take_damage(p.damage)
                p.remove_from_sprite_lists()
            elif abs(p.center_x - self.player_sprite.center_x) > 2500:
                p.remove_from_sprite_lists()

        # анимация
        self.player_sprite.alpha = 150 if time.time() - self.last_hit_time < 0.2 else 255

        tex_prefix = "player_attack" if time.time() - self.last_attack_time < ATTACK_DURATION else "player"
        suffix = "_r" if self.is_facing_right else "_l"
        self.player_sprite.texture = self.textures[tex_prefix + suffix]

        # портал
        if self.current_level == 1 and self.scene["Portal"]:
            if arcade.check_for_collision(self.player_sprite, self.scene["Portal"][0]):
                self.setup(2)

        # упал
        if self.player_sprite.center_y < -600:
            self.take_damage(25)
            if self.player_hp > 0: self.player_sprite.position = (200, 600)

    def make_projectile(self, from_obj, dx, dy, dist, dmg=8, size=0.3):
        if dist == 0: return
        vx = (dx / dist) * PROJECTILE_SPEED
        vy = (dy / dist) * PROJECTILE_SPEED
        p = Bullet(self.textures["projectile"], size, vx, vy, dmg)
        p.position = from_obj.position
        self.scene.add_sprite("Projectiles", p)

    def do_player_attack(self):
        if self.game_state != STATE_GAME: return
        self.last_attack_time = time.time()
        if self.sound_attack: arcade.play_sound(self.sound_attack)

        for lst in ["Enemies", "Ghosts", "Boss"]:
            for t in self.scene[lst]:
                if arcade.get_distance_between_sprites(self.player_sprite, t) < ATTACK_RANGE:
                    t.hp -= PLAYER_DAMAGE
                    t.color = arcade.color.RED
                    if t.hp <= 0:
                        t.remove_from_sprite_lists()
                        if self.current_level == 2 and not self.scene["Boss"]:
                            self.game_state = STATE_WIN
                            self.win_timer = 0.0  # сброс таймера

    def take_damage(self, amount):
        if self.player_hp <= 0 or time.time() - self.last_hit_time < INVULNERABILITY_TIME: return
        self.player_hp = max(0, self.player_hp - amount)
        self.last_hit_time = time.time()
        if self.sound_hit: arcade.play_sound(self.sound_hit)
        self.player_sprite.change_y = 15
        if self.player_hp == 0: self.game_state = STATE_GAME_OVER

    def on_key_press(self, key, mods):
        if self.game_state == STATE_MENU:
            if key == arcade.key.ENTER: self.setup(1)
        elif self.game_state == STATE_GAME:
            if key in [arcade.key.P, arcade.key.ESCAPE]:
                self.game_state = STATE_PAUSE
            elif key in [arcade.key.UP, arcade.key.W, arcade.key.SPACE] and self.physics_engine.can_jump():
                self.player_sprite.change_y = PLAYER_JUMP_SPEED
                arcade.play_sound(self.sound_jump)
            elif key in [arcade.key.LEFT, arcade.key.A]:
                self.player_sprite.change_x = -PLAYER_SPEED
                self.is_facing_right = False
            elif key in [arcade.key.RIGHT, arcade.key.D]:
                self.player_sprite.change_x = PLAYER_SPEED
                self.is_facing_right = True
            elif key == arcade.key.X:
                self.do_player_attack()
        elif self.game_state == STATE_PAUSE:
            if key in [arcade.key.P, arcade.key.ESCAPE]: self.game_state = STATE_GAME
        elif self.game_state == STATE_GAME_OVER:
            if key == arcade.key.R:
                self.setup(1)
            elif key == arcade.key.Q:
                self.game_state = STATE_MENU

    def on_key_release(self, key, mods):
        if key in [arcade.key.LEFT, arcade.key.A, arcade.key.RIGHT, arcade.key.D]:
            self.player_sprite.change_x = 0


if __name__ == "__main__":
    window = MyGame()
    arcade.run()
