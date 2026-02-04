import arcade
import random
import math
import time
import os
from PIL import Image, ImageDraw
from arcade.types import XYWH

# --- НАСТРОЙКИ ---
SCREEN_TITLE = "Pro Platformer: Flying Enemies & Fixes"

# Размер блока
BLOCK_SIZE = 128

# Баланс
PLAYER_START_HP = 100
PLAYER_DAMAGE = 35
ENEMY_DAMAGE = 15
INVULNERABILITY_TIME = 1.0

# Физика
GRAVITY = 1.5
PLAYER_SPEED = 9
PLAYER_JUMP_SPEED = 32
ATTACK_RANGE = 200  # Чуть увеличил дальность атаки

# Состояния
STATE_MENU = 0
STATE_GAME = 1
STATE_GAME_OVER = 2
STATE_WIN = 3


def clean_texture(filename, mirror=False):
    """ Умная загрузка текстур с очисткой фона """
    if filename.startswith(":"):
        tex = arcade.load_texture(filename)
        if mirror:
            return arcade.Texture(tex.image.transpose(Image.FLIP_LEFT_RIGHT))
        return tex

    if not os.path.exists(filename):
        # Fallback на смену расширения
        if filename.endswith(".jpg"):
            alt = filename.replace(".jpg", ".png")
        elif filename.endswith(".png"):
            alt = filename.replace(".png", ".jpg")
        else:
            alt = filename

        if os.path.exists(alt):
            filename = alt
        else:
            print(f"Файл не найден: {filename}")
            return arcade.make_soft_square_texture(30, arcade.color.GRAY)

    try:
        img = Image.open(filename).convert("RGBA")
        datas = img.getdata()
        new_data = []
        # Удаляем белый и почти белый фон
        for item in datas:
            # Если пиксель светлый (почти белый), делаем его прозрачным
            if item[0] > 210 and item[1] > 210 and item[2] > 210:
                new_data.append((255, 255, 255, 0))
            else:
                new_data.append(item)
        img.putdata(new_data)

        # !!! ИСПРАВЛЕНИЕ: Обрезаем невидимые края, чтобы не было левитации
        bbox = img.getbbox()
        if bbox:
            img = img.crop(bbox)

        if mirror: img = img.transpose(Image.FLIP_LEFT_RIGHT)
        return arcade.Texture(img)
    except:
        return arcade.make_soft_square_texture(30, arcade.color.GRAY)


class MyGame(arcade.Window):
    def __init__(self):
        super().__init__(title=SCREEN_TITLE, fullscreen=True)
        self.screen_width, self.screen_height = self.get_size()

        # Убираем размытие краев, чтобы не было щелей между блоками
        try:
            self.ctx.default_texture_filter = (arcade.gl.NEAREST, arcade.gl.NEAREST)
        except:
            pass

        self.game_state = STATE_MENU
        self.current_level = 1

        self.scene = None
        self.player_sprite = None
        self.physics_engine = None
        self.camera = None
        self.gui_camera = None

        self.player_hp = PLAYER_START_HP
        self.score = 0
        self.last_hit_time = 0
        self.is_facing_right = True

        self.textures = {}
        self.scales = {}
        self.bg_music = None
        self.boss_music = None
        self.music_player = None

        # --- ЗВУКИ ---
        try:
            self.sound_jump = arcade.load_sound(":resources:sounds/jump1.wav")
            self.sound_hit = arcade.load_sound(":resources:sounds/hit3.wav")
            self.sound_attack = arcade.load_sound(":resources:sounds/fall3.wav")
            self.bg_music = arcade.load_sound("assets/music.mp3")
            self.boss_music = arcade.load_sound("726ae3d59a7576a.mp3")
        except:
            pass

        # --- ФАЙЛЫ ---
        self.files = {
            "player": "assets/images/player_idle.jpg",
            "ground": "assets/images/grassMid.jpg",
            "platform": "assets/images/grassHalfMid.jpg",
            "enemy": "assets/images/enemyFloating_1.png",
            "coin": "assets/images/coinGold.jpg",
            "bg": "assets/images/bg_castle.jpg",
            "bush": "assets/images/bush.jpg",
            "boss": "assets/images/boss_new.png",
            "boss_bg": "assets/images/boss_bg.jpg"
        }

    def load_resources(self):
        if self.textures: return
        print("Загрузка текстур...")

        self.textures["player_r"] = clean_texture(self.files["player"])
        self.textures["player_l"] = clean_texture(self.files["player"], mirror=True)
        self.textures["ground"] = clean_texture(self.files["ground"])
        self.textures["platform"] = clean_texture(self.files["platform"])
        self.textures["enemy"] = clean_texture(self.files["enemy"])
        self.textures["boss"] = clean_texture(self.files["boss"])
        self.textures["coin"] = clean_texture(self.files["coin"])
        self.textures["bush"] = clean_texture(self.files["bush"])

        gw = self.textures["ground"].width if self.textures["ground"].width > 0 else 64
        self.scales["tile"] = BLOCK_SIZE / gw

        ph = self.textures["player_r"].height if self.textures["player_r"].height > 0 else 64
        self.scales["player"] = (BLOCK_SIZE * 1.2) / ph

        eh = self.textures["enemy"].height if self.textures["enemy"].height > 0 else 64
        self.scales["enemy"] = (BLOCK_SIZE * 0.9) / eh

        bh = self.textures["boss"].height if self.textures["boss"].height > 0 else 64
        self.scales["boss"] = (BLOCK_SIZE * 3.5) / bh

    def play_level_music(self, level):
        if self.music_player:
            try:
                self.music_player.pause()
            except:
                pass
            self.music_player = None

        new_music = None
        if level == 1:
            new_music = self.bg_music
        elif level == 2:
            new_music = self.boss_music

        if new_music:
            try:
                self.music_player = arcade.play_sound(new_music, loop=True, volume=0.5)
            except:
                pass

    def setup(self, level):
        self.current_level = level
        self.camera = arcade.Camera2D()
        self.gui_camera = arcade.Camera2D()
        self.scene = arcade.Scene()

        self.load_resources()
        if level == 1: self.player_hp = PLAYER_START_HP

        self.play_level_music(level)

        # === ФОН ===
        bg_path = self.files["bg"]
        if level == 2: bg_path = self.files["boss_bg"]

        try:
            if not os.path.exists(bg_path):
                if bg_path.endswith(".jpg"):
                    bg_path = bg_path.replace(".jpg", ".png")
                else:
                    bg_path = bg_path.replace(".png", ".jpg")

            bg = arcade.Sprite(bg_path)
            scale_w = self.screen_width / bg.width
            scale_h = self.screen_height / bg.height
            bg.scale = max(scale_w, scale_h) * 1.2
            bg.center_x = self.screen_width // 2
            bg.center_y = self.screen_height // 2
            self.scene.add_sprite("Background", bg)
        except:
            pass

        # === ПАРАМЕТРЫ СЕТКИ ===
        tile_scale = self.scales["tile"]
        real_tile_w = int(self.textures["ground"].width * tile_scale)
        real_tile_h = int(self.textures["ground"].height * tile_scale)

        # Шаг чуть меньше ширины для плотной стыковки
        step_x = real_tile_w - 1
        step_y = int(real_tile_h * 0.75)

        # ==========================================
        # УРОВЕНЬ 1: КОМПАКТНЫЙ И НАСЫЩЕННЫЙ
        # ==========================================
        if level == 1:
            rows = 6
            surface_level_y = 250
            LEVEL_LENGTH = 7000  # Сократили длину (было 20к)

            # --- ЗЕМЛЯ ---
            for x in range(-1000, LEVEL_LENGTH, step_x):
                for r in range(rows):
                    wall = arcade.Sprite(self.textures["ground"], scale=tile_scale)
                    wall.center_x = int(x)
                    depth_index = (rows - 1) - r
                    wall.center_y = int(surface_level_y - (depth_index * step_y))
                    # Нахлест для отсутствия щелей
                    wall.width += 2
                    self.scene.add_sprite("Walls", wall)

                    if r == rows - 1:
                        if random.random() < 0.20:
                            bush = arcade.Sprite(self.textures["bush"], scale=tile_scale * 0.8)
                            bush.center_x = x
                            bush.bottom = wall.top - 10
                            self.scene.add_sprite("Decorations", bush)

            # --- ВРАГИ (Летающие и преследующие) ---
            # Спавним их в случайных местах в воздухе
            for i in range(15):  # 15 врагов на уровень
                enemy_x = random.randint(1000, LEVEL_LENGTH - 1000)
                enemy_y = random.randint(surface_level_y + 100, surface_level_y + 600)

                enemy = arcade.Sprite(self.textures["enemy"], scale=self.scales["enemy"])
                enemy.position = (enemy_x, enemy_y)
                enemy.hp = 40

                # !!! ВАЖНО: Detailed убирает "невидимые барьеры" вокруг спрайта
                enemy.hit_box_algorithm = "Detailed"
                self.scene.add_sprite("Enemies", enemy)

            # --- ПЛАТФОРМЫ ---
            current_x = 800
            while current_x < LEVEL_LENGTH - 1000:
                struct_type = random.choice([1, 2, 3])
                if struct_type == 1:
                    plat = arcade.Sprite(self.textures["platform"], scale=tile_scale)
                    plat.position = (current_x, surface_level_y + 250)
                    plat.hit_box_algorithm = "Detailed"
                    self.scene.add_sprite("Walls", plat)
                    current_x += 500
                elif struct_type == 2:
                    for i in range(3):
                        plat = arcade.Sprite(self.textures["platform"], scale=tile_scale)
                        plat.position = (current_x + (i * 250), surface_level_y + 250 + (i * 150))
                        plat.hit_box_algorithm = "Detailed"
                        self.scene.add_sprite("Walls", plat)
                    current_x += 1000
                elif struct_type == 3:
                    # Длинный мост
                    for i in range(4):
                        plat = arcade.Sprite(self.textures["platform"], scale=tile_scale)
                        plat.position = (current_x + (i * real_tile_w), surface_level_y + 400)
                        plat.hit_box_algorithm = "Detailed"
                        self.scene.add_sprite("Walls", plat)
                    current_x += 1200

            # ПОРТАЛ
            portal = arcade.Sprite(self.textures["coin"], scale=tile_scale * 2.0)
            portal.position = (LEVEL_LENGTH - 500, surface_level_y + 150)
            portal.hit_box_algorithm = "Detailed"
            self.scene.add_sprite("Portal", portal)

            start_pos = (200, surface_level_y + 150)

        # ==========================================
        # УРОВЕНЬ 2: АРЕНА БОССА
        # ==========================================
        elif level == 2:
            surface_y = 200
            ARENA_WIDTH = 4500

            # Пол
            for x in range(-500, ARENA_WIDTH, step_x):
                for r in range(4):
                    wall = arcade.Sprite(self.textures["ground"], scale=tile_scale)
                    depth_index = 3 - r
                    wall.center_x = int(x)
                    wall.center_y = int(surface_y - (depth_index * step_y))
                    # Нахлест для отсутствия щелей
                    wall.width += 2
                    self.scene.add_sprite("Walls", wall)

            # Стены
            for y in range(0, 3000, step_y):
                w1 = arcade.Sprite(self.textures["ground"], scale=tile_scale)
                w1.position = (-200, y)
                self.scene.add_sprite("Walls", w1)
                w2 = arcade.Sprite(self.textures["ground"], scale=tile_scale)
                w2.position = (ARENA_WIDTH, y)
                self.scene.add_sprite("Walls", w2)

            # Платформы
            coords = [(800, 350), (1200, 550), (ARENA_WIDTH - 800, 350), (ARENA_WIDTH - 1200, 550),
                      (ARENA_WIDTH // 2, 750)]
            for cx, cy in coords:
                p = arcade.Sprite(self.textures["platform"], scale=tile_scale)
                p.position = (cx, surface_y + cy)
                p.hit_box_algorithm = "Detailed"
                self.scene.add_sprite("Walls", p)

            # БОСС
            boss = arcade.Sprite(self.textures["boss"], scale=self.scales["boss"])
            boss.center_x = ARENA_WIDTH // 2
            boss.bottom = surface_y + 50
            boss.hp = 1000
            boss.hit_box_algorithm = "Detailed"  # ИСПРАВЛЕНИЕ БАРЬЕРА БОССА
            self.scene.add_sprite("Boss", boss)

            start_pos = (200, surface_y + 150)

        # Игрок
        self.player_sprite = arcade.Sprite(self.textures["player_r"], scale=self.scales["player"])
        self.player_sprite.position = start_pos
        self.player_sprite.hit_box_algorithm = "Detailed"
        self.scene.add_sprite("Player", self.player_sprite)

        # Физика (только стены твердые!)
        self.physics_engine = arcade.PhysicsEnginePlatformer(
            self.player_sprite, gravity_constant=GRAVITY, walls=self.scene["Walls"]
        )

    def player_attack(self):
        if self.sound_attack: arcade.play_sound(self.sound_attack)
        self.player_sprite.center_x += 20 if self.is_facing_right else -20

        hit_list = []
        if "Enemies" in self.scene:
            for enemy in self.scene["Enemies"]:
                if arcade.get_distance_between_sprites(self.player_sprite, enemy) < ATTACK_RANGE:
                    hit_list.append(enemy)
        if "Boss" in self.scene:
            for boss in self.scene["Boss"]:
                if arcade.get_distance_between_sprites(self.player_sprite, boss) < ATTACK_RANGE + 200:
                    hit_list.append(boss)

        for enemy in hit_list:
            enemy.hp -= PLAYER_DAMAGE
            if self.sound_hit: arcade.play_sound(self.sound_hit)
            enemy.center_x += 50 if self.is_facing_right else -50
            enemy.color = arcade.color.RED
            if enemy.hp <= 0:
                enemy.remove_from_sprite_lists()
                self.score += 100
                if self.current_level == 2 and "Boss" in self.scene and not self.scene["Boss"]:
                    self.game_state = STATE_WIN

    def take_damage(self):
        if time.time() - self.last_hit_time < INVULNERABILITY_TIME: return
        self.player_hp -= ENEMY_DAMAGE
        self.last_hit_time = time.time()
        if self.sound_hit: arcade.play_sound(self.sound_hit)
        self.player_sprite.change_y = 15
        self.player_sprite.change_x = -20 if self.is_facing_right else 20
        if self.player_hp <= 0: self.game_state = STATE_GAME_OVER

    def on_draw(self):
        self.clear()
        W, H = self.screen_width, self.screen_height

        if self.game_state == STATE_MENU:
            arcade.Text("EPIC KNIGHT: FIXES", W / 2, H / 2 + 60, arcade.color.GOLD, 50, anchor_x="center").draw()
            arcade.Text("ENTER - Старт", W / 2, H / 2, arcade.color.WHITE, 20, anchor_x="center").draw()
            return

        if self.camera: self.camera.use()
        self.scene.draw()

        if self.gui_camera:
            self.gui_camera.use()
            arcade.draw_rect_filled(XYWH(180, H - 50, 304, 34), arcade.color.WHITE)
            arcade.draw_rect_filled(XYWH(180, H - 50, 300, 30), arcade.color.GRAY)
            hp_w = (self.player_hp / PLAYER_START_HP) * 300
            if hp_w < 0: hp_w = 0
            arcade.draw_rect_filled(XYWH(30 + hp_w / 2, H - 50, hp_w, 30), arcade.color.RED)
            arcade.Text(f"HP: {self.player_hp}", 180, H - 60, arcade.color.WHITE, 16, anchor_x="center").draw()
            arcade.Text(f"Score: {self.score}", 30, H - 100, arcade.color.GOLD, 24).draw()
            if "Boss" in self.scene and self.scene["Boss"]:
                boss = self.scene["Boss"][0]
                arcade.Text(f"BOSS: {boss.hp}", W - 200, H - 60, arcade.color.RED, 30, bold=True).draw()

        if self.game_state == STATE_GAME_OVER:
            arcade.draw_rect_filled(XYWH(W / 2, H / 2, W, H), (0, 0, 0, 200))
            arcade.Text("GAME OVER", W / 2, H / 2, arcade.color.RED, 60, anchor_x="center").draw()
            arcade.Text("R - Рестарт", W / 2, H / 2 - 70, arcade.color.WHITE, 20, anchor_x="center").draw()
        elif self.game_state == STATE_WIN:
            arcade.draw_rect_filled(XYWH(W / 2, H / 2, W, H), (0, 0, 0, 200))
            arcade.Text("VICTORY!", W / 2, H / 2, arcade.color.GOLD, 60, anchor_x="center").draw()

    def on_update(self, delta_time):
        if self.game_state != STATE_GAME: return

        # Мигание при уроне
        if time.time() - self.last_hit_time > 0.2:
            self.player_sprite.alpha = 255
            if "Enemies" in self.scene:
                for e in self.scene["Enemies"]: e.color = arcade.color.WHITE
            if "Boss" in self.scene:
                for b in self.scene["Boss"]: b.color = arcade.color.WHITE
        else:
            self.player_sprite.alpha = 150

        self.physics_engine.update()

        # Камера
        self.camera.position = (self.player_sprite.center_x, self.player_sprite.center_y)
        if "Background" in self.scene and self.scene["Background"]:
            bg = self.scene["Background"][0]
            bg.center_x = self.camera.position.x
            bg.center_y = self.camera.position.y

        # --- ИИ ВРАГОВ (ПРЕСЛЕДОВАНИЕ) ---
        enemies = []
        if "Enemies" in self.scene: enemies.extend(self.scene["Enemies"])
        if "Boss" in self.scene: enemies.extend(self.scene["Boss"])

        for enemy in enemies:
            # Вычисляем вектор до игрока
            dx = self.player_sprite.center_x - enemy.center_x
            dy = self.player_sprite.center_y - enemy.center_y

            # Дистанция агра (враги видят на 900 пикселей)
            distance = math.sqrt(dx * dx + dy * dy)

            if distance < 900:
                # Нормализуем вектор (чтобы скорость была одинаковой по диагонали)
                speed = 4  # Скорость полета

                # Если это босс, он чуть медленнее, но упорнее
                if "Boss" in self.scene and enemy in self.scene["Boss"]:
                    speed = 3.5

                angle = math.atan2(dy, dx)
                enemy.change_x = math.cos(angle) * speed
                enemy.change_y = math.sin(angle) * speed
            else:
                # Если игрок далеко, враг замедляется
                enemy.change_x *= 0.95
                enemy.change_y *= 0.95

            # Двигаем врага (PhysicsEnginePlatformer не управляет врагами в "Enemies", так что двигаем вручную)
            enemy.center_x += enemy.change_x
            enemy.center_y += enemy.change_y

            # Проверка столкновения с игроком
            if arcade.check_for_collision(self.player_sprite, enemy):
                self.take_damage()

        # Портал
        if self.current_level == 1 and "Portal" in self.scene:
            if arcade.check_for_collision(self.player_sprite, self.scene["Portal"][0]):
                self.setup(2)

        # Падение
        if self.player_sprite.center_y < -300:
            self.take_damage()
            self.player_sprite.center_y = 500
            self.player_sprite.center_x = 200

    def on_key_press(self, key, modifiers):
        if key == arcade.key.ESCAPE: self.close()
        if self.game_state == STATE_MENU:
            if key == arcade.key.ENTER:
                self.game_state = STATE_GAME
                self.setup(1)
            return
        if key == arcade.key.R and self.game_state == STATE_GAME_OVER:
            self.game_state = STATE_GAME
            self.setup(1)
            return

        if self.game_state == STATE_GAME:
            if key in [arcade.key.UP, arcade.key.W, arcade.key.SPACE]:
                if self.physics_engine.can_jump():
                    self.player_sprite.change_y = PLAYER_JUMP_SPEED
            elif key in [arcade.key.LEFT, arcade.key.A]:
                self.player_sprite.change_x = -PLAYER_SPEED
                self.is_facing_right = False
                self.player_sprite.texture = self.textures["player_l"]
            elif key in [arcade.key.RIGHT, arcade.key.D]:
                self.player_sprite.change_x = PLAYER_SPEED
                self.is_facing_right = True
                self.player_sprite.texture = self.textures["player_r"]
            elif key == arcade.key.X:
                self.player_attack()

    def on_key_release(self, key, modifiers):
        if key in [arcade.key.LEFT, arcade.key.A, arcade.key.RIGHT, arcade.key.D]:
            self.player_sprite.change_x = 0


if __name__ == "__main__":
    window = MyGame()
    arcade.run()